# modules/pick_bill_generate.py
import streamlit as st
import pandas as pd
import datetime
from modules import languages

T = languages.t

# ==========================================
# 1. 弹出框：领料单明细渲染逻辑 (@st.dialog)
# ==========================================
@st.dialog("📄 领料单明细 (Voucher Details)", width="large")
def show_voucher_details(row_dict, conn_erp, is_draft=False):
    vch_code = row_dict.get('VchCode')
    vch_type_name = str(row_dict.get('单据类型', '生产领料单'))
    
    st.markdown(f"<h3 style='text-align: center;'>{vch_type_name}</h3>", unsafe_allow_html=True)
    st.caption(f"**VchCode:** `{vch_code}` | **状态:** `{'草稿' if is_draft else '已审核'}`")
    
    hc1, hc2, hc3, hc4 = st.columns(4)
    hc1.markdown(f"**{T('单据编号')}**<br>{row_dict.get('单据编号', '')}", unsafe_allow_html=True)
    hc2.markdown(f"**{T('日期')}**<br>{row_dict.get('日期', '')}", unsafe_allow_html=True)
    hc3.markdown(f"**{T('经手人')}**<br>{row_dict.get('制单人', '')}", unsafe_allow_html=True)
    hc4.markdown(f"**{T('发料仓库')}**<br>{row_dict.get('发料仓库', '')}", unsafe_allow_html=True)
    st.divider()
    
    # 领料单明细查询 (VchType 172)
    if is_draft:
        # 草稿存在 BakDly
        detail_query = """
        SELECT p.FullName AS ProductName, t.Qty AS Quantity, t.price AS UnitPrice, 
               t.total AS TotalAmount, t.comment AS LineComment 
        FROM BakDly t LEFT JOIN Ptype p ON t.PtypeId = p.typeId 
        WHERE t.Vchcode = %s
        """
    else:
        # 已过账存在 DlySC (UsedType=2 为材料)
        detail_query = """
        SELECT p.FullName AS ProductName, t.Qty AS Quantity, t.price AS UnitPrice, 
               t.total AS TotalAmount, t.comment AS LineComment 
        FROM DlySC t LEFT JOIN Ptype p ON t.PtypeId = p.typeId 
        WHERE t.Vchcode = %s AND t.Usedtype = 2
        """
    
    try:
        with conn_erp.cursor(as_dict=True) as cursor:
            cursor.execute(detail_query, (vch_code,))
            detail_records = cursor.fetchall()
            
        if not detail_records:
            st.info(T("未找到商品明细。"))
        else:
            display_table = pd.DataFrame(detail_records).rename(columns={
                'ProductName': '材料名称', 'Quantity': '数量', 'UnitPrice': '单价', 
                'TotalAmount': '金额', 'LineComment': '备注'
            }).fillna('')
            st.dataframe(display_table, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"明细查询出错: {str(e)}")

    st.divider()
    st.markdown(f"**摘要:** {row_dict.get('摘要', '')}")

# ==========================================
# 2. 弹出框：选单引入 (@st.dialog)
# ==========================================
@st.dialog("📥 选单 : 引入生产任务单", width="large")
def select_manufacture_order_dialog(conn_erp, mats_dicts):
    st.markdown("##### 🔍 查询本月未完成任务单")
    today = datetime.date.today()
    first_day = today.replace(day=1)
    
    col_q1, col_q2, col_q3 = st.columns([1, 1, 2])
    search_start = col_q1.date_input("开始日期", first_day)
    search_end = col_q2.date_input("结束日期", today)
    search_kw = col_q3.text_input("任务单号 (搜索)")

    try:
        with conn_erp.cursor(as_dict=True) as cursor:
            sql = """
            SELECT d.vchcode AS VchCode, d.Date AS BillDate, d.Number AS BillNumber,
                   w.FullName AS Workshop, e.FullName AS Maker, d.Summary AS SummaryInfo
            FROM dlyndxsc d
            LEFT JOIN WorkShop w ON d.WtypeID = w.typeId
            LEFT JOIN Employee e ON d.EtypeID = e.typeId
            WHERE d.UserOver = 0 AND d.draft = 2 AND d.Vchtype = 171
              AND d.Date >= %s AND d.Date <= %s
            """
            params = [search_start.strftime('%Y-%m-%d'), search_end.strftime('%Y-%m-%d')]
            if search_kw.strip():
                sql += " AND d.Number LIKE %s"
                params.append(f"%{search_kw.strip()}%")
            cursor.execute(sql + " ORDER BY d.Date DESC", params)
            task_records = cursor.fetchall()
            
        if not task_records:
            st.warning("暂无待领料的任务单。")
            return
            
        df_tasks = pd.DataFrame(task_records).rename(columns={'BillDate': '日期', 'BillNumber': '任务单号', 'Workshop': '车间', 'Maker': '制单人', 'SummaryInfo': '摘要'})
        sel_event = st.dataframe(df_tasks, selection_mode="multi-row", on_select="rerun", use_container_width=True, hide_index=True)
        
        if sel_event.selection.rows:
            if st.button("确认引入明细", type="primary"):
                import_list = []
                with conn_erp.cursor(as_dict=True) as cursor:
                    for idx in sel_event.selection.rows:
                        v_code = df_tasks.iloc[idx]['VchCode']
                        v_num = df_tasks.iloc[idx]['任务单号']
                        cursor.execute("""
                            SELECT dsc.Qty, dsc.ToQty, dsc.Price, p.typeId, p.FullName, p.Standard 
                            FROM DlySC dsc LEFT JOIN Ptype p ON dsc.PtypeId = p.typeId 
                            WHERE dsc.Vchcode = %s AND dsc.Usedtype = 2
                        """, (int(v_code),))
                        for r in cursor.fetchall():
                            rem = float(r['Qty'] or 0) - float(r['ToQty'] or 0)
                            if rem > 0:
                                import_list.append({
                                    "任务单号": f"{v_num} | {v_code}",
                                    "材料与规格": f"{r['FullName']} ({r['Standard'] or '无'}) | {r['typeId']}",
                                    "领用数量": rem, "单价": float(r['Price'] or 0), "备注": ""
                                })
                st.session_state['pick_table_records'] = pd.DataFrame(import_list)
                st.rerun()
    except Exception as e:
        st.error(f"选单失败: {e}")

# ==========================================
# 3. 主页面逻辑
# ==========================================
def show(st, conn_erp):
    st.markdown(f"### 📋 {T('生产领料单')}")
    
    # 初始化清空机制
    if 'pick_comment_val' not in st.session_state: st.session_state['pick_comment_val'] = ""

    # 加载资料
    cursor = conn_erp.cursor(as_dict=True)
    cursor.execute("SELECT typeId, FullName FROM Employee")
    emps_dict = {r['FullName']: r['typeId'] for r in cursor.fetchall()}
    cursor.execute("SELECT typeId, FullName FROM Stock")
    stocks_dict = {r['FullName']: r['typeId'] for r in cursor.fetchall()}
    cursor.execute("SELECT typeId, FullName, Standard FROM Ptype WHERE (typeId LIKE '00001%' OR typeId LIKE '00003%' OR typeId LIKE '00004%' OR typeId LIKE '00005%' OR typeId LIKE '00006%') AND leveal IN (3, 4, 5)")
    mats_dict = {f"{r['FullName']} ({r['Standard'] or '无'}) | {r['typeId']}": r['typeId'] for r in cursor.fetchall()}

    # 默认值索引计算
    emp_names = list(emps_dict.keys())
    stock_names = list(stocks_dict.keys())
    idx_stock = next((i for i, n in enumerate(stock_names) if stocks_dict[n] == '00010'), 0)
    idx_emp = next((i for i, n in enumerate(emp_names) if emps_dict[n] == '00041'), 0)

    tab_entry, tab_drafts, tab_history = st.tabs([T("📝 单据录入"), T("📋 待审核(草稿)"), T("📜 领料经营历程")])

    with tab_entry:
        msg_box = st.empty()
        if 'pick_msg' in st.session_state:
            m = st.session_state['pick_msg']
            msg_box.success(m['text']) if m['type']=='success' else msg_box.error(m['text'])
            del st.session_state['pick_msg']

        tcol1, tcol2 = st.columns([3, 1])
        with tcol2:
            b_date = st.date_input("制单日期", datetime.date.today(), key="p_date")
            b_code = st.text_input("单据编号", f"LLD-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}")
        with tcol1:
            i1, i2 = st.columns(2)
            sel_stock = i1.selectbox("发料仓库", options=stock_names, index=idx_stock)
            st.text_input("摘要", key="pick_comment_val")
            i2.text_input("业务类型", value="生产领料", disabled=True)
            sel_emp = i2.selectbox("经手人", options=emp_names, index=idx_emp)

        st.markdown("---")
        b1, b2, b3 = st.columns([2, 6, 2])
        if b1.button("📥 选单 (引入任务)", use_container_width=True): select_manufacture_order_dialog(conn_erp, mats_dict)
        save_btn = b3.button("保存草稿", type="primary", use_container_width=True)

        if 'pick_table_records' not in st.session_state:
            st.session_state['pick_table_records'] = pd.DataFrame(columns=["任务单号", "材料与规格", "领用数量", "单价", "备注"])

        final_edit_df = st.data_editor(st.session_state['pick_table_records'], num_rows="dynamic", use_container_width=True, key="pick_editor", column_config={
            "材料与规格": st.column_config.SelectboxColumn("原材料明细", options=list(mats_dict.keys()), required=True, width="large"),
            "领用数量": st.column_config.NumberColumn("数量", min_value=0.01, required=True),
            "单价": st.column_config.NumberColumn("单价", min_value=0.0),
            "备注": st.column_config.TextColumn("备注")
        })

        if save_btn:
            if final_edit_df.empty:
                st.session_state['pick_msg'] = {'type': 'error', 'text': '请录入明细！'}; st.rerun()
            try:
                # 1. 插入 Dlyndx
                summary = f"{st.session_state['pick_comment_val']}-dplight系统生成"
                cursor.execute("INSERT INTO Dlyndx (DATE, NUMBER, VchType, summary, etypeid, ktypeid, ifcheck, period, draft, Total, SaveTime) OUTPUT Inserted.Vchcode VALUES (%s, %s, 172, %s, %s, %s, '000050000100001', %s, 1, 0, GETDATE())", (b_date.strftime('%Y-%m-%d'), b_code, summary, emps_dict[sel_emp], stocks_dict[sel_stock], int(b_date.strftime('%Y%m'))))
                v_code = cursor.fetchone()['Vchcode']
                # 2. 插入 BakDly
                for idx, row in final_edit_df.iterrows():
                    pid = mats_dict.get(row['材料与规格'])
                    qty, pri = float(row['领用数量']), float(row['单价'])
                    cursor.execute("INSERT INTO BakDly (Vchcode, ktypeid, PtypeId, Qty, price, total, comment, date, usedtype, period, Vchtype, RowNo) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, '2', %s, 172, %s)", (v_code, stocks_dict[sel_stock], pid, qty, pri, qty*pri, row['备注'], b_date.strftime('%Y-%m-%d'), int(b_date.strftime('%Y%m')), idx+1))
                conn_erp.commit()
                st.session_state['pick_msg'] = {'type': 'success', 'text': f"✅ 保存成功！单号 {b_code}"}
                st.session_state['pick_table_records'] = pd.DataFrame(columns=["任务单号", "材料与规格", "领用数量", "单价", "备注"])
                st.session_state['pick_comment_val'] = ""; st.rerun()
            except Exception as e:
                conn_erp.rollback(); st.error(f"失败: {e}")

    with tab_drafts:
        st.subheader("待审核领料草稿")
        cursor.execute("SELECT d.vchcode AS VchCode, d.DATE AS VchDate, d.NUMBER AS VchNumber, e.FullName AS Maker, k.FullName AS Stock, d.summary AS SummaryInfo FROM Dlyndx d LEFT JOIN Employee e ON d.etypeid = e.typeId LEFT JOIN Stock k ON d.ktypeid = k.typeId WHERE d.VchType = 172 AND d.draft = 1 ORDER BY d.DATE DESC")
        recs = cursor.fetchall()
        if recs:
            df = pd.DataFrame(recs).rename(columns={'VchDate':'日期','VchNumber':'单据编号','Maker':'经手人','Stock':'发料仓库','SummaryInfo':'摘要'})
            sel = st.dataframe(df, use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun")
            if sel.selection.rows: show_voucher_details(pd.DataFrame(recs).iloc[sel.selection.rows[0]].to_dict(), conn_erp, True)
        else: st.info("暂无草稿。")

    with tab_history:
        st.subheader("已过账领料历史")
        h1, h2 = st.columns(2)
        s_d = h1.date_input("开始日期", datetime.date.today()-datetime.timedelta(days=7), key="hs")
        e_d = h2.date_input("结束日期", datetime.date.today(), key="he")
        cursor.execute("SELECT d.vchcode AS VchCode, d.DATE AS VchDate, d.NUMBER AS VchNumber, e.FullName AS Maker, k.FullName AS Stock, d.summary AS SummaryInfo FROM Dlyndx d LEFT JOIN Employee e ON d.etypeid = e.typeId LEFT JOIN Stock k ON d.ktypeid = k.typeId WHERE d.VchType = 172 AND d.draft = 2 AND d.DATE >= %s AND d.DATE <= %s ORDER BY d.DATE DESC", (s_d.strftime('%Y-%m-%d'), e_d.strftime('%Y-%m-%d')))
        recs_h = cursor.fetchall()
        if recs_h:
            df_h = pd.DataFrame(recs_h).rename(columns={'VchDate':'日期','VchNumber':'单据编号','Maker':'经手人','Stock':'发料仓库','SummaryInfo':'摘要'})
            sel_h = st.dataframe(df_h, use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun")
            if sel_h.selection.rows: show_voucher_details(pd.DataFrame(recs_h).iloc[sel_h.selection.rows[0]].to_dict(), conn_erp, False)
        else: st.info("该时段无记录。")