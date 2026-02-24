# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from modules import languages

T = languages.t

# ==========================================
# 1. 弹出框：拟真单据详情渲染逻辑 (@st.dialog)
# ==========================================
@st.dialog("📄 单据详情 (Voucher Details)", width="large")
def show_voucher_details(row_dict, conn_erp):
    vch_code = row_dict['VchCode']
    vch_type_name = str(row_dict.get('单据类型', ''))
    
    # --- 渲染拟真表头 ---
    st.markdown(f"<h3 style='text-align: center;'>{vch_type_name}</h3>", unsafe_allow_html=True)
    st.caption(f"**VchCode:** `{vch_code}`")
    
    hc1, hc2, hc3, hc4 = st.columns(4)
    hc1.markdown(f"**{T('单据编号')}**<br>{row_dict.get('单据编号', '')}", unsafe_allow_html=True)
    hc2.markdown(f"**{T('日期')}**<br>{row_dict.get('日期', '')}", unsafe_allow_html=True)
    hc3.markdown(f"**{T('往来单位')}**<br>{row_dict.get('往来单位', '')}", unsafe_allow_html=True)
    hc4.markdown(f"**{T('出库仓库')}**<br>{row_dict.get('出库仓库', '')}", unsafe_allow_html=True)
    st.divider()
    
    # --- 提取并渲染明细 ---
    detail_query = """
    SELECT 
        p.FullName AS ProductName,
        t.Qty AS Quantity,
        t.price AS UnitPrice,
        t.total AS TotalAmount,
        t.comment AS LineComment
    FROM (
        SELECT PtypeId, Qty, price, total, comment FROM Dlysale WHERE Vchcode = %s
        UNION ALL
        SELECT PtypeId, Qty, price, total, comment FROM Dlybuy WHERE Vchcode = %s
        UNION ALL
        SELECT PtypeId, Qty, price, total, comment FROM dlyother WHERE Vchcode = %s
        UNION ALL
        SELECT PtypeId, Qty, price, total, comment FROM DlySC WHERE Vchcode = %s
    ) t
    LEFT JOIN Ptype p ON t.PtypeId = p.typeId
    """
    
    try:
        with conn_erp.cursor(as_dict=True) as cursor:
            cursor.execute(detail_query, (vch_code, vch_code, vch_code, vch_code))
            detail_records = cursor.fetchall()
            
        if not detail_records:
            st.info(T("未找到商品明细（可能是纯财务/费用类单据，或生产明细缺少相关字段）。"))
        else:
            detail_df = pd.DataFrame(detail_records)
            
            detail_columns_map = {
                'ProductName': '商品名称',
                'Quantity': '数量',
                'UnitPrice': '单价',
                'TotalAmount': '金额',
                'LineComment': '备注'
            }
            display_detail_df = detail_df.rename(columns=detail_columns_map).fillna('')
            
            if any(keyword in vch_type_name for keyword in ['销售', '出库', '完工', '生产']):
                display_detail_df['数量'] = pd.to_numeric(display_detail_df['数量'], errors='coerce').abs()
                display_detail_df['金额'] = pd.to_numeric(display_detail_df['金额'], errors='coerce').abs()
            
            st.dataframe(
                display_detail_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "数量": st.column_config.NumberColumn(format="%.2f"),
                    "单价": st.column_config.NumberColumn(format="%.2f"),
                    "金额": st.column_config.NumberColumn(format="%.2f")
                }
            )
            
    except Exception as e:
        st.error(f"明细查询出错: {str(e)}")

    # --- 渲染拟真表尾 ---
    st.divider()
    fc1, fc2, fc3, fc4 = st.columns(4)
    fc1.markdown(f"**{T('制单人')}**<br>{row_dict.get('制单人', '')}", unsafe_allow_html=True)
    fc2.markdown(f"**{T('经办人')}**<br>{row_dict.get('经办人', '')}", unsafe_allow_html=True)
    fc3.markdown(f"**{T('过账时间')}**<br>{row_dict.get('过账时间', '')}", unsafe_allow_html=True)
    
    safe_total = pd.to_numeric(row_dict.get('金额', 0), errors='coerce')
    if pd.isna(safe_total): safe_total = 0
    fc4.markdown(f"**{T('单据总金额')}**<br><span style='color:red; font-size:1.1em;'>{safe_total:,.2f}</span>", unsafe_allow_html=True)


# ==========================================
# 2. 状态映射函数
# ==========================================
def format_red_status(row_dict):
    red_word = str(row_dict.get('RedWord', '')).strip().upper()
    red_old = str(row_dict.get('RedOld', '')).strip().upper()
    
    # 哪怕传入的是 None 或 'NONE'，这里的逻辑依然会非常安全地兜底走到 '否'
    if red_word == 'F' and red_old == 'F': return '否'
    if red_word == 'T' or red_old == 'T': return '是'
    if red_word == 'F': return '否'
    
    # 对于生产表传进来的 NULL，上面都不命中，走到这里。
    # 为了避免生产表全部变成'是'，我们需要加一个针对空值的判定
    if not red_word or red_word == 'NONE' or red_word == 'NAN': return '否'
    
    return '是'

def format_draft_status(draft_code):
    status_map = {1: '草稿', 2: '过账单据', 4: '待审核'}
    return status_map.get(draft_code, f'未知({draft_code})')


# ==========================================
# 3. 主界面核心逻辑
# ==========================================
def show(st, conn_erp):
    st.markdown(f"#### 📜 {T('经营历程')} (Business History)")
    st.caption("💡 提示：**点击表格中的任意一行**，即可自动弹出包含表头/表尾的单据详情。")
    
    filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 2])
    with filter_col1:
        start_date = st.date_input(T("开始日期"), date.today())
    with filter_col2:
        end_date = st.date_input(T("结束日期"), date.today())
    with filter_col3:
        search_keyword = st.text_input(T("模糊搜索 (支持空格分隔多条件，如: 采购 张三)"), "")
        
    if start_date > end_date:
        st.warning(T("开始日期不能晚于结束日期！"))
        return

    # --- 核心 SQL (修复红字红冲字段缺失) ---
    query_sql = """
    SELECT 
        d.vchcode AS VchCode, d.date AS VchDate, d.number AS VchNumber, vt.fullname AS VchTypeName,
        d.summary AS Summary, 
        b.fullname AS BTypeFullName, 
        e.fullname AS EmployeeName,
        ISNULL(s1.fullname, ws.fullname) AS OutStockName, 
        s2.fullname AS InStockName, d.inputno AS InputUser,
        d.total AS TotalAmount, a.fullname AS AccountSubject, d.gatheringdate AS GatheringDate,
        dp.fullname AS DepartmentName, d.savetime AS SaveTime, d.modifydate AS ModifyTime,
        d.auditdate AS AuditTime, d.redword AS RedWord, d.redold AS RedOld, d.draft AS DraftStatus
    FROM (
        SELECT vchcode, date, number, vchtype, summary, 
               btypeid, NULL AS wtypeid, 
               etypeid, ktypeid, ktypeid2, 
               inputno, total, ifcheck, gatheringdate, 
               projectid, 
               savetime, modifydate, auditdate, redword, redold, draft 
        FROM Dlyndx WHERE date >= %s AND date <= %s
        UNION ALL
        SELECT vchcode, date, number, vchtype, summary, 
               NULL AS btypeid, wtypeid, 
               etypeid, NULL AS ktypeid, NULL AS ktypeid2, 
               inputno, NULL AS total,   
               NULL AS ifcheck, NULL AS gatheringdate, 
               NULL AS projectid, 
               savetime, NULL AS modifydate, auditdate, 
               NULL AS redword, NULL AS redold, -- 【核心修复】：dlyndxsc 表无红字概念，使用 NULL 占位
               draft 
        FROM dlyndxsc WHERE date >= %s AND date <= %s
    ) d
    LEFT JOIN vchtype vt ON d.vchtype = vt.vchtype
    LEFT JOIN btype b ON d.btypeid = b.typeid
    LEFT JOIN WorkShop ws ON d.wtypeid = ws.typeid 
    LEFT JOIN employee e ON d.etypeid = e.typeid
    LEFT JOIN stock s1 ON d.ktypeid = s1.typeid
    LEFT JOIN stock s2 ON d.ktypeid2 = s2.typeid
    LEFT JOIN atypecw a ON d.ifcheck = a.typeid
    LEFT JOIN Department dp ON d.projectid = dp.typeid
    ORDER BY d.date DESC, d.savetime DESC
    """
    
    try:
        with conn_erp.cursor(as_dict=True) as cursor:
            str_start = start_date.strftime('%Y-%m-%d')
            str_end = end_date.strftime('%Y-%m-%d')
            cursor.execute(query_sql, (str_start, str_end, str_start, str_end))
            history_records = cursor.fetchall()
            
    except Exception as e:
        st.error(f"{T('查询失败')}: {str(e)}")
        return

    if not history_records:
        st.info(T("所选日期范围内没有单据记录。"))
        return

    history_df = pd.DataFrame(history_records)

    # --- 字段加工与格式化 ---
    history_df['红字'] = history_df.apply(format_red_status, axis=1)
    history_df['状态'] = history_df['DraftStatus'].apply(format_draft_status)
    
    def apply_abs_total(row_dict):
        amt = pd.to_numeric(row_dict['TotalAmount'], errors='coerce')
        if pd.notna(amt) and any(kw in str(row_dict.get('VchTypeName', '')) for kw in ['销售', '出库', '完工', '生产']):
            return abs(amt)
        return amt
        
    history_df['TotalAmount'] = history_df.apply(apply_abs_total, axis=1)
    
    transfer_mask = history_df['VchTypeName'].astype(str).str.contains('调拨单', na=False)
    if transfer_mask.any():
        temp_stock = history_df.loc[transfer_mask, 'OutStockName']
        history_df.loc[transfer_mask, 'OutStockName'] = history_df.loc[transfer_mask, 'InStockName']
        history_df.loc[transfer_mask, 'InStockName'] = temp_stock
    
    datetime_columns = ['VchDate', 'GatheringDate', 'SaveTime', 'ModifyTime', 'AuditTime']
    for col in datetime_columns:
        if col in history_df.columns:
            history_df[col] = pd.to_datetime(history_df[col]).dt.strftime('%Y-%m-%d %H:%M:%S').fillna('')
            if col in ['VchDate', 'GatheringDate']:
                history_df[col] = history_df[col].str[:10]

    display_columns_mapping = {
        'VchCode': 'VchCode', 'VchDate': '日期', 'VchNumber': '单据编号',
        'VchTypeName': '单据类型', 'Summary': '摘要', 
        'BTypeFullName': '往来单位', 
        'EmployeeName': '经办人', 'OutStockName': '出库仓库', 'InStockName': '入库仓库',
        'InputUser': '制单人', 'TotalAmount': '金额', 'AccountSubject': '会计科目',
        'GatheringDate': '收付款日期', 'DepartmentName': '部门', 'SaveTime': '保存时间',
        'ModifyTime': '修改时间', 'AuditTime': '过账时间', '红字': '红字', '状态': '状态'
    }
    
    final_display_df = history_df[list(display_columns_mapping.keys())].rename(columns=display_columns_mapping).fillna('')

    if search_keyword:
        search_terms = [term.strip().lower() for term in search_keyword.split() if term.strip()]
        for term in search_terms:
            match_mask = final_display_df.astype(str).apply(lambda row_val: row_val.str.lower().str.contains(term).any(), axis=1)
            final_display_df = final_display_df[match_mask]

    selection_event = st.dataframe(
        final_display_df,
        use_container_width=True,
        height=600,
        selection_mode="single-row",
        on_select="rerun",
        column_config={"金额": st.column_config.NumberColumn(format="%.2f")}
    )
    
    if len(selection_event.selection.rows) > 0:
        selected_index = selection_event.selection.rows[0]
        selected_row_dict = final_display_df.iloc[selected_index].to_dict()
        show_voucher_details(selected_row_dict, conn_erp)
    
    valid_amounts = pd.to_numeric(final_display_df['金额'].replace('', 0), errors='coerce').fillna(0)
    st.caption(f"**{T('总计记录数')}**: {len(final_display_df)} | **{T('本页总金额')}**: {valid_amounts.sum():,.2f}")