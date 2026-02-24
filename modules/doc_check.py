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
from modules.languages import t

# ================= 1. 配置区域 =================
# 注意：API KEY 最好放在环境变量或 secrets.toml 中，但这里为您保留硬编码方便测试
DASHSCOPE_API_KEY = "sk-02b08633efa44a6bb6bd45bad735c80d" 
dashscope.api_key = DASHSCOPE_API_KEY

# ================= 2. 数据库工具 =================
def get_mssql_engine(db_conf):
    """根据字典配置创建 SQLAlchemy Engine"""
    password = quote_plus(db_conf["pass"])
    conn_str = f"mssql+pymssql://{db_conf['user']}:{password}@{db_conf['host']}:{db_conf['port']}/{db_conf['db']}?charset=utf8"
    engine = create_engine(conn_str)
    return engine

# ================= 3. AI 识别 =================
def analyze_image_with_qwen(image_bytes):
    temp_filename = f"/tmp/temp_{int(time.time()*1000)}.jpg"
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
                txt = re.sub(r'```json\s*', '', txt)
                txt = re.sub(r'```\s*', '', txt).strip()
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
def perform_audit(hand_data, db_conf):
    doc_no = str(hand_data.get('No.', '')).strip()
    doc_qty = float(hand_data.get('手写箱数', 0))
    doc_amt = float(hand_data.get('手写金额', 0))
    doc_prod = str(hand_data.get('手写产品', '')).strip()
    doc_cust = str(hand_data.get('手写客户', '')).strip()

    engine = get_mssql_engine(db_conf)
    
    df_system_rows = pd.DataFrame()
    sys_customer_name = t("未锁定")
    lock_reason = ""
    match_status = "❌ " + t("单据号未找到")
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
                lock_reason = f"{t('摘要')}: {summary_txt}"
                match_status = "⏳ " + t("比对中...")
            else:
                lock_reason = f"{t('无此编号')}: {doc_no}"
        except Exception as e:
            return {t("最终状态"): "❌ DB Error", t("备注"): str(e)}
    else:
        lock_reason = "❌ " + t("无编号")

    if target_vchcode:
        sql_detail = text("""
            SELECT 
                d.Date, CAST(b.FullName AS NVARCHAR(200)) AS [单位全名], CAST(p.FullName AS NVARCHAR(200)) AS [商品全名], 
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
            match_status = "✅ " + t("找到单据")
        else:
            match_status = "❌ " + t("无明细")

    best_p, sys_box, sys_amt = t("未找到"), 0, 0
    
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
                best_p = f"{t('未找到')} (System: {','.join(sys_prods[:2])}...)"

        if final_row is not None:
            sys_box = float(final_row['系统箱数'])
            sys_amt = float(final_row['金额'])

    qty_ok = abs(sys_box - doc_qty) < 0.1
    amt_ok = abs(sys_amt - doc_amt) < 10.0 
    
    row_status = "✅ " + t("通过")
    if match_status.startswith("❌"): row_status = match_status
    elif t("未找到") in best_p: row_status = "❌ " + t("系统无此品")
    elif not qty_ok: row_status = "❌ " + t("箱数不符")
    elif not amt_ok: row_status = "❌ " + t("金额不符")
        
    cust_check = "✅"
    if sys_customer_name != t("未锁定"):
         if ("贸易" in doc_cust or "门市" in doc_cust) and "ALI-" in sys_customer_name:
             cust_check = "✅ (挂靠)"
         else:
             _, c_score = process.extractOne(doc_cust, [sys_customer_name])
             if c_score < 40: cust_check = "⚠️ " + t("名字差异")

    # 返回结果字典 (Key用中文，方便后续df直接展示，或者可以统一翻译Key)
    # 为了兼容以前的逻辑，Key保持原样，仅翻译Value
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
def process_upload(file_obj, db_conf):
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

# ================= 6. 模块入口 =================
def show(st, db_conf):
    st.markdown(f"#### 🌍 {t('单据核对系统')}")

    if 'chk_raw_data' not in st.session_state:
        st.session_state['chk_raw_data'] = pd.DataFrame()
    if 'chk_audit_results' not in st.session_state:
        st.session_state['chk_audit_results'] = pd.DataFrame()

    c1, c2 = st.columns([4, 1])
    with c1:
        st.info(t("请上传手写单据图片 (JPG/PNG)，系统将自动识别并与数据库比对。"))
    with c2:
        if st.button("🗑️ " + t("清空列表")):
            st.session_state['chk_raw_data'] = pd.DataFrame()
            st.session_state['chk_audit_results'] = pd.DataFrame()
            st.rerun()

    uploaded_files = st.file_uploader(t("批量上传图片"), type=['jpg', 'png'], accept_multiple_files=True)

    if uploaded_files:
        processed_files = set()
        if not st.session_state['chk_raw_data'].empty:
            processed_files = set(st.session_state['chk_raw_data']['文件名'].unique())
        
        new_rows = []
        new_cnt = 0
        
        for f in uploaded_files:
            if f.name not in processed_files:
                new_cnt += 1
                with st.spinner(f"{t('正在识别')}: {f.name}..."):
                    rows = process_upload(f, db_conf)
                    new_rows.extend(rows)
        
        if new_rows:
            new_df = pd.DataFrame(new_rows)
            st.session_state['chk_raw_data'] = pd.concat([st.session_state['chk_raw_data'], new_df], ignore_index=True)
            st.success(f"{t('成功识别')} {new_cnt} {t('张新单据')}！")

    # 显示编辑区
    if not st.session_state['chk_raw_data'].empty:
        st.subheader(f"📝 {t('识别结果 (请核对并修正)')}")
        
        editable_cols = ["文件名", "No.", "手写日期", "手写客户", "手写产品", "手写箱数", "手写金额"]
        
        # 显示可编辑表格
        edited_df = st.data_editor(
            st.session_state['chk_raw_data'][editable_cols], 
            num_rows="dynamic",
            use_container_width=True,
            key="chk_editor",
            column_config={
                "文件名": st.column_config.TextColumn(label=t("文件名")),
                "No.": st.column_config.TextColumn(label=t("单据编号")),
                "手写日期": st.column_config.TextColumn(label=t("日期")),
                "手写客户": st.column_config.TextColumn(label=t("客户")),
                "手写产品": st.column_config.TextColumn(label=t("产品")),
                "手写箱数": st.column_config.NumberColumn(label=t("箱数")),
                "手写金额": st.column_config.NumberColumn(label=t("金额")),
            }
        )
        
        # 比对按钮
        if st.button("🔄 " + t("开始与数据库比对"), type="primary"):
            results = []
            prog_bar = st.progress(0)
            
            for i, (index, row) in enumerate(edited_df.iterrows()):
                progress_val = min((i + 1) / len(edited_df), 1.0)
                prog_bar.progress(progress_val)
                
                audit_res = perform_audit(row, db_conf)
                combined_row = {**row.to_dict(), **audit_res}
                results.append(combined_row)
            
            prog_bar.empty()
            st.session_state['chk_audit_results'] = pd.DataFrame(results)
            st.success("✅ " + t("比对完成"))

        # 显示最终结果
        if not st.session_state['chk_audit_results'].empty:
            st.markdown(f"### 📊 {t('最终核对报告')}")
            final_df = st.session_state['chk_audit_results']
            
            def color_row(val):
                s = str(val)
                if '❌' in s: return 'color: #d32f2f; font-weight: bold'
                if '✅' in s: return 'color: #2e7d32'
                if '⚠️' in s: return 'color: #ef6c00; font-weight: bold'
                return ''
            
            try:
                st.dataframe(
                    final_df.style.map(color_row, subset=['最终状态', '金额核对', '客户核对']),
                    use_container_width=True
                )
            except:
                st.dataframe(final_df, use_container_width=True)
            
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                final_df.to_excel(writer, index=False)
            st.download_button("📥 " + t("下载 Excel 报表"), out.getvalue(), f"Audit_Report_{int(time.time())}.xlsx")