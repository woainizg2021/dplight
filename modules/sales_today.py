# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st
import datetime
import re
import pymysql
from openai import OpenAI
import config
from modules.languages import t  

def run_query(conn, sql):
    try:
        return pd.read_sql(sql, conn)
    except Exception as e:
        st.error(f"SQL执行报错: {str(e)} \n\n 对应的SQL: {sql}")
        return pd.DataFrame()

def get_check_status_map(mysql_conf, country, module_type, v_codes):
    if not v_codes: return {}
    try:
        conn = pymysql.connect(**mysql_conf)
        with conn.cursor() as cursor:
            placeholders = ', '.join(['%s'] * len(v_codes))
            sql = f"SELECT v_code, is_checked FROM check_status WHERE country=%s AND module=%s AND v_code IN ({placeholders})"
            cursor.execute(sql, [country, module_type] + v_codes)
            result = cursor.fetchall()
            return {row[0]: bool(row[1]) for row in result}
    except:
        return {}
    finally:
        if 'conn' in locals(): conn.close()

def update_single_check(mysql_conf, country, module_type, v_code, status):
    try:
        conn = pymysql.connect(**mysql_conf)
        with conn.cursor() as cursor:
            sql = "REPLACE INTO check_status (country, module, v_code, is_checked, update_time) VALUES (%s, %s, %s, %s, NOW())"
            cursor.execute(sql, (country, module_type, v_code, 1 if status else 0))
            conn.commit()
    except:
        pass
    finally:
        if 'conn' in locals(): conn.close()

def handle_date_change():
    st.session_state.current_date = st.session_state._date_picker
    st.session_state.flag_loaded = False

def show(st, conn_erp, mysql_conf, current_country):
    st.markdown(f"""
        <div style="padding-top: 15px; padding-bottom: 10px; font-size: 20px; font-weight: bold; color: #333; line-height: 1.5;">
            📊 {t('销售查询')}
        </div>
    """, unsafe_allow_html=True)

    if 'sales_df' not in st.session_state:
        st.session_state.sales_df = pd.DataFrame()
    if 'expense_df' not in st.session_state:
        st.session_state.expense_df = pd.DataFrame()
    if 'all_exp_df' not in st.session_state:
        st.session_state.all_exp_df = pd.DataFrame()
    if 'model_df' not in st.session_state:
        st.session_state.model_df = pd.DataFrame()
    if 'current_date' not in st.session_state:
        st.session_state.current_date = datetime.date.today()
    if 'flag_loaded' not in st.session_state:
        st.session_state.flag_loaded = False
    if 'editor_key_counter' not in st.session_state:
        st.session_state.editor_key_counter = 0

    c_date, c_btn, c_ai, _ = st.columns([2, 1, 2.5, 4.5])
    with c_date:
        st.date_input(t("选择日期"), value=st.session_state.current_date, key="_date_picker", on_change=handle_date_change, label_visibility="collapsed")
    with c_btn:
        if st.button(t("刷新数据"), type="primary", use_container_width=True):
            st.session_state.flag_loaded = False
            st.rerun()
    with c_ai:
        run_ai = st.button("🤖 AI 综合分析", type="secondary", use_container_width=True)

    str_date = st.session_state.current_date.strftime('%Y-%m-%d')

    if run_ai:
        with st.spinner("AI 智能机器人正在联动分析「销售查询」与「热销款缺货天数」，请稍候..."):
            try:
                ai_client = OpenAI(api_key=config.AI_CONFIG['api_key'], base_url=config.AI_CONFIG['base_url'])
                
                sales_str = "今日暂无销售数据"
                if not st.session_state.model_df.empty:
                    sales_str = st.session_state.model_df[["型号", "箱数", "总价"]].head(10).to_string(index=False)
                
                sql_hot_stockout = """
                WITH PtypeBase AS (
                    SELECT typeid, FullName AS 存货名称, ISNULL(NULLIF(UnitRate1, 0), 1) AS 装箱数 
                    FROM dbo.ptype 
                    WHERE typeid IN ('000020000100002', '000020000100003', '000020000100006', '000020000100007', '000020000300006', '000020000400004', '000020000400007', '000020000400010', '000020000400012', '000020000400018', '000020000400024', '000020000400025', '000020000500007', '000020000500012', '000020000500017', '000020000500023', '000020000500024', '000020000500025', '000020000500026', '000020000500027', '000020000500029', '000020000500034', '000020000500038', '000020000500039', '000020000500044', '000020000500045', '000020000800001', '000020000900037', '000020001200013', '000020001200014', '000020001200018', '000020002700001') 
                    AND Deleted = 0 AND sonnum = 0
                ),
                CurrentStock AS (
                    SELECT PtypeId, SUM(CASE WHEN KtypeId = '00003' THEN Qty ELSE 0 END) AS 门市库存, SUM(CASE WHEN KtypeId IN ('00003', '00011') THEN Qty ELSE 0 END) AS 总库存 
                    FROM dbo.GoodsStocks WHERE KtypeId IN ('00003', '00011') AND PtypeId IN (SELECT typeid FROM PtypeBase) GROUP BY PtypeId
                )
                SELECT 
                    CAST(pb.存货名称 AS NVARCHAR(200)) AS 热销款名称,
                    CAST(ISNULL(cs.门市库存, 0) * 1.0 / pb.装箱数 AS DECIMAL(18, 1)) AS 门市当前箱数,
                    CAST(ISNULL(cs.总库存, 0) * 1.0 / pb.装箱数 AS DECIMAL(18, 1)) AS 总库存箱数
                FROM PtypeBase pb LEFT JOIN CurrentStock cs ON pb.typeid = cs.PtypeId
                WHERE (ISNULL(cs.门市库存, 0) * 1.0 / pb.装箱数) < 6
                ORDER BY 门市当前箱数 ASC
                """
                df_hot = run_query(conn_erp, sql_hot_stockout)
                stock_str = "32款热销产品目前库存充足，无缺货危机。"
                if not df_hot.empty:
                    stock_str = df_hot.to_string(index=False)
                
                # 🔥 AI 提示词精准修正：乌方业务员
                prompt = f"""
                你是Dplight跨国照明工厂的营运总监。请结合【今日销售查询】与【热销32款的缺货天数】，写一份直击痛点、具备执行力的经营分析报告。
                数据：
                1. 【今日销售主力】：\n{sales_str}
                2. 【热销32款-高危缺货清单】（列出的都是门市当前箱数不足6箱的红线款）：\n{stock_str}

                要求：
                1. 语言干练、一针见血。客观，公正，指导销售和生产，具备落地可执行指导意见。禁用“一塌糊涂”等侮辱性词汇。
                2. 综合分析：看看今天的销量是否受了缺货的影响？点名批评缺货的核心款，下达补货指令。考虑海运至少45天的因素。考虑生产效率因素。考虑当地员工效率和熟练程度因素。考虑中方和乌方业务员因素。
                3. 【排版铁律】：绝对禁止使用任何大标题（禁用 # 语法）。通篇使用常规加粗文字和无序列表。
                4. 【视觉高亮】：对于缺货箱数、核心型号、补货指令，必须使用HTML标签 `<span style='background-color: #ffe58f; color: #000; font-weight: bold; padding: 2px 4px; border-radius: 3px;'>你的文字</span>` 进行背景高亮！
                """
                
                response = ai_client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}], temperature=0.7)
                st.markdown(f"""
                <div style="background-color: #ffffff; color: #000000; padding: 20px 24px; border-radius: 8px; border-left: 4px solid #8e44ad; box-shadow: 0 2px 8px rgba(0,0,0,0.08); font-size: 0.95rem; line-height: 1.6; margin-bottom: 20px;">
                    <div style="font-size: 1.1rem; font-weight: bold; margin-bottom: 12px; color: #222;">🤖 营运总监·销存联动诊断报告</div>
                    {response.choices[0].message.content}
                </div>
                """, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"🤖 AI 调用出现异常，请稍后重试: {e}")

    if not st.session_state.flag_loaded:
        with st.spinner(t("加载中...")):
            sql_sales = f"""
            SELECT d.VchCode, d.Number AS [完整单号], CAST(ISNULL(d.Summary, '') AS NVARCHAR(500)) AS [摘要], 
                CASE WHEN d.VchType = 11 THEN ABS(d.Total) ELSE 0 END AS [销售金额],
                ISNULL((SELECT SUM(ABS(DebitTotal)) FROM DlyA a WHERE a.VchCode = d.VchCode AND a.AtypeId LIKE '0000100001%'), 0) AS [现金],
                ISNULL((SELECT SUM(ABS(DebitTotal)) FROM DlyA a WHERE a.VchCode = d.VchCode AND a.AtypeId LIKE '0000100002%'), 0) AS [银行],
                CASE WHEN d.VchType IN (4, 2) THEN ABS(d.Total) ELSE 0 END AS [收回欠款],
                CAST(b.FullName AS NVARCHAR(200)) AS [客户]
            FROM Dlyndx d LEFT JOIN Btype b ON d.BtypeId = b.TypeId
            WHERE d.Date = '{str_date}' AND d.Draft = 2 AND d.VchType IN (11, 4, 2) ORDER BY d.VchCode DESC
            """
            df_sales = run_query(conn_erp, sql_sales)
            if not df_sales.empty:
                df_sales['应收账款'] = df_sales.apply(lambda r: max(0, r['销售金额'] - r['现金'] - r['银行']) if r['销售金额'] > 0 else 0, axis=1)
                df_sales['手工单号'] = df_sales['摘要'].apply(lambda x: ",".join(re.findall(r'[(（](.*?)[)）]', str(x))) if x else "")
                df_sales['显示单号'] = df_sales['完整单号'].astype(str).apply(lambda x: x[-5:] if len(x)>5 else x)
                v_codes = df_sales['VchCode'].astype(str).tolist()
                check_map = get_check_status_map(mysql_conf, current_country, "TodaySales", v_codes)
                df_sales['核对'] = df_sales['VchCode'].astype(str).map(check_map).fillna(False)
                st.session_state.sales_df = df_sales
            else:
                st.session_state.sales_df = pd.DataFrame()
            
            st.session_state.all_exp_df = run_query(conn_erp, f"SELECT * FROM [v_费用明细列表] WHERE CONVERT(varchar(10), [业务日期], 120) = '{str_date}'")
            df_total_exp = run_query(conn_erp, f"SELECT ISNULL(SUM([借方金额_元]), 0) AS [今日费用] FROM [v_费用明细列表] WHERE CONVERT(varchar(10), [业务日期], 120) = '{str_date}'")
            st.session_state.all_exp_total = df_total_exp['今日费用'].iloc[0] if not df_total_exp.empty else 0.0
            
            f_lend = "lendtotal"
            f_debit = "debittotal"
            try:
                with conn_erp.cursor() as cursor:
                    cursor.execute("SELECT name FROM sys.columns WHERE object_id = OBJECT_ID('t_cw_dly')")
                    dly_cols = [row[0].lower() for row in cursor.fetchall()]
                    if 'lendtotal' in dly_cols: 
                        f_lend = 'lendtotal'
                        f_debit = 'debittotal'
                    elif 'credit' in dly_cols: 
                        f_lend = 'credit'
                        f_debit = 'debit'
                    elif 'df' in dly_cols: 
                        f_lend = 'df'
                        f_debit = 'jf'
            except:
                pass

            sql_exp = f"""
            SELECT RTRIM(a.atypeid) AS AtypeId, ISNULL(vt.FullName, '手工凭证') AS VchTypeName, a.vchtype AS VchTypeCode,
                SUM(CASE WHEN a.vchtype = 45 THEN ABS(ISNULL(a.{f_debit}, 0)) ELSE ISNULL(a.{f_lend}, 0) END) AS Amount
            FROM t_cw_dly a JOIN t_cw_dlyndx ndx ON a.vchcode = ndx.vchcode LEFT JOIN vchtype vt ON a.vchtype = vt.vchtype
            WHERE a.date = '{str_date}' AND ndx.draft = 2 AND RTRIM(a.atypeid) IN ('000010000100001', '000010000100002', '000010000100003', '000010000100004')
            GROUP BY RTRIM(a.atypeid), ISNULL(vt.FullName, '手工凭证'), a.vchtype
            """
            df_exp = run_query(conn_erp, sql_exp)
            acc_map = {'000010000100001': '门市先令现金', '000010000100002': '工厂先令现金', '000010000100003': '门市美金现金', '000010000100004': '工厂美金现金'}
            exp_results = {k: {'账户名称': v, '费用支出': 0.0, '付款单支付': 0.0, '退货支出': 0.0, '其他支出': 0.0, '合计': 0.0} for k, v in acc_map.items()}
            
            if not df_exp.empty and 'AtypeId' in df_exp.columns:
                for _, r in df_exp.iterrows():
                    aid = str(r['AtypeId']).strip()
                    pay_amt = float(r['Amount']) if pd.notna(r['Amount']) else 0.0
                    if aid in exp_results:
                        if r['VchTypeCode'] == '45' or '退货' in r['VchTypeName']: exp_results[aid]['退货支出'] += pay_amt
                        elif '付款' in r['VchTypeName']: exp_results[aid]['付款单支付'] += pay_amt
                        elif '费用' in r['VchTypeName'] or '凭证' in r['VchTypeName']: exp_results[aid]['费用支出'] += pay_amt
                        else: exp_results[aid]['其他支出'] += pay_amt 
            
            exp_list = list(exp_results.values())
            sum_fee, sum_pay, sum_ret, sum_oth = sum([x['费用支出'] for x in exp_list]), sum([x['付款单支付'] for x in exp_list]), sum([x['退货支出'] for x in exp_list]), sum([x['其他支出'] for x in exp_list])
            for x in exp_list: x['合计'] = x['费用支出'] + x['付款单支付'] + x['退货支出'] + x['其他支出']
            st.session_state.store_shilling_exp = exp_results.get('000010000100001', {}).get('合计', 0.0)
            exp_list.append({'账户名称': '【总计】', '费用支出': sum_fee, '付款单支付': sum_pay, '退货支出': sum_ret, '其他支出': sum_oth, '合计': sum_fee + sum_pay + sum_ret + sum_oth})
            st.session_state.expense_df = pd.DataFrame(exp_list)
            
            # 🔥 终极防空数据方案：
            # 1. UNION ALL 囊括你说的所有表！
            # 2. 严格遵循 p.typeId = t.ptypeid！
            # 3. GROUP BY t.ptypeid 兜底，即便关联失败也绝对出数据！
            sql_model = f"""
            SELECT 
                MAX(CAST(ISNULL(p.FullName, '未知商品') AS NVARCHAR(200))) AS [型号],
                MAX(CAST(ISNULL(p.UnitRate1, 1) AS DECIMAL(18,2))) AS [装箱数],
                SUM(ABS(ISNULL(t.Qty, 0))) AS [总数量],
                SUM(ABS(ISNULL(t.total, 0))) AS [总价]
            FROM (
                SELECT vchcode, ptypeid, Qty, total FROM dbo.DlySale
                UNION ALL
                SELECT vchcode, ptypeid, Qty, total FROM dbo.DlyBuy
                UNION ALL
                SELECT vchcode, ptypeid, Qty, total FROM dbo.dlyother
            ) t
            JOIN dbo.Dlyndx d ON t.vchcode = d.vchcode
            LEFT JOIN dbo.ptype p ON t.ptypeid = p.typeid
            WHERE CONVERT(varchar(10), d.Date, 120) = '{str_date}' 
              AND d.Draft = 2
            GROUP BY t.ptypeid
            HAVING SUM(ABS(ISNULL(t.Qty, 0))) > 0 OR SUM(ABS(ISNULL(t.total, 0))) > 0
            ORDER BY SUM(ABS(ISNULL(t.total, 0))) DESC, SUM(ABS(ISNULL(t.Qty, 0))) DESC
            """
            df_m = run_query(conn_erp, sql_model)
            if not df_m.empty:
                df_m['箱数'] = df_m.apply(lambda r: round(r['总数量']/r['装箱数'], 1) if r['装箱数'] > 0 else 0, axis=1)
                df_m['单价'] = df_m.apply(lambda r: round(r['总价'] / r['总数量'], 2) if r['总数量'] > 0 else 0, axis=1)
            st.session_state.model_df = df_m
            
            st.session_state.flag_loaded = True

    col_left, col_right = st.columns([2.3, 1])

    with col_left:
        df_view = st.session_state.sales_df
        if not df_view.empty:
            display_cols = ["核打勾", "显示单号", "手工单号", "销售金额", "现金", "应收账款", "收回欠款", "银行", "客户"]
            df_temp = df_view.rename(columns={"核对": "核打勾"})
            
            editor_key = f"sales_editor_{str_date}_{current_country}_{st.session_state.editor_key_counter}"
            edited_res = st.data_editor(
                df_temp[display_cols],
                key=editor_key,
                use_container_width=True,
                height=450,
                hide_index=True,
                disabled=["显示单号", "手工单号", "销售金额", "现金", "应收账款", "收回欠款", "银行", "客户"],
                column_config={
                    "核打勾": st.column_config.CheckboxColumn(label=t("核对"), width="small"),
                    "显示单号": st.column_config.TextColumn(label=t("销售单号"), width=None),
                    "手工单号": st.column_config.TextColumn(label=t("手工单号")),
                    "销售金额": st.column_config.NumberColumn(label=t("销售金额"), format="%.2f"),
                }
            )

            if st.session_state.get(editor_key) and st.session_state[editor_key].get("edited_rows"):
                changes = st.session_state[editor_key]["edited_rows"]
                has_updates = False
                for idx_str, col_changes in changes.items():
                    if "核打勾" in col_changes:
                        idx = int(idx_str)
                        new_val = col_changes["核打勾"]
                        v_code = str(df_view.loc[idx, 'VchCode'])
                        update_single_check(mysql_conf, current_country, "TodaySales", v_code, new_val)
                        st.session_state.sales_df.at[idx, '核对'] = new_val
                        has_updates = True
                
                if has_updates:
                    st.session_state.editor_key_counter += 1
                    st.rerun()

            sums = df_view[['销售金额', '现金', '应收账款', '收回欠款', '银行']].sum()
            st.markdown(
                f"| **{t('合计')}** | **{t('销售金额')}** | **{t('现金')}** | **{t('应收账款')}** | **{t('收回欠款')}** | **{t('银行(支票)')}** | **💰 {t('费用')}** |\n"
                "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
                f"| {t('数值')} | `{sums['销售金额']:,.2f}` | `{sums['现金']:,.2f}` | `{sums['应收账款']:,.2f}` | `{sums['收回欠款']:,.2f}` | `{sums['银行']:,.2f}` | `{st.session_state.store_shilling_exp:,.2f}` |"
            )
        else:
            st.info(t("今日暂无流水数据"))

        st.markdown(f"##### 💸 {t('现金流出明细 (精细化四账户)')}")
        st.dataframe(st.session_state.expense_df, use_container_width=True, hide_index=True)

        st.markdown(f"##### 📋 {t('各项费用支出明细 (源自原始视图)')}")
        if not st.session_state.all_exp_df.empty:
            st.dataframe(st.session_state.all_exp_df, use_container_width=True, hide_index=True)
            st.caption(f"**{t('原始视图费用总计')}**: `{st.session_state.all_exp_total:,.2f}`")
        else:
            st.info(t("今日暂无原始视图费用记录"))

    with col_right:
        df_m = st.session_state.model_df
        if not df_m.empty:
            st.dataframe(
                df_m[["型号", "装箱数", "箱数", "单价", "总价"]], 
                use_container_width=True, height=650, hide_index=True,
                column_config={
                    "型号": st.column_config.TextColumn(label=t("型号")),
                    "装箱数": st.column_config.NumberColumn(label=t("装箱数")),
                    "箱数": st.column_config.NumberColumn(label=t("箱数"), format="%.1f"),
                    "单价": st.column_config.NumberColumn(label=t("单价"), format="%.2f"),
                    "总价": st.column_config.NumberColumn(label=t("总价"), format="%.2f"),
                }
            )
            st.success(f"**{t('合计箱数')}:** `{df_m['箱数'].sum():.1f}` | **{t('合计总价')}:** `{df_m['总价'].sum():,.2f}`")
        else:
            st.caption(t("暂无型号统计"))