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
    st.markdown(f"#### 🏆 {t('业务员销售排行榜')}")

    if 'show_salesman_profit' not in st.session_state:
        st.session_state['show_salesman_profit'] = False

    sql_months = """
        SELECT DISTINCT CAST([月份] AS NVARCHAR(50)) AS [月份]
        FROM [v_业务员销售排行榜] 
        ORDER BY [月份] DESC
    """
    try:
        df_months = run_query(conn, sql_months)
        month_list = df_months['月份'].tolist()
    except:
        month_list = []
        
    c1, c2, c3 = st.columns([1.5, 3, 1.5])
    with c1:
        # 翻译标签
        selected_month = st.selectbox(t("选择月份"), month_list, index=0 if month_list else None)
    
    with c2:
        # 翻译搜索框，回车即查
        search_kw = st.text_input(t("搜索"), placeholder=t("输入姓名") + "...")

    # --- 敏感数据解锁 ---
    with c3:
        if not st.session_state['show_salesman_profit']:
            pwd = st.text_input(t("查看毛利密码"), type="password", key="salesman_pwd", placeholder=t("输入密码解锁"), label_visibility="collapsed")
            if pwd == SECRET_PASS:
                st.session_state['show_salesman_profit'] = True
                st.rerun()
            elif pwd:
                st.toast(t("密码错误"), icon="❌")
        else:
            if st.button("🔓 " + t("已解锁 (点击隐藏)"), type="secondary", key="lock_salesman"):
                st.session_state['show_salesman_profit'] = False
                st.rerun()

    if selected_month:
        sql = f"""
        SELECT 
            CAST([业务员] AS NVARCHAR(100)) AS [业务员],
            [销售额合计_不含税_万],
            [成本合计_万],
            [毛利合计_万],
            [毛利率_百分比]
        FROM [v_业务员销售排行榜]
        WHERE CAST([月份] AS NVARCHAR(50)) = '{selected_month}'
        ORDER BY [销售额合计_不含税_万] DESC
        """
        
        df = run_query(conn, sql)

        if not df.empty:
            if search_kw:
                df = df[df['业务员'].astype(str).str.contains(search_kw, case=False)]

            df.insert(0, '排名', range(1, 1 + len(df)))

            is_unlocked = st.session_state['show_salesman_profit']
            
            base_cols = ["排名", "业务员", "销售额合计_不含税_万"]
            profit_cols = ["毛利合计_万", "毛利率_百分比", "成本合计_万"]
            
            final_cols = base_cols + profit_cols if is_unlocked else base_cols

            if not search_kw and len(df) >= 3:
                top1 = df.iloc[0]
                top2 = df.iloc[1]
                top3 = df.iloc[2]
                
                # 翻译看板
                st.markdown(f"##### 👑 {t('销售精英')}")
                k1, k2, k3, k4 = st.columns(4)
                
                with k1: st.metric(t("冠军"), top1['业务员'], f"{top1['销售额合计_不含税_万']:.2f}")
                with k2: st.metric(t("亚军"), top2['业务员'], f"{top2['销售额合计_不含税_万']:.2f}")
                with k3: st.metric(t("季军"), top3['业务员'], f"{top3['销售额合计_不含税_万']:.2f}")
                
                with k4:
                    total_sales = df['销售额合计_不含税_万'].sum()
                    if is_unlocked:
                        total_profit = df['毛利合计_万'].sum()
                        avg_margin = (total_profit / total_sales * 100) if total_sales > 0 else 0
                        st.metric(t("全员总毛利"), f"{total_profit:.2f}", f"{t('平均毛利')} {avg_margin:.1f}%")
                    else:
                        st.metric(t("全员总销售"), f"{total_sales:.2f}")
                
                st.divider()

            if not df.empty:
                max_sales = df['销售额合计_不含税_万'].max()
                if max_sales > 0:
                    df['业绩条'] = df['销售额合计_不含税_万'] / max_sales * 100
                else:
                    df['业绩条'] = 0
                
                if '业绩条' not in final_cols:
                    # 插入到销售额后面
                    final_cols.insert(3, '业绩条')

            # 翻译列名配置
            st.dataframe(
                df[final_cols],
                use_container_width=True,
                height=700,
                hide_index=True,
                column_config={
                    "排名": st.column_config.NumberColumn(label=t("排名"), format="#%d", width="small"),
                    "业务员": st.column_config.TextColumn(label=t("业务员"), width="medium"),
                    
                    "销售额合计_不含税_万": st.column_config.NumberColumn(
                        label=t("销售额"), format="%.2f", width="small"
                    ),
                    
                    "业绩条": st.column_config.ProgressColumn(
                        label=t("业绩贡献"), format="%.0f%%", min_value=0, max_value=100
                    ),
                    
                    # 敏感数据
                    "毛利合计_万": st.column_config.NumberColumn(label=t("毛利"), format="%.2f"),
                    "毛利率_百分比": st.column_config.NumberColumn(label=t("毛利率"), format="%.1f%%"),
                    "成本合计_万": st.column_config.NumberColumn(label=t("成本"), format="%.2f"),
                }
            )
        else:
            st.info(f"{selected_month} {t('暂无数据')}")
    else:
        st.info(t("暂无数据"))