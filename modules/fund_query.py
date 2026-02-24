import pandas as pd
import streamlit as st
import datetime
from modules.languages import t

SECRET_PASS = "8888"

def run_query(conn, sql):
    try:
        return pd.read_sql(sql, conn)
    except Exception:
        return pd.DataFrame()

def clean_zero(val):
    if val == 0 or val == 0.0: return None
    return val

def show(st, conn):
    # 翻译标题
    st.markdown(f"#### 💰 {t('资金查询')}")

    if 'show_fund' not in st.session_state:
        st.session_state['show_fund'] = False

    if not st.session_state['show_fund']:
        c1, c2 = st.columns([2, 1])
        with c1: st.info(t("此报表包含核心资金数据，请输入密码。"))
        with c2:
            pwd = st.text_input(t("解锁密码"), type="password", label_visibility="collapsed", key="fund_pwd")
            if pwd:
                if pwd == SECRET_PASS:
                    st.session_state['show_fund'] = True
                    st.rerun()
                else:
                    st.error(t("密码错误"))
        return

    # --- 解锁后 ---

    c1, c2, c3, c4 = st.columns([1.5, 1.5, 2, 2])
    with c1:
        today = datetime.date.today()
        # 翻译日期控件
        start_date = st.date_input(t("开始日期"), today.replace(day=1), key="fund_start")
    with c2:
        end_date = st.date_input(t("结束日期"), today, key="fund_end")
    with c3:
        try:
            # CAST 账户名称
            df_acc = run_query(conn, "SELECT DISTINCT CAST([账户名称] AS NVARCHAR(100)) AS [账户名称] FROM [v_资金明细源表]")
            acc_list = [t("全部账户")] + df_acc['账户名称'].tolist()
        except:
            acc_list = [t("全部账户")]
        
        # 翻译标签
        selected_acc = st.selectbox(t("选择账户"), acc_list)
        
    with c4:
        # 翻译按钮
        if st.button("🔒 " + t("锁定"), type="primary"):
            st.session_state['show_fund'] = False
            st.rerun()

    if start_date and end_date:
        s_date = start_date.strftime('%Y-%m-%d')
        e_date = end_date.strftime('%Y-%m-%d')
        
        # 1. 账户余额表
        sql_balance = f"""
        SELECT 
            CAST([账户名称] AS NVARCHAR(100)) AS [账户名称],
            [科目编码], 
            SUM(CASE WHEN [业务日期] < '{s_date}' THEN [净变动] ELSE 0 END) AS [期初余额],
            SUM(CASE WHEN [业务日期] BETWEEN '{s_date}' AND '{e_date}' THEN [收入金额] ELSE 0 END) AS [本期收入],
            SUM(CASE WHEN [业务日期] BETWEEN '{s_date}' AND '{e_date}' THEN [支出金额] ELSE 0 END) AS [本期支出],
            SUM(CASE WHEN [业务日期] <= '{e_date}' THEN [净变动] ELSE 0 END) AS [期末余额]
        FROM [v_资金明细源表]
        GROUP BY [账户名称], [科目编码]
        """
        
        acc_filter = ""
        if selected_acc != t("全部账户"):
            acc_filter = f"AND CAST([账户名称] AS NVARCHAR(100)) = '{selected_acc}'"
            sql_balance = f"SELECT * FROM ({sql_balance}) t WHERE [账户名称] = '{selected_acc}'"

        sql_detail = f"""
        SELECT 
            CONVERT(varchar(10), [业务日期], 120) AS [日期],
            CAST([账户名称] AS NVARCHAR(100)) AS [账户名称],
            CAST([摘要] AS NVARCHAR(500)) AS [摘要],
            [收入金额],
            [支出金额],
            CAST([往来单位] AS NVARCHAR(200)) AS [往来单位],
            CAST([经手人] AS NVARCHAR(100)) AS [经手人],
            [单据编号]
        FROM [v_资金明细源表]
        WHERE [业务日期] BETWEEN '{s_date}' AND '{e_date}'
        {acc_filter}
        ORDER BY [业务日期] DESC, [单据内码] DESC
        """

        df_bal = run_query(conn, sql_balance)
        df_det = run_query(conn, sql_detail)

        if not df_bal.empty:
            total_money = df_bal['期末余额'].sum()
            
            st.markdown(f"##### 💼 {t('资金总览')} ({t('期末余额')})")
            st.metric(t("资金合计"), f"{total_money:,.2f}")
            
            st.markdown(f"##### 💳 {t('各账户余额表')}")
            
            cols = ['期初余额', '本期收入', '本期支出', '期末余额']
            sum_row = pd.DataFrame(df_bal[cols].sum()).T
            sum_row['账户名称'] = '🟢 ' + t('合计')
            sum_row['科目编码'] = ''
            
            df_bal_show = pd.concat([df_bal, sum_row], ignore_index=True)
            for c in cols: df_bal_show[c] = df_bal_show[c].apply(clean_zero)

            # 余额表 (列名翻译)
            st.dataframe(
                df_bal_show,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "账户名称": st.column_config.TextColumn(label=t("账户名称"), width="medium"),
                    "科目编码": st.column_config.TextColumn(label=t("科目编码"), width="small"),
                    "期初余额": st.column_config.NumberColumn(label=t("期初余额"), format="%.2f"),
                    "本期收入": st.column_config.NumberColumn(label=t("本期收入"), format="%.2f"),
                    "本期支出": st.column_config.NumberColumn(label=t("本期支出"), format="%.2f"),
                    "期末余额": st.column_config.NumberColumn(label=t("期末余额"), format="%.2f"),
                }
            )
            st.divider()

        st.markdown(f"##### 📜 {t('单据流水')} ({len(df_det)})")
        if not df_det.empty:
            df_det['收入金额'] = df_det['收入金额'].apply(clean_zero)
            df_det['支出金额'] = df_det['支出金额'].apply(clean_zero)

            # 流水表 (列名翻译)
            st.dataframe(
                df_det,
                use_container_width=True,
                height=500,
                hide_index=True,
                column_config={
                    "日期": st.column_config.TextColumn(label=t("日期"), width="small"),
                    "账户名称": st.column_config.TextColumn(label=t("账户名称"), width="medium"),
                    "摘要": st.column_config.TextColumn(label=t("摘要"), width="large"),
                    "收入金额": st.column_config.NumberColumn(label=t("收入金额"), format="%.2f"),
                    "支出金额": st.column_config.NumberColumn(label=t("支出金额"), format="%.2f"),
                    "往来单位": st.column_config.TextColumn(label=t("往来单位"), width="medium"),
                    "经手人": st.column_config.TextColumn(label=t("经手人"), width="small"),
                    "单据编号": st.column_config.TextColumn(label=t("单据编号"), width="small"),
                }
            )
        else:
            st.info(t("无数据。"))