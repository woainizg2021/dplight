import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
import json
from thefuzz import process
import io
import dashscope
from http import HTTPStatus
import os
import datetime
import time
import re

# ================= 1. 配置区域 =================
DB_HOST = 'cmal_hk001-ww.rwxyun.site'
DB_PORT = '3433'

DATABASES = {
    "🇳🇬 尼日利亚": {"user": "hzgjmy616329", "pass": "axup_-22637483", "db": "CMCSYUN355738"},
    "🇺🇬 乌干达":   {"user": "ywszmjckyxgs_ggfn599939", "pass": "0Nk107HO-321S!-_", "db": "CMCSYUN532502"},
    "🇰🇪 肯尼亚":   {"user": "ywszmjckyxgs_ggfn599939", "pass": "0Nk107HO-321S!-_", "db": "CMCSYUN4348395"}
}

DASHSCOPE_API_KEY = "sk-02b08633efa44a6bb6bd45bad735c80d" 
dashscope.api_key = DASHSCOPE_API_KEY

# ================= 2. 数据库工具 =================
def get_mssql_engine(config):
    password = quote_plus(config["pass"])
    conn_str = f"mssql+pymssql://{config['user']}:{password}@{DB_HOST}:{DB_PORT}/{config['db']}?charset=utf8"
    engine = create_engine(conn_str)
    return engine

# ================= 3. AI 识别 =================
def analyze_image_with_qwen(image_bytes):
    temp_filename = f"/root/temp_{int(time.time()*1000)}.jpg"
    with open(temp_filename, "wb") as f:
        f.write(image_bytes)
    img_uri = f"file://{temp_filename}"

    prompt = """
    你是一位财务审计员，审核一张【非洲复写纸单据】。
    !!! 核心提取任务 !!!
    1. 【单据编号(No.)】：在右上角 No. 后面。只提取数字部分！(例如 20599)。
    2. 【客户名】：如果包含 "贸易"、"门市"，请提取。
    3. 【产品】：提取型号（如 DP-902）。
    4. 【日期】：格式 DD-MM-YY。
    
    返回纯 JSON：
    {
        "receipt_no": "纯数字编号",
        "date": "YYYY-MM-DD",
        "customer_name": "客户名",
        "items": [
            {
                "product_name": "产品名",
                "quantity": 数字类型,
                "amount": 数字类型 (总金额)
            }
        ]
    }
    """
    
    ocr_result = {"error": "Unknown Error"}
    for attempt in range(2):
        try:
            messages = [{"role": "user", "content": [{"image": img_uri}, {"text": prompt}]}]
            response = dashscope.MultiModalConversation.call(model='qwen-vl-max', messages=messages)
            
            if response.status_code == HTTPStatus.OK:
                txt = response.output.choices[0].message.content[0]['text']
                txt = txt.replace("```json", "").replace("```", "").strip()
                ocr_result = json.loads(txt)
                break
            else:
                ocr_result = {"error": f"API Error: {response.message}"}
        except Exception as e:
            ocr_result = {"error": f"Exception: {str(e)}"}
            time.sleep(1)
    
    if os.path.exists(temp_filename): os.remove(temp_filename)
    return ocr_result

# ================= 4. 比对逻辑 =================
def perform_audit(hand_data, db_config):
    doc_no = str(hand_data.get('No.', '')).strip()
    doc_date = str(hand_data.get('手写日期', '')).strip()
    doc_cust = str(hand_data.get('手写客户', '')).strip()
    doc_prod = str(hand_data.get('手写产品', '')).strip()
    doc_qty = float(hand_data.get('手写箱数', 0))
    doc_amt = float(hand_data.get('手写金额', 0))

    engine = get_mssql_engine(db_config)
    
    df_system_rows = pd.DataFrame()
    sys_customer_name = "未锁定"
    lock_reason = ""
    match_status = "❌ 单据号未找到"
    target_vchcode = None

    if doc_no and len(doc_no) > 3:
        search_summary = f"%{doc_no}%"
        sql_head = text("""
            SELECT TOP 1 Vchcode, Summary, Date 
            FROM DlyNdx 
            WHERE Summary LIKE :no AND VchType = 11 
            ORDER BY Date DESC
        """)
        try:
            with engine.connect() as conn:
                head_res = pd.read_sql(sql_head, conn, params={"no": search_summary})
            
            if not head_res.empty:
                target_vchcode = int(head_res.iloc[0]['Vchcode'])
                summary_txt = head_res.iloc[0]['Summary']
                lock_reason = f"摘要: {summary_txt}"
                match_status = "⏳ 比对中..."
            else:
                lock_reason = f"无此编号: {doc_no}"
        except Exception as e:
            return {"最终状态": "❌ DB连接失败", "备注": str(e)}
    else:
        lock_reason = "❌ 无编号"

    if target_vchcode:
        sql_detail = text("""
            SELECT 
                d.Date, b.FullName AS [单位全名], p.FullName AS [商品全名], 
                ABS(d.Qty) AS [基本数量], ABS(d.Total) AS [金额],
                ISNULL(NULLIF(p.UnitRate1, 0), 1) AS [装箱率]
            FROM DlySale d
            LEFT JOIN Ptype p ON d.PtypeID = p.TypeID
            LEFT JOIN Btype b ON d.BtypeID = b.TypeID
            WHERE d.Vchcode = :vch
        """)
        with engine.connect() as conn:
            df_system_rows = pd.read_sql(sql_detail, conn, params={"vch": target_vchcode})
        
        if not df_system_rows.empty:
            df_system_rows['系统箱数'] = df_system_rows['基本数量'] / df_system_rows['装箱率']
            sys_customer_name = df_system_rows.iloc[0]['单位全名']
            match_status = "✅ 找到单据"
        else:
            match_status = "❌ 无明细"

    best_p, sys_box, sys_amt = "未找到", 0, 0
    
    if not df_system_rows.empty:
        sys_prods = df_system_rows['商品全名'].unique().tolist()
        d_prod_clean = re.sub(r'pcs\s+of\s+', '', doc_prod, flags=re.IGNORECASE)
        d_prod_clean = re.sub(r'[$$].*?[$$]', '', d_prod_clean).strip()
        
        candidates_by_qty = df_system_rows[abs(df_system_rows['系统箱数'] - doc_qty) < 0.1]
        
        final_row = None
        if not candidates_by_qty.empty:
            if len(candidates_by_qty) == 1:
                final_row = candidates_by_qty.iloc[0]
                best_p = final_row['商品全名']
            else:
                match_p, p_score = process.extractOne(d_prod_clean, candidates_by_qty['商品全名'].tolist())
                final_row = candidates_by_qty[candidates_by_qty['商品全名'] == match_p].iloc[0]
                best_p = match_p
        
        if final_row is None:
            match_p, p_score = process.extractOne(d_prod_clean, sys_prods) if sys_prods else (None, 0)
            if p_score > 40:
                best_p = match_p
                rows = df_system_rows[df_system_rows['商品全名'] == match_p]
                final_row = rows.iloc[0]
            else:
                best_p = f"未找到 (系统含: {','.join(sys_prods[:2])}...)"

        if final_row is not None:
            sys_box = float(final_row['系统箱数'])
            sys_amt = float(final_row['金额'])

    qty_ok = abs(sys_box - doc_qty) < 0.1
    amt_ok = abs(sys_amt - doc_amt) < 10.0 
    
    row_status = "✅ 通过"
    if match_status.startswith("❌"): row_status = match_status
    elif "未找到" in best_p: row_status = "❌ 系统无此品"
    elif not qty_ok: row_status = "❌ 箱数不符"
    elif not amt_ok: row_status = "❌ 金额不符"
        
    cust_check = "✅"
    if sys_customer_name != "未锁定":
         if ("贸易" in doc_cust or "门市" in doc_cust) and "ALI-" in sys_customer_name:
             cust_check = "✅ (挂靠)"
         else:
             _, c_score = process.extractOne(doc_cust, [sys_customer_name])
             if c_score < 40: cust_check = "⚠️ 名字差异"

    return {
        "系统客户": sys_customer_name,
        "客户核对": cust_check,
        "系统产品": best_p,
        "系统箱数": f"{sys_box:.1f}",
        "系统金额": sys_amt,
        "金额核对": "✅" if amt_ok else "❌",
        "最终状态": row_status,
        "备注": lock_reason
    }

# ================= 5. 初始 AI 处理 =================
def process_upload(file_obj, db_config):
    ocr_json = analyze_image_with_qwen(file_obj.getvalue())
    if "error" in ocr_json: return []

    raw_no = str(ocr_json.get('receipt_no', ''))
    doc_no = ''.join(filter(str.isdigit, raw_no))
    if doc_no.startswith("100") and len(doc_no) >= 7: doc_no = doc_no[1:]

    doc_date = ocr_json.get('date', '')
    if doc_date:
        try:
            dt = pd.to_datetime(doc_date)
            if dt.year < 2025: doc_date = doc_date.replace(str(dt.year), "2026")
        except: pass
        
    doc_cust = ocr_json.get('customer_name', 'Unknown')
    
    rows = []
    items = ocr_json.get('items', [])
    if not items:
        rows.append({
            "文件名": file_obj.name, "No.": doc_no, "手写日期": doc_date,
            "手写客户": doc_cust, "手写产品": "", "手写箱数": 0, "手写金额": 0
        })
    else:
        for item in items:
            rows.append({
                "文件名": file_obj.name,
                "No.": doc_no,
                "手写日期": doc_date,
                "手写客户": doc_cust,
                "手写产品": item.get('product_name', ''),
                "手写箱数": float(item.get('quantity', 0)),
                "手写金额": float(item.get('amount', 0))
            })
    return rows

# ================= 6. 界面入口 =================
st.set_page_config(page_title="非洲单据核对", layout="wide")

if 'raw_data' not in st.session_state:
    st.session_state['raw_data'] = pd.DataFrame()
if 'audit_results' not in st.session_state:
    st.session_state['audit_results'] = pd.DataFrame()

col_title, col_db, col_btn = st.columns([2, 1, 1])
with col_title:
    st.title("🌍 非洲单据核对系统")
with col_db:
    selected_db_name = st.selectbox("🏭 选择工厂数据库", list(DATABASES.keys()), label_visibility="collapsed")
    current_db_config = DATABASES[selected_db_name]
with col_btn:
    if st.button("🗑️ 清空所有"):
        st.session_state['raw_data'] = pd.DataFrame()
        st.session_state['audit_results'] = pd.DataFrame()
        st.rerun()

st.markdown("---")

uploaded_files = st.file_uploader("📂 批量上传图片 (支持 JPG/PNG)", type=['jpg', 'png'], accept_multiple_files=True)

if uploaded_files:
    processed_files = set()
    if not st.session_state['raw_data'].empty:
        processed_files = set(st.session_state['raw_data']['文件名'].unique())
    
    new_rows = []
    new_files_count = 0
    
    for f in uploaded_files:
        if f.name not in processed_files:
            new_files_count += 1
            with st.spinner(f"正在识别: {f.name}..."):
                rows = process_upload(f, current_db_config)
                new_rows.extend(rows)
    
    if new_rows:
        new_df = pd.DataFrame(new_rows)
        st.session_state['raw_data'] = pd.concat([st.session_state['raw_data'], new_df], ignore_index=True)
        st.success(f"成功识别 {new_files_count} 张新单据！")

if not st.session_state['raw_data'].empty:
    st.subheader("📝 识别结果 (可编辑 - 发现错误直接改！)")
    
    editable_cols = ["文件名", "No.", "手写日期", "手写客户", "手写产品", "手写箱数", "手写金额"]
    edited_df = st.data_editor(
        st.session_state['raw_data'][editable_cols], 
        num_rows="dynamic",
        use_container_width=True,
        key="data_editor"
    )
    
    if st.button("🔄 应用修正并重新比对", type="primary"):
        results = []
        progress = st.progress(0)
        
        # !!! 修复进度条报错的关键代码 !!!
        for i, (index, row) in enumerate(edited_df.iterrows()):
            progress_val = min((i + 1) / len(edited_df), 1.0)
            progress.progress(progress_val)
            
            audit_res = perform_audit(row, current_db_config)
            combined_row = {**row.to_dict(), **audit_res}
            results.append(combined_row)
            
        st.session_state['audit_results'] = pd.DataFrame(results)
        st.success("✅ 比对完成！")

    if not st.session_state['audit_results'].empty:
        st.markdown("### 📊 最终核对报告")
        final_df = st.session_state['audit_results']
        
        def color_row(val):
            s = str(val)
            if '❌' in s: return 'color: red; font-weight: bold'
            if '✅' in s: return 'color: green'
            if '⚠️' in s: return 'color: orange; font-weight: bold'
            return ''
        
        cols_to_style = [c for c in ['最终状态', '金额核对'] if c in final_df.columns]
        st.dataframe(
            final_df.style.applymap(color_row, subset=cols_to_style),
            use_container_width=True
        )
        
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            final_df.to_excel(writer, index=False)
        st.download_button("📥 下载 Excel 报表", out.getvalue(), f"核对报告_{int(time.time())}.xlsx")