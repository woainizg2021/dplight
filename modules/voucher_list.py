# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from modules import languages

T = languages.t

def get_safe_field(available_cols, candidates):
    """【核心黑科技】：从数据库真实列中智能探测字段，彻底阻绝 SQL 报错"""
    for c in candidates:
        if c.lower() in available_cols:
            return c
    return 'NULL'

# ==========================================
# 1. 弹出框：拟真凭证详情渲染逻辑 (@st.dialog)
# ==========================================
@st.dialog("🧾 记账凭证 (Accounting Voucher)", width="large")
def show_voucher_details(row_dict, conn_erp):
    vch_code = row_dict['VchCode']
    
    # --- 渲染拟真表头 ---
    st.markdown("<h3 style='text-align: center;'>记账凭证</h3>", unsafe_allow_html=True)
    st.caption(f"**VchCode:** `{vch_code}`")
    
    hc1, hc2, hc3, hc4 = st.columns(4)
    hc1.markdown(f"**{T('凭证编号')}**<br>{row_dict.get('凭证编号', '')}", unsafe_allow_html=True)
    hc2.markdown(f"**{T('凭证日期')}**<br>{row_dict.get('日期', '')}", unsafe_allow_html=True)
    hc3.markdown(f"**{T('凭证摘要')}**<br>{row_dict.get('摘要', '')}", unsafe_allow_html=True)
    hc4.markdown(f"**{T('制单人')}**<br>{row_dict.get('制单人', '')}", unsafe_allow_html=True)
    st.divider()
    
    # --- 全面检查：动态读取明细表 t_cw_dly 结构 ---
    try:
        with conn_erp.cursor() as cursor:
            cursor.execute("SELECT name FROM sys.columns WHERE object_id = OBJECT_ID('t_cw_dly')")
            dly_cols = [row[0].lower() for row in cursor.fetchall()]
    except Exception as e:
        st.error(f"无法读取明细表结构: {e}")
        return

    if not dly_cols:
        st.warning(T("读取不到明细表结构，请确认底层是否存在 t_cw_dly。"))
        return

    # 智能字段匹配 (优先使用财贸系惯用词，向下兼容)
    f_dly_summary = get_safe_field(dly_cols, ['summary', 'zy', 'memo'])
    f_dly_atypeid = get_safe_field(dly_cols, ['atypeid', 'accountid', 'kmid'])
    f_dly_btypeid = get_safe_field(dly_cols, ['btypeid', 'unitid', 'wlid'])
    f_dly_projectid = get_safe_field(dly_cols, ['projectid', 'deptid', 'bmid'])
    f_debit = get_safe_field(dly_cols, ['jf', 'debit', 'jftotal', 'debitamount'])
    f_credit = get_safe_field(dly_cols, ['df', 'credit', 'dftotal', 'creditamount'])
    f_rowno = get_safe_field(dly_cols, ['rowno', 'entryno', 'id'])

    # 动态组装 JOIN 语句
    join_atype = f"LEFT JOIN atypecw a ON t.{f_dly_atypeid} = a.typeid" if f_dly_atypeid != 'NULL' else ""
    join_btype = f"LEFT JOIN btype b ON t.{f_dly_btypeid} = b.typeid" if f_dly_btypeid != 'NULL' else ""
    join_dept = f"LEFT JOIN Department dp ON t.{f_dly_projectid} = dp.typeid" if f_dly_projectid != 'NULL' else ""

    # 动态组装 SELECT 语句
    detail_query = f"""
    SELECT 
        {'t.' + f_dly_summary if f_dly_summary != 'NULL' else 'NULL'} AS LineSummary,
        {'a.fullname' if f_dly_atypeid != 'NULL' else 'NULL'} AS AccountSubject,
        {'b.fullname' if f_dly_btypeid != 'NULL' else 'NULL'} AS BTypeFullName,
        {'dp.fullname' if f_dly_projectid != 'NULL' else 'NULL'} AS DepartmentName,
        {'t.' + f_debit if f_debit != 'NULL' else '0'} AS DebitAmount,   
        {'t.' + f_credit if f_credit != 'NULL' else '0'} AS CreditAmount  
    FROM t_cw_dly t
    {join_atype}
    {join_btype}
    {join_dept}
    WHERE t.vchcode = %s
    ORDER BY {'t.' + f_rowno if f_rowno != 'NULL' else '(SELECT NULL)'} ASC
    """
    
    try:
        with conn_erp.cursor(as_dict=True) as cursor:
            cursor.execute(detail_query, (vch_code,))
            detail_records = cursor.fetchall()
            
        if not detail_records:
            st.info(T("未找到该凭证的分录明细。"))
        else:
            detail_df = pd.DataFrame(detail_records)
            
            detail_columns_map = {
                'LineSummary': '分录摘要',
                'AccountSubject': '会计科目',
                'BTypeFullName': '往来单位',
                'DepartmentName': '核算部门',
                'DebitAmount': '借方金额',
                'CreditAmount': '贷方金额'
            }
            display_detail_df = detail_df.rename(columns=detail_columns_map).fillna('')
            
            st.dataframe(
                display_detail_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "借方金额": st.column_config.NumberColumn(format="%.2f"),
                    "贷方金额": st.column_config.NumberColumn(format="%.2f")
                }
            )
            
            # 底部借贷合计试算平衡校验
            debit_sum = pd.to_numeric(display_detail_df['借方金额'], errors='coerce').fillna(0).sum()
            credit_sum = pd.to_numeric(display_detail_df['贷方金额'], errors='coerce').fillna(0).sum()
            
            balance_color = "green" if abs(debit_sum - credit_sum) < 0.01 else "red"
            balance_text = "试算平衡" if abs(debit_sum - credit_sum) < 0.01 else "借贷不平"
            
            st.caption(f"**{T('合计')}** 👉 借方: `{debit_sum:,.2f}` | 贷方: `{credit_sum:,.2f}` | <span style='color:{balance_color}; font-weight:bold;'>[{balance_text}]</span>", unsafe_allow_html=True)
            
    except Exception as e:
        st.error(f"明细查询出错: {str(e)}")

    # --- 渲染拟真表尾 ---
    st.divider()
    fc1, fc2, fc3, fc4 = st.columns(4)
    fc1.markdown(f"**{T('审核人')}**<br>{row_dict.get('审核人', '')}", unsafe_allow_html=True)
    fc2.markdown(f"**{T('记账人')}**<br>{row_dict.get('记账人', '')}", unsafe_allow_html=True)
    fc3.markdown(f"**{T('保存时间')}**<br>{row_dict.get('保存时间', '')}", unsafe_allow_html=True)
    
    safe_total = pd.to_numeric(row_dict.get('凭证总额', 0), errors='coerce')
    if pd.isna(safe_total): safe_total = 0
    fc4.markdown(f"**{T('凭证总金额')}**<br><span style='color:#1E90FF; font-size:1.1em;'>{safe_total:,.2f}</span>", unsafe_allow_html=True)


# ==========================================
# 2. 主界面核心逻辑
# ==========================================
def show(st, conn_erp):
    st.markdown(f"#### 🏦 {T('凭证列表')} (Voucher List)")
    st.caption("💡 提示：**点击表格中的任意一行**，即可自动弹出详细的会计分录（借贷方明细）。")
    
    filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 2])
    with filter_col1:
        start_date = st.date_input(T("开始日期"), date.today())
    with filter_col2:
        end_date = st.date_input(T("结束日期"), date.today())
    with filter_col3:
        search_keyword = st.text_input(T("模糊搜索 (支持空格分隔多条件，如: 报销 张三)"), "")
        
    if start_date > end_date:
        st.warning(T("开始日期不能晚于结束日期！"))
        return

    # --- 全面检查：动态读取主表 t_cw_dlyndx 结构 ---
    try:
        with conn_erp.cursor() as cursor:
            cursor.execute("SELECT name FROM sys.columns WHERE object_id = OBJECT_ID('t_cw_dlyndx')")
            ndx_cols = [row[0].lower() for row in cursor.fetchall()]
    except Exception as e:
        st.error(f"无法读取主表结构: {e}")
        return

    if not ndx_cols:
        st.warning(T("数据库中不存在 t_cw_dlyndx 表，请确认底层表名。"))
        return

    # 智能映射主表字段 (彻底解决 Invalid column name 报错)
    f_vchnumber = get_safe_field(ndx_cols, ['pznumber', 'vchnumber', 'pznum', 'number', 'vchno'])
    f_summary = get_safe_field(ndx_cols, ['summary', 'zy', 'memo'])
    f_inputno = get_safe_field(ndx_cols, ['inputno', 'maker', 'buid', 'operator'])
    f_auditno = get_safe_field(ndx_cols, ['auditno', 'checker', 'auditor'])
    f_postno = get_safe_field(ndx_cols, ['postno', 'tallyno', 'accno', 'jzno'])
    f_total = get_safe_field(ndx_cols, ['total', 'amount', 'je', 'pztotal'])
    f_savetime = get_safe_field(ndx_cols, ['savetime', 'createdate', 'inputdate'])

    # 动态组装 SQL
    query_sql = f"""
    SELECT 
        d.vchcode AS VchCode, 
        d.date AS VchDate, 
        {'d.' + f_vchnumber if f_vchnumber != 'NULL' else 'NULL'} AS VchNumber, 
        {'d.' + f_summary if f_summary != 'NULL' else 'NULL'} AS Summary, 
        {'d.' + f_inputno if f_inputno != 'NULL' else 'NULL'} AS InputUser, 
        {'d.' + f_auditno if f_auditno != 'NULL' else 'NULL'} AS AuditUser, 
        {'d.' + f_postno if f_postno != 'NULL' else 'NULL'} AS PostUser, 
        {'d.' + f_total if f_total != 'NULL' else '0'} AS TotalAmount, 
        {'d.' + f_savetime if f_savetime != 'NULL' else 'NULL'} AS SaveTime
    FROM t_cw_dlyndx d
    WHERE d.date >= %s AND d.date <= %s
    ORDER BY d.date DESC, {'d.' + f_savetime if f_savetime != 'NULL' else 'd.vchcode'} DESC
    """
    
    try:
        with conn_erp.cursor(as_dict=True) as cursor:
            str_start = start_date.strftime('%Y-%m-%d')
            str_end = end_date.strftime('%Y-%m-%d')
            cursor.execute(query_sql, (str_start, str_end))
            voucher_records = cursor.fetchall()
            
    except Exception as e:
        st.error(f"{T('查询失败')}: {str(e)}")
        return

    if not voucher_records:
        st.info(T("所选日期范围内没有凭证记录。"))
        return

    voucher_df = pd.DataFrame(voucher_records)

    # --- 字段加工与格式化 ---
    datetime_columns = ['VchDate', 'SaveTime']
    for col in datetime_columns:
        if col in voucher_df.columns:
            voucher_df[col] = pd.to_datetime(voucher_df[col]).dt.strftime('%Y-%m-%d %H:%M:%S').fillna('')
            if col == 'VchDate':
                voucher_df[col] = voucher_df[col].str[:10]

    display_columns_mapping = {
        'VchCode': 'VchCode', 
        'VchDate': '日期', 
        'VchNumber': '凭证编号',
        'Summary': '摘要', 
        'InputUser': '制单人', 
        'AuditUser': '审核人', 
        'PostUser': '记账人',
        'TotalAmount': '凭证总额', 
        'SaveTime': '保存时间'
    }
    
    final_display_df = voucher_df[list(display_columns_mapping.keys())].rename(columns=display_columns_mapping).fillna('')

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
        column_config={"凭证总额": st.column_config.NumberColumn(format="%.2f")}
    )
    
    if len(selection_event.selection.rows) > 0:
        selected_index = selection_event.selection.rows[0]
        selected_row_dict = final_display_df.iloc[selected_index].to_dict()
        show_voucher_details(selected_row_dict, conn_erp)
    
    valid_amounts = pd.to_numeric(final_display_df['凭证总额'].replace('', 0), errors='coerce').fillna(0)
    st.caption(f"**{T('总计记录数')}**: {len(final_display_df)} | **{T('本页总金额')}**: {valid_amounts.sum():,.2f}")