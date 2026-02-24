# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st
import datetime
# 引入翻译
from modules.languages import t

def run_query(conn, sql):
    try:
        return pd.read_sql(sql, conn)
    except Exception as e:
        st.error(f"SQL执行出错: {e}")
        return pd.DataFrame()

def clean_zero(val):
    if pd.isna(val) or val == 0 or val == 0.0: return None
    return val

# ==========================================
# 弹出框：明细详情穿透
# ==========================================
@st.dialog("📄 单据详情 (Voucher Details)", width="large")
def show_voucher_details(row_dict, conn_erp):
    vch_code = str(row_dict.get('VchCode'))
    vch_type_name = str(row_dict.get('类型', t('单据详情')))
    
    # --- 渲染拟真表头 ---
    st.markdown(f"<h3 style='text-align: center;'>{vch_type_name}</h3>", unsafe_allow_html=True)
    st.caption(f"**VchCode:** `{vch_code}`")
    
    hc1, hc2, hc3, hc4 = st.columns(4)
    hc1.markdown(f"**{t('单据编号')}**<br>{row_dict.get('单据编号', '')}", unsafe_allow_html=True)
    hc2.markdown(f"**{t('日期')}**<br>{row_dict.get('日期', '')}", unsafe_allow_html=True)
    hc3.markdown(f"**{t('往来单位')}**<br>{row_dict.get('往来单位', '')}", unsafe_allow_html=True)
    hc4.markdown(f"**{t('经手人')}**<br>{row_dict.get('经手人', '')}", unsafe_allow_html=True)
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
            st.info(t("未找到商品明细。"))
        else:
            detail_df = pd.DataFrame(detail_records)
            
            detail_columns_map = {
                'ProductName': t('商品名称'),
                'Quantity': t('数量'),
                'UnitPrice': t('单价'),
                'TotalAmount': t('金额'),
                'LineComment': t('备注')
            }
            display_detail_df = detail_df.rename(columns=detail_columns_map).fillna('')
            
            display_detail_df[t('数量')] = pd.to_numeric(display_detail_df[t('数量')], errors='coerce').abs()
            display_detail_df[t('金额')] = pd.to_numeric(display_detail_df[t('金额')], errors='coerce').abs()
            
            st.dataframe(
                display_detail_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    t('数量'): st.column_config.NumberColumn(format="%.2f"),
                    t('单价'): st.column_config.NumberColumn(format="%.2f"),
                    t('金额'): st.column_config.NumberColumn(format="%.2f")
                }
            )
            
    except Exception as e:
        st.error(f"{t('明细查询出错')}: {str(e)}")

    st.divider()
    fc1, fc2 = st.columns([3, 1])
    fc1.markdown(f"**{t('摘要')}**<br>{row_dict.get('摘要/手工单', '')}", unsafe_allow_html=True)
    
    safe_total = pd.to_numeric(row_dict.get('金额', 0), errors='coerce')
    if pd.isna(safe_total): safe_total = 0
    fc2.markdown(f"**{t('单据总金额')}**<br><span style='color:red; font-size:1.1em;'>{safe_total:,.2f}</span>", unsafe_allow_html=True)

# ==========================================
# 主视图展示逻辑
# ==========================================
def show(st, conn):
    # 【全局打勾状态记忆】
    if 'io_verified_docs' not in st.session_state:
        st.session_state['io_verified_docs'] = set()
    if 'io_docs_df' not in st.session_state:
        st.session_state['io_docs_df'] = pd.DataFrame()

    st.markdown(f"##### 🚚 {t('出入库明细查询')}")

    c1, c2, c3, c4, c5 = st.columns([1.2, 1.2, 1.5, 2, 1])
    
    with c1:
        start_date = st.date_input(t("开始日期"), datetime.date.today(), key="io_start")
    with c2:
        end_date = st.date_input(t("结束日期"), datetime.date.today(), key="io_end")
    
    with c3:
        biz_map = {
            "全部业务": [], "采购入库": [34, 6], "销售出库": [11, 45],
            "仓库调拨": [21, 48], "其他出入库": [46, 47], "报损报溢": [9, 14]
        }
        biz_options = list(biz_map.keys())
        selected_biz_label = st.selectbox(t("业务类型"), biz_options, format_func=lambda x: t(x), key="io_biz")
        selected_types = biz_map[selected_biz_label]
        
    with c4:
        search_txt = st.text_input(t("搜索"), placeholder=t("搜索 (名称/编号)") + "...", key="io_search")

    with c5:
        st.write("") 
        st.write("")
        if st.button(t("查询"), type="primary", key="io_btn"):
            st.session_state['io_refresh'] = True
            if 'selected_sku' in st.session_state:
                del st.session_state['selected_sku']

    date_start = start_date.strftime('%Y-%m-%d 00:00:00')
    date_end = end_date.strftime('%Y-%m-%d 23:59:59')

    if selected_types:
        type_str = ",".join(map(str, selected_types))
        sql_type_filter = f"AND d.VchType IN ({type_str})"
    else:
        sql_type_filter = "AND d.VchType IN (34,6, 11,45, 21,48, 46,47, 9,14)"

    col_left, col_right = st.columns([2, 1])

    # ==========================================
    # 右表：SKU 汇总 
    # ==========================================
    with col_right:
        sql_sku = f"""
        SELECT 
            MAX(CAST(p.FullName AS NVARCHAR(200))) AS [商品名称],
            MAX(CAST(p.UserCode AS VARCHAR(50))) AS [编号],
            SUM(CASE WHEN t.Qty > 0 THEN t.Qty ELSE 0 END) AS [入库数],
            SUM(CASE WHEN t.Qty < 0 THEN ABS(t.Qty) ELSE 0 END) AS [出库数],
            MAX(CAST(p.Unit1 AS NVARCHAR(20))) AS [单位]
        FROM (
            SELECT PtypeId, ISNULL(Qty, 0) AS Qty FROM DlySale s JOIN Dlyndx d ON s.VchCode=d.VchCode WHERE d.Date BETWEEN '{date_start}' AND '{date_end}' AND d.Draft=2 {sql_type_filter}
            UNION ALL
            SELECT PtypeId, ISNULL(Qty, 0) AS Qty FROM DlyBuy s JOIN Dlyndx d ON s.VchCode=d.VchCode WHERE d.Date BETWEEN '{date_start}' AND '{date_end}' AND d.Draft=2 {sql_type_filter}
            UNION ALL
            SELECT PtypeId, ISNULL(Qty, 0) AS Qty FROM dlyother s JOIN Dlyndx d ON s.VchCode=d.VchCode WHERE d.Date BETWEEN '{date_start}' AND '{date_end}' AND d.Draft=2 {sql_type_filter}
            UNION ALL
            SELECT PtypeId, ISNULL(Qty, 0) AS Qty FROM DlySC s JOIN Dlyndx d ON s.VchCode=d.VchCode WHERE d.Date BETWEEN '{date_start}' AND '{date_end}' AND d.Draft=2 {sql_type_filter}
        ) t
        LEFT JOIN Ptype p ON t.PtypeId = p.typeId
        GROUP BY t.PtypeId
        HAVING SUM(ABS(t.Qty)) > 0
        ORDER BY SUM(ABS(t.Qty)) DESC
        """
        
        df_sku = run_query(conn, sql_sku)
        selected_code = None 
        selected_name = ""

        if not df_sku.empty:
            if search_txt:
                mask = df_sku['商品名称'].astype(str).str.contains(search_txt, case=False) | \
                       df_sku['编号'].astype(str).str.contains(search_txt, case=False)
                df_sku = df_sku[mask]

            if not df_sku.empty:
                df_sku['入库数'] = df_sku['入库数'].apply(clean_zero)
                df_sku['出库数'] = df_sku['出库数'].apply(clean_zero)

                st.markdown(f"**{t('SKU 汇总')}**")

                event_right = st.dataframe(
                    df_sku,
                    use_container_width=True,
                    height=600,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    column_config={
                        "商品名称": st.column_config.TextColumn(label=t("商品名称"), width="medium"),
                        "编号": st.column_config.TextColumn(label=t("存货编号"), width="small"),
                        "入库数": st.column_config.NumberColumn(label=t("入库数量"), format="%d"),
                        "出库数": st.column_config.NumberColumn(label=t("出库数量"), format="%d"),
                        "单位": st.column_config.TextColumn(label=t("单位"), width="small"),
                    }
                )
                
                if event_right and event_right.selection and event_right.selection.rows:
                    idx = event_right.selection.rows[0]
                    selected_row = df_sku.iloc[idx]
                    selected_code = selected_row['编号']
                    selected_name = selected_row['商品名称']
            else:
                st.info(t("无数据。"))
        else:
            st.info(t("无数据。"))

    # ==========================================
    # 左表：单据流水
    # ==========================================
    with col_left:
        extra_cols = ""
        extra_joins = ""
        left_title = t("单据流水")

        if selected_code:
            left_title = f"{t('单据流水')} (Filter: {selected_name})"
            extra_cols = ", ISNULL(sku.SKU_Qty, 0) AS [数量], ISNULL(sku.SKU_Carton, 0) AS [箱数]"
            extra_joins = f"""
            INNER JOIN (
                SELECT VchCode, SUM(ABS(Qty)) as SKU_Qty,
                       SUM(CASE WHEN ISNULL(p.UnitRate1, 0) > 0 THEN ABS(Qty) / p.UnitRate1 ELSE 0 END) AS SKU_Carton
                FROM (
                    SELECT VchCode, Qty, PtypeId FROM DlySale WHERE 1=1
                    UNION ALL SELECT VchCode, Qty, PtypeId FROM DlyBuy WHERE 1=1
                    UNION ALL SELECT VchCode, Qty, PtypeId FROM dlyother WHERE 1=1
                    UNION ALL SELECT VchCode, Qty, PtypeId FROM DlySC WHERE 1=1
                ) s 
                JOIN Ptype p ON s.PtypeId=p.TypeId 
                WHERE p.UserCode='{selected_code}'
                GROUP BY VchCode
            ) sku ON d.VchCode = sku.VchCode
            """
        
        # --- 精巧的 UI 布局：左边显示标题，右边显示下拉查看明细框 ---
        title_col, view_col = st.columns([1.5, 1])
        with title_col:
            st.markdown(f"<div style='margin-top:20px'><b>{left_title}</b></div>", unsafe_allow_html=True)
            st.caption("💡 提示：在表格中打勾自动保存进度；右侧选择单号查看明细。")

        sql_docs = f"""
        SELECT 
            d.vchcode AS VchCode,
            d.Number AS [单据编号],
            CONVERT(varchar(10), d.Date, 120) AS [日期],
            d.VchType, 
            CAST(ISNULL(d.Summary, '') AS NVARCHAR(500)) AS [摘要/手工单],
            ABS(ISNULL(d.Total, 0)) AS [金额],
            CAST(e.FullName AS NVARCHAR(100)) AS [经手人],
            CAST(b.FullName AS NVARCHAR(200)) AS [往来单位]
            {extra_cols}
        FROM Dlyndx d
        LEFT JOIN Employee e ON d.EtypeId = e.TypeId
        LEFT JOIN Btype b ON d.BtypeId = b.TypeId
        {extra_joins}
        WHERE d.Date BETWEEN '{date_start}' AND '{date_end}'
          AND d.Draft = 2
          {sql_type_filter}
        ORDER BY d.Date ASC, d.VchCode ASC
        """
        
        df_docs = run_query(conn, sql_docs)
        
        if not df_docs.empty:
            type_dict = {
                34: t('采购入库'), 6: t('采购退货'),
                11: t('销售出库'), 45: t('销售退货'),
                21: t('仓库调拨'), 48: t('仓库调拨'),
                9: t('报损'), 14: t('报溢'),
                46: t('其他入库'), 47: t('其他出库')
            }
            df_docs['类型'] = df_docs['VchType'].map(type_dict).fillna(t('其他'))
            
            if not selected_code and search_txt:
                mask = df_docs['单据编号'].astype(str).str.contains(search_txt, case=False) | \
                       df_docs['摘要/手工单'].astype(str).str.contains(search_txt, case=False) | \
                       df_docs['往来单位'].astype(str).str.contains(search_txt, case=False)
                df_docs = df_docs[mask]

            df_docs['金额'] = df_docs['金额'].apply(clean_zero)
            
            # 🔥 核心修复1：单据编号转为纯字符串，Streamlit 会自动将其 100% 靠左对齐，不裁切！
            df_docs['单据编号'] = df_docs['单据编号'].astype(str)
            
            # 匹配打勾状态
            df_docs['核对'] = df_docs['VchCode'].astype(str).apply(lambda x: True if x in st.session_state['io_verified_docs'] else False)

            cols_show = ["核对", "单据编号", "日期", "类型", "摘要/手工单", "金额", "经手人", "往来单位"]
            
            if selected_code:
                cols_show.insert(5, "数量")
                cols_show.insert(6, "箱数")
                df_docs['数量'] = df_docs['数量'].apply(clean_zero)
                df_docs['箱数'] = df_docs['箱数'].apply(clean_zero)
            
            # 在右上角放一个极简的下拉框用来查看明细，取代冲突的点击行
            with view_col:
                vch_list = df_docs['单据编号'].tolist()
                detail_vch = st.selectbox(
                    "📄", vch_list, index=None, 
                    placeholder=t("下拉查看单据明细..."), label_visibility="collapsed"
                )
                if detail_vch:
                    vch_row = df_docs[df_docs['单据编号'] == detail_vch].iloc[0].to_dict()
                    show_voucher_details(vch_row, conn)

            col_cfg = {
                "VchCode": None, 
                "核对": st.column_config.CheckboxColumn(label=t("核对")),
                "单据编号": st.column_config.TextColumn(label=t("单据编号")), # 不设width，纯字符串自动完美靠左
                "日期": st.column_config.TextColumn(label=t("日期"), width="small"),
                "类型": st.column_config.TextColumn(label=t("业务类型"), width="small"),
                "摘要/手工单": st.column_config.TextColumn(label=t("摘要"), width="medium"),
                "金额": st.column_config.NumberColumn(label=t("总价"), format="%.2f"),
                "数量": st.column_config.NumberColumn(label=t("该SKU数量"), format="%.1f"),
                "箱数": st.column_config.NumberColumn(label=t("该SKU箱数"), format="%.1f"),
                "经手人": st.column_config.TextColumn(label=t("经手人"), width="small"),
                "往来单位": st.column_config.TextColumn(label=t("往来单位"), width="medium"),
            }

            # 存储当前的 df 用于后续的 diff 比对
            st.session_state['io_docs_df'] = df_docs
            display_df = df_docs[cols_show + ["VchCode"]]

            # 🔥 核心修复2：使用 data_editor 并完全去掉了 on_select/selection_mode 冲突
            edited_res = st.data_editor(
                display_df,
                use_container_width=True,
                height=600,
                hide_index=True,
                disabled=[c for c in cols_show if c != "核对"] + ["VchCode"], # 只有核对可点
                key="io_doc_editor",
                column_config=col_cfg
            )
            
            # 🔥 核心修复3：完美复刻你的参考代码，利用 equals 进行差异找点，强制刷新
            if not edited_res['核对'].equals(display_df['核对']):
                diff_mask = edited_res['核对'] != display_df['核对']
                for idx in edited_res.index[diff_mask]:
                    v_code = str(display_df.loc[idx, 'VchCode'])
                    new_val = bool(edited_res.loc[idx, '核对'])
                    
                    if new_val:
                        st.session_state['io_verified_docs'].add(v_code)
                    else:
                        st.session_state['io_verified_docs'].discard(v_code)
                st.rerun()
                
        else:
            st.info(t("无数据。"))