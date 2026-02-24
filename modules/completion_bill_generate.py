# modules/completion_bill_generate.py
import streamlit as st
import pandas as pd
import datetime
from modules import languages

T = languages.t

# --- 核心：国家账套规则嗅探引擎 ---
def get_tenant_rules(dbname):
    rules = {
        'CMCSYUN355738': { # 🇳🇬 尼日利亚
            'fin': ['00003'], 
            'mat': ['00001', '00127', '00002'],
            'wh_fin': ['00006', '00002'], 
            'wh_mat': ['00001', '00004']
        },
        'CMCSYUN4348395': { # 🇰🇪 肯尼亚
            'fin': ['00003'], 
            'mat': ['00001', '00004', '00005', '00007', '00009', '00010', '00011', '00012', '00013', '00002'],
            'wh_fin': ['00002'], 
            'wh_mat': ['00004', '0000500001', '00001']
        },
        'CMCSYUN532502': { # 🇺🇬 乌干达
            'fin': ['00002'], 
            'mat': ['00001', '00003', '00004', '00005', '00006'],
            'wh_fin': ['00003', '00011'], 
            'wh_mat': ['00010']
        }
    }
    return rules.get(dbname.upper(), {'fin': ['00002','00003'], 'mat': ['00001','00002','00003'], 'wh_fin': [], 'wh_mat': []})

# ==========================================
# 1. 弹出框：单据明细渲染 (核心修复点：ID精准切分)
# ==========================================
@st.dialog("📄 单据明细 (Voucher Details)", width="large")
def show_voucher_details(row_dict, conn_erp, tenant_rules, is_draft=False):
    vch_code = row_dict.get('VchCode')
    vch_type_name = str(row_dict.get('单据类型', '完工验收单'))
    
    st.markdown(f"<h3 style='text-align: center;'>{vch_type_name}</h3>", unsafe_allow_html=True)
    st.caption(f"**VchCode:** `{vch_code}` | **状态:** `{'草稿' if is_draft else '已审核'}`")
    
    hc1, hc2, hc3, hc4 = st.columns(4)
    hc1.markdown(f"**{T('单据编号')}**<br>{row_dict.get('单据编号', '')}", unsafe_allow_html=True)
    hc2.markdown(f"**{T('日期')}**<br>{row_dict.get('日期', '')}", unsafe_allow_html=True)
    hc3.markdown(f"**{T('经手人')}**<br>{row_dict.get('制单人', '')}", unsafe_allow_html=True)
    hc4.markdown(f"**{T('入库仓库')}**<br>{row_dict.get('入库仓库', '')}", unsafe_allow_html=True)
    st.divider()
    
    if is_draft:
        # 获取了 PtypeId 用于精准识别
        detail_query = """
            SELECT p.FullName AS ProductName, t.PtypeId AS PtypeId, t.Qty AS Quantity, t.price AS UnitPrice, 
                   t.total AS TotalAmount, t.comment AS LineComment, 
                   t.FreeDom01 AS WorkerCount, t.FreeDom02 AS WorkHours, t.FreeDom03 AS WorkGroup 
            FROM BakDly t 
            LEFT JOIN Ptype p ON t.PtypeId = p.typeId 
            WHERE t.Vchcode = %s
        """
    else:
        # 过账查询同样获取 PtypeId
        detail_query = """
            SELECT p.FullName AS ProductName, t.PtypeId AS PtypeId, t.Qty AS Quantity, t.price AS UnitPrice, 
                   t.total AS TotalAmount, t.comment AS LineComment, 
                   t.FreeDom01 AS WorkerCount, t.FreeDom02 AS WorkHours, t.FreeDom03 AS WorkGroup 
            FROM (
                SELECT PtypeId, Qty, price, total, comment, FreeDom01, FreeDom02, FreeDom03 FROM Dlysale WHERE Vchcode = %s 
                UNION ALL 
                SELECT PtypeId, Qty, price, total, comment, FreeDom01, FreeDom02, FreeDom03 FROM Dlybuy WHERE Vchcode = %s 
                UNION ALL 
                SELECT PtypeId, Qty, price, total, comment, FreeDom01, FreeDom02, FreeDom03 FROM dlyother WHERE Vchcode = %s 
                UNION ALL 
                SELECT PtypeId, Qty, price, total, comment, FreeDom01, FreeDom02, FreeDom03 FROM DlySC WHERE Vchcode = %s
            ) t 
            LEFT JOIN Ptype p ON t.PtypeId = p.typeId
        """
    
    try:
        with conn_erp.cursor(as_dict=True) as cursor:
            if is_draft: 
                cursor.execute(detail_query, (vch_code,))
            else: 
                cursor.execute(detail_query, (vch_code, vch_code, vch_code, vch_code))
            detail_records = cursor.fetchall()
            
        if not detail_records:
            st.info(T("未找到明细。"))
        else:
            df_detail = pd.DataFrame(detail_records)
            
            # 【终极解决方案】：根据配置规则里的成品前缀，进行字符串级别的绝对切割
            fin_prefixes = tuple(tenant_rules['fin'])
            df_detail['行类型'] = df_detail['PtypeId'].apply(
                lambda x: '成品入库' if str(x).startswith(fin_prefixes) else '耗用材料'
            )
            
            df_detail['Quantity'] = pd.to_numeric(df_detail['Quantity'], errors='coerce').abs()
            df_detail['TotalAmount'] = pd.to_numeric(df_detail['TotalAmount'], errors='coerce').abs()
            
            # --- 分层 1: 完工产品 (必须展示自由项) ---
            st.markdown(f"**📦 {T('完工产品明细 (入库)')}**")
            df_fin = df_detail[df_detail['行类型'] == '成品入库'].copy()
            if not df_fin.empty:
                col_map_fin = {
                    'ProductName': '成品名称', 'Quantity': '数量', 'UnitPrice': '单价', 'TotalAmount': '金额', 
                    'WorkerCount': '作业人数(自由项1)', 'WorkHours': '作业时间(自由项2)', 'WorkGroup': '工作组(自由项3)', 'LineComment': '备注'
                }
                keep_cols_fin = [c for c in col_map_fin.keys() if c in df_fin.columns]
                df_display_fin = df_fin[keep_cols_fin].rename(columns=col_map_fin).fillna('')
                st.dataframe(df_display_fin, use_container_width=True, hide_index=True)
            else:
                st.caption(T("暂无成品入库记录。"))
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # --- 分层 2: 耗用材料 (隐蔽不相关的自由项) ---
            st.markdown(f"**🔧 {T('耗用材料明细 (出库)')}**")
            df_mat = df_detail[df_detail['行类型'] == '耗用材料'].copy()
            if not df_mat.empty:
                col_map_mat = {
                    'ProductName': '材料名称', 'Quantity': '数量', 'UnitPrice': '单价', 'TotalAmount': '金额', 'LineComment': '备注'
                }
                keep_cols_mat = [c for c in col_map_mat.keys() if c in df_mat.columns]
                df_display_mat = df_mat[keep_cols_mat].rename(columns=col_map_mat).fillna('')
                st.dataframe(df_display_mat, use_container_width=True, hide_index=True)
            else:
                st.caption(T("暂无耗用材料记录。"))

    except Exception as e:
        st.error(f"明细查询出错: {e}")
        
    st.divider()
    fc1, fc2 = st.columns([3, 1])
    fc1.markdown(f"**摘要:** {row_dict.get('摘要', '')}")

# ==========================================
# 2. 选单引入
# ==========================================
@st.dialog("📥 单据选择 : 生产任务单", width="large")
def select_manufacture_order_dialog(conn_erp, db_rules):
    st.markdown("##### 🔍 查询条件")
    today = datetime.date.today()
    col_q1, col_q2, col_q3 = st.columns([1, 1, 2])
    search_start = col_q1.date_input("开始日期", today.replace(day=1))
    search_end = col_q2.date_input("结束日期", today)
    search_kw = col_q3.text_input("任务单号 (支持模糊搜索)")

    try:
        with conn_erp.cursor(as_dict=True) as cursor:
            sql_tasks = "SELECT d.vchcode AS VchCode, d.Date AS BillDate, d.Number AS BillNumber, w.FullName AS Workshop, e.FullName AS Maker, d.Summary AS SummaryInfo FROM dlyndxsc d LEFT JOIN WorkShop w ON d.WtypeID = w.typeId LEFT JOIN Employee e ON d.EtypeID = e.typeId WHERE d.UserOver = 0 AND d.draft = 2 AND d.Vchtype = 171 AND d.Date >= %s AND d.Date <= %s"
            params = [search_start.strftime('%Y-%m-%d'), search_end.strftime('%Y-%m-%d')]
            if search_kw.strip():
                sql_tasks += " AND d.Number LIKE %s"
                params.append(f"%{search_kw.strip()}%")
            cursor.execute(sql_tasks + " ORDER BY d.Date DESC", params)
            task_records = cursor.fetchall()
            
        if not task_records:
            st.warning(T("无未完成生产任务单。"))
            return
            
        df_tasks = pd.DataFrame(task_records).rename(columns={'BillDate': '日期', 'BillNumber': '单据编号', 'Workshop': '车间', 'Maker': '制单人', 'SummaryInfo': '摘要'})
        sel_event = st.dataframe(df_tasks, selection_mode="multi-row", on_select="rerun", use_container_width=True, hide_index=True)
        
        if sel_event.selection.rows:
            if st.button("确认引入所选任务单", type="primary"):
                fin_list, mat_list = [], []
                with conn_erp.cursor(as_dict=True) as cursor:
                    for idx in sel_event.selection.rows:
                        vc = df_tasks.iloc[idx]['VchCode']
                        vn = df_tasks.iloc[idx]['单据编号']
                        cursor.execute("SELECT dsc.Usedtype AS UsedType, dsc.Qty AS PlanQty, dsc.ToQty AS FinishedQty, dsc.Price AS UnitPrice, p.typeId AS PTypeID, p.FullName AS ItemName, p.Standard AS ItemStd FROM DlySC dsc LEFT JOIN Ptype p ON dsc.PtypeId = p.typeId WHERE dsc.Vchcode = %s", (int(vc),))
                        for r in cursor.fetchall():
                            rem = float(r['PlanQty'] or 0) - float(r['FinishedQty'] or 0)
                            if rem <= 0: continue
                            item_str = f"{r['ItemName']} ({r['ItemStd'] or '无规格'}) | {r['PTypeID']}"
                            if str(r['UsedType']) == '1':
                                fin_list.append({"完工类型": "成品入库", "存货与规格": item_str, "任务单号": f"{vn} | {vc}", "验收数量": rem, "单价": float(r['UnitPrice'] or 0), "作业人数": 1, "作业时间": 0.0, "工作组": "", "备注": ""})
                            elif str(r['UsedType']) == '2':
                                mat_list.append({"任务单号": f"{vn} | {vc}", "存货与规格": item_str, "本次使用数量": rem, "单位成本": float(r['UnitPrice'] or 0)})
                st.session_state['fin_recs_v1'] = pd.DataFrame(fin_list)
                st.session_state['mat_recs_v1'] = pd.DataFrame(mat_list)
                st.rerun() 
    except Exception as e:
        st.error(f"查询失败: {e}")

# ==========================================
# 3. 基础资料智能缓存
# ==========================================
@st.cache_resource(ttl=300)
def fetch_erp_options(_conn, dbname):
    rules = get_tenant_rules(dbname)
    info_dict = {'emps': {}, 'stocks': {}, 'ptypes_finished': {}, 'ptypes_all': {}, 'tasks': {}}
    try:
        cursor = _conn.cursor(as_dict=True)
        cursor.execute("SELECT typeId, FullName FROM Employee")
        for r in cursor.fetchall(): info_dict['emps'][r['FullName']] = r['typeId']
        
        cursor.execute("SELECT typeId, FullName FROM Stock")
        for r in cursor.fetchall(): info_dict['stocks'][r['FullName']] = r['typeId']
        
        fin_cond = " OR ".join([f"typeId LIKE '{prefix}%'" for prefix in rules['fin']])
        cursor.execute(f"SELECT typeId, FullName, Standard FROM Ptype WHERE ({fin_cond}) AND leveal IN (3, 4, 5)")
        for r in cursor.fetchall(): info_dict['ptypes_finished'][f"{r['FullName']} ({r['Standard'] or '无'}) | {r['typeId']}"] = r['typeId']
        
        mat_cond = " OR ".join([f"typeId LIKE '{prefix}%'" for prefix in rules['mat']])
        cursor.execute(f"SELECT typeId, FullName, Standard FROM Ptype WHERE ({mat_cond}) AND leveal IN (3, 4, 5)")
        for r in cursor.fetchall(): info_dict['ptypes_all'][f"{r['FullName']} ({r['Standard'] or '无'}) | {r['typeId']}"] = r['typeId']
        
        cursor.execute("SELECT Vchcode, Number FROM dlyndxsc WHERE UserOver=0")
        for r in cursor.fetchall(): info_dict['tasks'][f"{r['Number']} | {r['Vchcode']}"] = str(r['Vchcode'])
    except Exception as e:
        st.error(f"加载资料失败: {e}")
    return info_dict, rules

# ==========================================
# 4. 主程序入口
# ==========================================
def show(st, conn_erp):
    # 嗅探国家账套
    with conn_erp.cursor() as cur:
        cur.execute("SELECT DB_NAME()")
        current_db = cur.fetchone()[0].upper()
        
    erp_dicts, tenant_rules = fetch_erp_options(conn_erp, current_db)
    
    st.markdown(f"### 🏭 {T('完工验收单系统')}")

    emp_names = list(erp_dicts['emps'].keys())
    stock_names = list(erp_dicts['stocks'].keys())
    
    # 智能定位默认仓库
    idx_stock = 0
    for target_id in tenant_rules['wh_fin']:
        found = False
        for i, sn in enumerate(stock_names):
            if erp_dicts['stocks'][sn] == target_id:
                idx_stock = i
                found = True
                break
        if found: break

    # 默认经手人 (如果有 00006 默认选 00006，没有则0)
    idx_emp = next((i for i, e in enumerate(emp_names) if erp_dicts['emps'][e] == '00006'), 0)

    # 状态初始化
    if 'wgys_sum_v1' not in st.session_state: st.session_state['wgys_sum_v1'] = ""

    tab_entry, tab_drafts, tab_audited = st.tabs([T("📝 单据录入"), T("📋 待审核(草稿)"), T("✅ 已过账列表")])

    with tab_entry:
        msg_box = st.empty()
        if 'wgys_notif' in st.session_state:
            n = st.session_state['wgys_notif']
            msg_box.success(n['txt']) if n['tp'] == 'ok' else msg_box.error(n['txt'])
            del st.session_state['wgys_notif']

        col_t1, col_t2 = st.columns([3, 1])
        with col_t2:
            b_date = st.date_input(T("制单日期"), datetime.date.today())
            b_code = st.text_input(T("单据编号"), f"WGYS-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}")
            is_fixed_cost = st.checkbox(T("按定额成本完工入库"), value=False)
        with col_t1:
            i1, i2 = st.columns(2)
            sel_stock = i1.selectbox(T("入库成品仓"), options=stock_names, index=idx_stock)
            st.text_input(T("摘要"), key="wgys_sum_v1")
            i2.text_input(T("业务类型"), value="基本生产", disabled=True)
            sel_emp = i2.selectbox(T("经手人"), options=emp_names, index=idx_emp)

        st.markdown("---")
        
        c_btn1, c_btn2, c_btn3 = st.columns([2, 6, 2])
        if c_btn1.button("📥 选单 (引入任务)"): select_manufacture_order_dialog(conn_erp, tenant_rules)
        save_btn = c_btn3.button(T("保存草稿"), type="primary", use_container_width=True)

        st.markdown(f"**{T('完工产品明细 (入库)')}**")
        if 'fin_recs_v1' not in st.session_state:
            st.session_state['fin_recs_v1'] = pd.DataFrame(columns=["完工类型", "存货与规格", "任务单号", "验收数量", "单价", "作业人数", "作业时间", "工作组", "备注"])

        edit_fin = st.data_editor(st.session_state['fin_recs_v1'], num_rows="dynamic", use_container_width=True, key="fin_ed_v1", column_config={
            "完工类型": st.column_config.SelectboxColumn("类型", options=["成品入库", "半成品入库"], default="成品入库"),
            "存货与规格": st.column_config.SelectboxColumn("成品明细", options=list(erp_dicts['ptypes_finished'].keys()), required=True, width="large"),
            "任务单号": st.column_config.SelectboxColumn("源任务单", options=["无"] + list(erp_dicts['tasks'].keys()), width="medium"),
            "验收数量": st.column_config.NumberColumn("数量", min_value=0.01, required=True),
            "单价": st.column_config.NumberColumn("单价", min_value=0.0),
            "作业人数": st.column_config.NumberColumn("作业人数", min_value=0, default=1),
            "作业时间": st.column_config.NumberColumn("作业时间", min_value=0.0),
            "工作组": st.column_config.TextColumn("工作组"),
            "备注": st.column_config.TextColumn("备注")
        })

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"**{T('耗用材料明细 (出库)')}**")
        if 'mat_recs_v1' not in st.session_state:
            st.session_state['mat_recs_v1'] = pd.DataFrame(columns=["任务单号", "存货与规格", "本次使用数量", "单位成本"])

        edit_mat = st.data_editor(st.session_state['mat_recs_v1'], num_rows="dynamic", use_container_width=True, key="mat_ed_v1", column_config={
            "任务单号": st.column_config.SelectboxColumn("任务单号", options=["无"] + list(erp_dicts['tasks'].keys()), width="medium"),
            "存货与规格": st.column_config.SelectboxColumn("耗用材料", options=list(erp_dicts['ptypes_all'].keys()), required=True, width="large"),
            "本次使用数量": st.column_config.NumberColumn("消耗数量", min_value=0.01, required=True),
            "单位成本": st.column_config.NumberColumn("单位成本", min_value=0.0)
        })

        if save_btn:
            if edit_fin.empty and edit_mat.empty:
                st.session_state['wgys_notif'] = {'tp': 'err', 'txt': '请录入明细！'}; st.rerun()
            try:
                cursor = conn_erp.cursor(as_dict=True)
                eid, sid = erp_dicts['emps'][sel_emp], erp_dicts['stocks'][sel_stock]
                cursor.execute("SELECT TOP 1 period FROM T_GBL_MonthProc WHERE StartDate <= %s AND EndDate >= %s", (b_date.strftime('%Y-%m-%d'), b_date.strftime('%Y-%m-%d')))
                prd_res = cursor.fetchone()
                prd = prd_res['period'] if prd_res else int(b_date.strftime('%Y%m'))

                edit_fin["验收数量"] = pd.to_numeric(edit_fin["验收数量"], errors='coerce').fillna(0)
                edit_fin["单价"] = pd.to_numeric(edit_fin["单价"], errors='coerce').fillna(0)
                sum_total = float((edit_fin["验收数量"] * edit_fin["单价"]).sum())
                f_flag = 1 if is_fixed_cost else 0
                final_sum = f"{st.session_state['wgys_sum_v1']}-dplight系统生成"

                cursor.execute("INSERT INTO Dlyndx (DATE, NUMBER, VchType, summary, etypeid, ktypeid, ifcheck, period, draft, Total, SaveTime, NormCost, BillTotal) OUTPUT Inserted.Vchcode VALUES (%s, %s, 174, %s, %s, %s, '000050000100001', %s, 1, %s, GETDATE(), %s, %s)", 
                               (b_date.strftime('%Y-%m-%d'), b_code, final_sum, eid, sid, prd, sum_total, f_flag, sum_total))
                v_code = cursor.fetchone()['Vchcode']

                # 插入成品
                r_num = 1
                for _, r in edit_fin.iterrows():
                    pid = erp_dicts['ptypes_finished'].get(r["存货与规格"], "")
                    if not pid: continue
                    tid = int(erp_dicts['tasks'].get(str(r.get("任务单号", "无")), 0))
                    q, p = float(r["验收数量"]), float(r["单价"])
                    cursor.execute("INSERT INTO BakDly (Vchcode, etypeid, ktypeid, PtypeId, Qty, price, total, comment, date, usedtype, period, FreeDom01, FreeDom02, FreeDom03, SourceVchCode, RowNo, SourceVchType) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, '1', %s, %s, %s, %s, %s, %s, 171)", 
                                   (v_code, eid, sid, pid, q, p, q*p, r.get("备注", ""), b_date.strftime('%Y-%m-%d'), prd, str(r.get("作业人数", "1")), str(r.get("作业时间", "0")), str(r.get("工作组", "")), tid, r_num))
                    r_num += 1

                # 插入材料
                for _, r in edit_mat.iterrows():
                    pid = erp_dicts['ptypes_all'].get(r["存货与规格"], "")
                    if not pid: continue
                    tid = int(erp_dicts['tasks'].get(str(r.get("任务单号", "无")), 0))
                    q, p = float(r["本次使用数量"]), float(r["单位成本"])
                    cursor.execute("INSERT INTO BakDly (Vchcode, ktypeid, PtypeId, Qty, price, total, date, usedtype, period, SourceVchCode, RowNo, SourceVchType) VALUES (%s, %s, %s, %s, %s, %s, %s, '2', %s, %s, %s, 171)", 
                                   (v_code, sid, pid, q, p, q*p, b_date.strftime('%Y-%m-%d'), prd, tid, r_num))
                    r_num += 1

                conn_erp.commit()
                st.session_state['wgys_notif'] = {'tp': 'ok', 'txt': f"✅ 保存成功！单号: {b_code}"}
                st.session_state['wgys_sum_v1'] = ""
                st.session_state['fin_recs_v1'] = pd.DataFrame(columns=["完工类型", "存货与规格", "任务单号", "验收数量", "单价", "作业人数", "作业时间", "工作组", "备注"])
                st.session_state['mat_recs_v1'] = pd.DataFrame(columns=["任务单号", "存货与规格", "本次使用数量", "单位成本"])
                st.rerun()
            except Exception as e:
                conn_erp.rollback(); st.error(f"报错: {e}")

    with tab_drafts:
        st.subheader(T("待审核草稿列表"))
        if st.button("🔄 刷新草稿"): st.rerun()
        try:
            with conn_erp.cursor(as_dict=True) as cursor:
                cursor.execute("SELECT d.vchcode AS VchCode, d.DATE AS VDate, d.NUMBER AS VNum, e.FullName AS EMName, k.FullName AS SKName, d.Total, d.summary FROM Dlyndx d LEFT JOIN Employee e ON d.etypeid = e.typeId LEFT JOIN Stock k ON d.ktypeid = k.typeId WHERE d.VchType = 174 AND d.draft = 1 ORDER BY d.DATE DESC")
                items_d = cursor.fetchall()
            if items_d:
                df_d = pd.DataFrame(items_d).rename(columns={'VDate':'日期','VNum':'单据编号','EMName':'制单人','SKName':'入库仓库','Total':'金额','summary':'摘要'})
                sel_d = st.dataframe(df_d, use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun")
                if sel_d.selection.rows:
                    rd = pd.DataFrame(items_d).iloc[sel_d.selection.rows[0]].to_dict()
                    rd.update({'单据类型': '完工验收单(草稿)', '单据编号': rd['VNum'], '日期': rd['VDate'], '制单人': rd['EMName'], '入库仓库': rd['SKName'], '金额': rd['Total'], '摘要': rd['summary']})
                    # 关键修改点：将 tenant_rules 传递进去
                    show_voucher_details(rd, conn_erp, tenant_rules, True)
            else: st.info("暂无待审核草稿。")
        except Exception as e:
            st.error(f"查询出错: {e}")

    with tab_audited:
        st.subheader(T("已过账列表"))
        h1, h2 = st.columns(2)
        s_d = h1.date_input("开始日期", datetime.date.today()-datetime.timedelta(days=7))
        e_d = h2.date_input("结束日期", datetime.date.today())
        try:
            with conn_erp.cursor(as_dict=True) as cursor:
                cursor.execute("SELECT d.vchcode AS VchCode, d.DATE AS VDate, d.NUMBER AS VNum, e.FullName AS EMName, k.FullName AS SKName, d.Total, d.summary, d.auditdate FROM Dlyndx d LEFT JOIN Employee e ON d.etypeid = e.typeId LEFT JOIN Stock k ON d.ktypeid = k.typeId WHERE d.VchType = 174 AND d.draft = 2 AND d.DATE >= %s AND d.DATE <= %s ORDER BY d.DATE DESC", (s_d.strftime('%Y-%m-%d'), e_d.strftime('%Y-%m-%d')))
                items_h = cursor.fetchall()
            if items_h:
                df_h = pd.DataFrame(items_h).rename(columns={'VDate':'日期','VNum':'单据编号','EMName':'制单人','SKName':'入库仓库','Total':'金额','summary':'摘要','auditdate':'审核日期'})
                sel_h = st.dataframe(df_h, use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun")
                if sel_h.selection.rows:
                    rh = pd.DataFrame(items_h).iloc[sel_h.selection.rows[0]].to_dict()
                    rh.update({'单据类型': '完工验收单', '单据编号': rh['VNum'], '日期': rh['VDate'], '制单人': rh['EMName'], '入库仓库': rh['SKName'], '金额': rh['Total'], '摘要': rh['summary']})
                    # 关键修改点：将 tenant_rules 传递进去
                    show_voucher_details(rh, conn_erp, tenant_rules, False)
            else: st.info("查询范围内无记录。")
        except Exception as e:
            st.error(f"查询出错: {e}")