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
    st.markdown(f"#### 💸 {t('费用查询')}")

    if 'show_expense' not in st.session_state:
        st.session_state['show_expense'] = False

    if not st.session_state['show_expense']:
        c1, c2 = st.columns([2, 1])
        with c1:
            st.info(t("此报表包含敏感财务数据，请输入密码。"))
        with c2:
            pwd = st.text_input(t("解锁密码"), type="password", label_visibility="collapsed")
            if pwd:
                if pwd == SECRET_PASS:
                    st.session_state['show_expense'] = True
                    st.rerun()
                else:
                    st.error(t("密码错误"))
        return

    # --- 解锁后 ---
    
    c1, c2, c3, c4 = st.columns([1.5, 1.5, 2, 2])
    with c1:
        today = datetime.date.today()
        start_date = st.date_input(t("开始日期"), today.replace(day=1))
    with c2:
        end_date = st.date_input(t("结束日期"), today)
        
    with c3:
        try:
            sql_codes = "SELECT DISTINCT CAST([科目名称] AS NVARCHAR(100)) AS [科目名称] FROM [v_费用明细列表] ORDER BY [科目名称]"
            df_codes = run_query(conn, sql_codes)
            # 使用 t() 翻译“全部科目”
            code_list = [t("全部科目")] + df_codes['科目名称'].tolist()
        except:
            code_list = [t("全部科目")]
        
        selected_code = st.selectbox(t("科目筛选"), code_list)
        
    with c4:
        # 回车即查
        search_kw = st.text_input(t("搜索"), placeholder=t("搜索 (摘要/科目/凭证号)"))

    st.write("") 
    if st.button(t("查询"), type="primary"):
        st.session_state['exp_refresh'] = True

    s_date = start_date.strftime('%Y-%m-%d')
    e_date = end_date.strftime('%Y-%m-%d')
    
    sql = f"""
    SELECT 
        CONVERT(varchar(10), [业务日期], 120) AS [日期],
        [会计期间],
        [凭证编号],
        [科目编码],
        CAST([科目名称] AS NVARCHAR(200)) AS [科目名称],
        CAST([摘要内容] AS NVARCHAR(500)) AS [摘要内容],
        [借方金额_元]
    FROM [v_费用明细列表]
    WHERE [业务日期] BETWEEN '{s_date}' AND '{e_date}'
    ORDER BY [业务日期] DESC, [凭证编号] DESC
    """
    
    df = run_query(conn, sql)

    if not df.empty:
        # Python 过滤
        if selected_code != t("全部科目"):
            df = df[df['科目名称'] == selected_code]
            
        if search_kw:
            mask = df['摘要内容'].astype(str).str.contains(search_kw, case=False) | \
                   df['科目名称'].astype(str).str.contains(search_kw, case=False) | \
                   df['凭证编号'].astype(str).str.contains(search_kw, case=False)
            df = df[mask]

        if not df.empty:
            total_exp = df['借方金额_元'].sum()
            
            st.markdown(f"##### 📊 {t('费用概览')}")
            k1, k2 = st.columns(2)
            with k1: st.metric(t("期间总费用"), f"{total_exp:,.2f}")
            with k2: st.metric(t("笔数"), f"{len(df)}")
            st.divider()

            df['借方金额_元'] = df['借方金额_元'].apply(clean_zero)
            
            sum_row = pd.DataFrame(columns=df.columns)
            sum_row.loc[0] = {'日期': '🟢 ' + t('合计'), '借方金额_元': total_exp}
            
            df_display = pd.concat([df, sum_row], ignore_index=True)

            # 翻译列名
            st.dataframe(
                df_display,
                use_container_width=True,
                height=600,
                hide_index=True,
                column_config={
                    "日期": st.column_config.TextColumn(label=t("日期"), width="small"),
                    "会计期间": st.column_config.NumberColumn(label=t("会计期间"), format="%d", width="small"),
                    "凭证编号": st.column_config.TextColumn(label=t("凭证编号"), width="small"),
                    "科目编码": st.column_config.TextColumn(label=t("科目编码"), width="small"),
                    "科目名称": st.column_config.TextColumn(label=t("科目名称"), width="medium"),
                    "摘要内容": st.column_config.TextColumn(label=t("摘要"), width="large"),
                    "借方金额_元": st.column_config.NumberColumn(label=t("支出金额"), format="%.2f"),
                }
            )
        else:
            st.info(t("无数据。"))
    else:
        st.info(t("无数据。"))