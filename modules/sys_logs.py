import pandas as pd
import streamlit as st
import pymysql
from modules.languages import t

# 管理员密码
SECRET_PASS = "admin888" 

def get_logs(mysql_conf, limit=100):
    try:
        conn = pymysql.connect(
            host=mysql_conf["host"], port=mysql_conf["port"],
            user=mysql_conf["user"], 
            password=mysql_conf["password"], # <--- 修正点：用 password
            database="erp_status_db", charset='utf8mb4'
        )
        
        sql = f"""
        SELECT 
            access_time, ip_address, country_selected, page_visited, user_agent
        FROM access_logs
        ORDER BY access_time DESC
        LIMIT {limit}
        """
        
        df = pd.read_sql(sql, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame()

def show(st, mysql_conf):
    st.markdown(f"#### 🛡️ {t('系统日志')}")

    if 'show_logs' not in st.session_state:
        st.session_state['show_logs'] = False

    if not st.session_state['show_logs']:
        c1, c2 = st.columns([2, 1])
        with c1: st.warning(t("访问受限"))
        with c2:
            pwd = st.text_input(t("解锁密码"), type="password", key="log_pwd", label_visibility="collapsed")
            if pwd:
                if pwd == SECRET_PASS:
                    st.session_state['show_logs'] = True
                    st.rerun()
                else:
                    st.error(t("密码错误"))
        return

    # --- 解锁后 ---
    
    c1, c2, c3 = st.columns([1, 3, 1])
    with c1:
        limit_num = st.selectbox(t("显示条数"), [50, 100, 200, 500], index=1)
    with c2: st.empty()
    with c3:
        if st.button("🔄 " + t("刷新数据")):
            st.rerun()

    df = get_logs(mysql_conf, limit_num)

    if not df.empty:
        total_visits = len(df)
        unique_ips = df['ip_address'].nunique()
        top_page = df['page_visited'].mode()[0] if not df.empty else "None"

        k1, k2, k3 = st.columns(3)
        with k1: st.metric(t("最近访问量"), f"{total_visits}")
        with k2: st.metric(t("独立访客 (IP)"), f"{unique_ips}")
        with k3: st.metric(t("最热报表"), top_page)
        
        st.divider()

        st.dataframe(
            df,
            use_container_width=True,
            height=600,
            hide_index=True,
            column_config={
                "access_time": st.column_config.DatetimeColumn(label=t("时间"), format="YYYY-MM-DD HH:mm:ss"),
                "ip_address": st.column_config.TextColumn(label=t("IP地址"), width="small"),
                "country_selected": st.column_config.TextColumn(label=t("账套"), width="small"),
                "page_visited": st.column_config.TextColumn(label=t("访问页面"), width="medium"),
                "user_agent": st.column_config.TextColumn(label=t("设备信息"), width="large"),
            }
        )
    else:
        st.info(t("暂无数据"))