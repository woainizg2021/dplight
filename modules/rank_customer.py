import pandas as pd
import streamlit as st
from modules.languages import t

SECRET_PASS = "f888"

def run_query(conn, sql):
    try:
        return pd.read_sql(sql, conn)
    except Exception:
        return pd.DataFrame()

def show(st, conn):
    # 翻译标题
    st.markdown(f"#### 🏆 {t('客户销售排行榜')} ({t('月度')})")

    if 'show_cust_profit' not in st.session_state:
        st.session_state['show_cust_profit'] = False

    sql_months = """
        SELECT DISTINCT CAST([年月] AS NVARCHAR(50)) AS [年月], [月份排序] 
        FROM [v_客户销售排行榜] 
        ORDER BY [月份排序] DESC
    """
    try:
        df_months = run_query(conn, sql_months)
        month_list = df_months['年月'].tolist()
    except:
        month_list = []
        
    c1, c2, c3 = st.columns([1.5, 3, 1.5])
    with c1:
        # 翻译标签
        selected_month = st.selectbox(t("选择月份"), month_list, index=0 if month_list else None)
    
    with c2:
        # 翻译搜索框，回车即查
        search_kw = st.text_input(t("搜索"), placeholder=t("输入客户名称") + "...")

    # --- 敏感数据解锁 ---
    with c3:
        if not st.session_state['show_cust_profit']:
            pwd = st.text_input(t("查看毛利密码"), type="password", key="cust_pwd", placeholder=t("输入密码解锁"), label_visibility="collapsed")
            if pwd == SECRET_PASS:
                st.session_state['show_cust_profit'] = True
                st.rerun()
            elif pwd:
                st.toast(t("密码错误"), icon="❌")
        else:
            if st.button("🔓 " + t("已解锁 (点击隐藏)"), type="secondary", key="lock_cust"):
                st.session_state['show_cust_profit'] = False
                st.rerun()

    if selected_month:
        sql = f"""
        SELECT 
            CAST([客户名称] AS NVARCHAR(200)) AS [客户名称],
            [销售额_万元], 
            [成本_万元], 
            [毛利_万元], 
            [毛利率_百分比], 
            [销售额占比_百分比], 
            [毛利占比_百分比]
        FROM [v_客户销售排行榜]
        WHERE CAST([年月] AS NVARCHAR(50)) = '{selected_month}'
        ORDER BY [销售额_万元] DESC
        """
        
        df = run_query(conn, sql)

        if not df.empty:
            if search_kw:
                df = df[df['客户名称'].astype(str).str.contains(search_kw, case=False)]

            df.insert(0, '排名', range(1, 1 + len(df)))

            is_unlocked = st.session_state['show_cust_profit']
            
            base_cols = ["排名", "客户名称", "销售额_万元", "销售额占比_百分比"]
            profit_cols = ["毛利_万元", "毛利率_百分比", "毛利占比_百分比", "成本_万元"]
            
            final_cols = base_cols + profit_cols if is_unlocked else base_cols

            if not search_kw and len(df) >= 3:
                top1 = df.iloc[0]
                top2 = df.iloc[1]
                top3 = df.iloc[2]
                
                # 翻译看板
                st.markdown(f"##### 👑 {t('优质客户')}")
                k1, k2, k3, k4 = st.columns(4)
                
                with k1: st.metric(t("第一名"), top1['客户名称'], f"{top1['销售额_万元']:.2f}")
                with k2: st.metric(t("第二名"), top2['客户名称'], f"{top2['销售额_万元']:.2f}")
                with k3: st.metric(t("第三名"), top3['客户名称'], f"{top3['销售额_万元']:.2f}")
                
                with k4:
                    total_sales = df['销售额_万元'].sum()
                    if is_unlocked:
                        total_profit = df['毛利_万元'].sum()
                        st.metric(t("当月总毛利"), f"{total_profit:.2f}")
                    else:
                        st.metric(t("当月总销售"), f"{total_sales:.2f}")
                
                st.divider()

            # 翻译列名
            st.dataframe(
                df[final_cols], 
                use_container_width=True,
                height=700,
                hide_index=True,
                column_config={
                    "排名": st.column_config.NumberColumn(label=t("排名"), format="#%d", width="small"),
                    "客户名称": st.column_config.TextColumn(label=t("客户"), width="medium"),
                    
                    "销售额_万元": st.column_config.NumberColumn(
                        label=t("销售额"), format="%.2f", width="small"
                    ),
                    "销售额占比_百分比": st.column_config.ProgressColumn(
                        label=t("销售占比"), format="%.1f%%", min_value=0, max_value=100
                    ),
                    
                    # 敏感数据
                    "毛利_万元": st.column_config.NumberColumn(label=t("毛利"), format="%.2f", width="small"),
                    "毛利率_百分比": st.column_config.NumberColumn(label=t("毛利率"), format="%.1f%%"),
                    "毛利占比_百分比": st.column_config.NumberColumn(label=t("毛利占比"), format="%.1f%%"),
                    "成本_万元": st.column_config.NumberColumn(label=t("成本"), format="%.2f"),
                }
            )
        else:
            st.info(f"{selected_month} {t('暂无数据')}")
    else:
        st.info(t("暂无数据"))