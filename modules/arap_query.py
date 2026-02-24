import pandas as pd
import streamlit as st
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
    st.markdown(f"#### 💰 {t('应收款查询')}")

    if 'show_arap' not in st.session_state:
        st.session_state['show_arap'] = False

    if not st.session_state['show_arap']:
        c1, c2 = st.columns([2, 1])
        with c1:
            st.info(t("此报表包含敏感财务数据，请输入密码。"))
        with c2:
            pwd = st.text_input(t("解锁密码"), type="password", label_visibility="collapsed")
            if pwd:
                if pwd == SECRET_PASS:
                    st.session_state['show_arap'] = True
                    st.rerun()
                else:
                    st.error(t("密码错误"))
        return

    # --- 解锁后 ---

    c1, c2, c3 = st.columns([2, 1.5, 1])
    with c1:
        # 回车即查
        search_kw = st.text_input(t("搜索"), placeholder=t("输入客户名称后回车..."))
    with c2:
        # 自动刷新
        show_all = st.checkbox(t("显示已结清客户 (余额为0)"), value=False)
    with c3:
        if st.button("🔒 " + t("锁定")):
            st.session_state['show_arap'] = False
            st.rerun()

    sql = """
    SELECT 
        CAST([客户名称] AS NVARCHAR(200)) AS [客户名称],
        [期初应收],
        [本期新增],
        [本期减少],
        [期末应收]
    FROM [v_应收应付]
    ORDER BY [期末应收] DESC
    """
    
    df = run_query(conn, sql)

    if not df.empty:
        # Python 过滤
        if search_kw:
            df = df[df['客户名称'].astype(str).str.contains(search_kw, case=False)]
        
        if not show_all:
            df = df[abs(df['期末应收']) > 0.01]

        # 汇总看板
        total_ar = df['期末应收'].sum()
        total_income = df['本期减少'].sum()
        
        st.markdown(f"##### 📊 {t('资金概况')}")
        k1, k2, k3 = st.columns(3)
        with k1: st.metric(t("当前总欠款"), f"{total_ar:,.2f}")
        with k2: st.metric(t("本期已回款"), f"{total_income:,.2f}")
        with k3: st.metric(t("欠款客户数"), f"{len(df)}")
        st.divider()

        # 数据清洗
        num_cols = ['期初应收', '本期新增', '本期减少', '期末应收']
        total_row = pd.DataFrame(df[num_cols].sum()).T
        total_row['客户名称'] = '🟢 ' + t('合计')
        
        for col in num_cols: df[col] = df[col].apply(clean_zero)
        for col in num_cols: total_row[col] = total_row[col].apply(clean_zero)

        df_display = pd.concat([df, total_row], ignore_index=True)

        # 翻译列名
        st.dataframe(
            df_display,
            use_container_width=True,
            height=700,
            hide_index=True,
            column_config={
                "客户名称": st.column_config.TextColumn(label=t("客户"), width="medium"),
                "期初应收": st.column_config.NumberColumn(label=t("期初余额"), format="%.2f"),
                "本期新增": st.column_config.NumberColumn(label=t("本期收入"), format="%.2f"), # 这里语境是应收增加
                "本期减少": st.column_config.NumberColumn(label=t("收回欠款"), format="%.2f"),
                "期末应收": st.column_config.NumberColumn(label=t("期末余额"), format="%.2f"),
            }
        )
    else:
        st.info(t("无数据。"))