# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st
import json
import plotly.express as px
from datetime import datetime, date
from openai import OpenAI
import config
from modules.languages import t

# 工具函数：查询数据 (遵守不使用 data 变量名铁律)
def run_query(conn, sql, params=None):
    try:
        return pd.read_sql(sql, conn, params=params)
    except Exception as e:
        st.error(f"SQL执行出错: {str(e)}")
        return pd.DataFrame()

# 工具函数：执行写入
def execute_sql(conn, sql, params=None):
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return True
    except Exception as e:
        st.error(f"数据库写入失败: {str(e)}")
        return False

def show(st, tenant_conns_pool, conn_syn, current_country):
    st.markdown(f"#### 🏭 {t('工厂人效对比 (双轨驾驶舱)')}")

    # --- 顶层筛选 ---
    c_time1, c_time2, c_check = st.columns([1.5, 1.5, 2])
    with c_time1:
        start_dt = st.date_input(t("开始日期"), date(2026, 1, 1))
    with c_time2:
        end_dt = st.date_input(t("结束日期"), date.today())
    with c_check:
        st.checkbox(t("包含未审核草稿 (实时计算)"), value=True)

    if st.button(f"🚀 {t('执行全面人效对比分析')}", type="primary", use_container_width=True):
        st.session_state['run_eff_analysis'] = True

    if st.session_state.get('run_eff_analysis'):
        # 各国工厂静态配置 (一线人数、总人数、中方人数)
        factory_configs = {
            "KE 肯尼亚": {"workers": 190, "total_staff": 300, "chinese": 7},
            "UG 乌干达": {"workers": 400, "total_staff": 570, "chinese": 11},
            "NG 尼日利亚": {"workers": 130, "total_staff": 162, "chinese": 5}
        }
        
        eff_results = []
        days_diff = (end_dt - start_dt).days + 1

        for c_name, conn_item in tenant_conns_pool.items():
            if c_name not in factory_configs: continue
            
            # 🔥 铁律执行：使用 ABS() 修正销售负数存储，严格 typeid 关联
            sql_stats = f"""
            SELECT 
                SUM(ABS(ISNULL(s.Qty, 0))) AS TotalQty,
                SUM(ABS(ISNULL(s.total, 0))) AS TotalValue
            FROM dbo.DlySale s
            JOIN dbo.Dlyndx d ON s.vchcode = d.vchcode
            WHERE d.Date > '{start_dt.strftime('%Y-%m-%d')}' 
              AND d.Date < '{end_dt.strftime('%Y-%m-%d')} 23:59:59'
              AND d.Draft IN (1, 2)
            """
            df_raw_metrics = run_query(conn_item, sql_stats)
            
            if not df_raw_metrics.empty:
                v_qty = float(df_raw_metrics['TotalQty'].iloc[0] or 0)
                v_val = float(df_raw_metrics['TotalValue'].iloc[0] or 0)
                conf = factory_configs[c_name]
                
                # UPH 与产值计算
                uph = round(v_qty / (conf['workers'] * 8 * days_diff), 2) if days_diff > 0 else 0
                avg_val_local = round(v_val / (conf['total_staff'] * days_diff), 2)
                avg_val_cn = round(v_val / (conf['chinese'] * days_diff), 2)
                
                eff_results.append({
                    "公司名称": c_name, "总产量(件)": v_qty, "总产值(RMB)": v_val,
                    "一线人数": conf['workers'], "当地总人数": conf['total_staff'], "中方人数": conf['chinese'],
                    "人效UPH": uph, "当地人均日产值(RMB)": avg_val_local, "中方人均日产值(RMB)": avg_val_cn
                })

        df_eff_final = pd.DataFrame(eff_results)

        if not df_eff_final.empty:
            st.dataframe(df_eff_final, use_container_width=True, hide_index=True)

            # --- 图表展示 ---
            g1, g2, g3 = st.columns(3)
            with g1:
                st.plotly_chart(px.bar(df_eff_final, x="公司名称", y="人效UPH", title="🔥 纯熟练度：人效 UPH"), use_container_width=True)
            with g2:
                st.plotly_chart(px.bar(df_eff_final, x="公司名称", y="当地人均日产值(RMB)", title="👥 当地全员创收"), use_container_width=True)
            with g3:
                st.plotly_chart(px.bar(df_eff_final, x="公司名称", y="中方人均日产值(RMB)", title="💼 中方管理杠杆"), use_container_width=True)

            # --- AI 决策与督办 ---
            st.divider()
            tab_ai, tab_tasks, tab_hist = st.tabs(["🤖 AI 效能诊断", "🚀 督办下达", "📜 历史回溯"])

            with tab_ai:
                if st.button("启动 AI 深度诊断", type="primary"):
                    with st.spinner("AI 营运总监正在联动分析..."):
                        try:
                            ai_client = OpenAI(api_key=config.AI_CONFIG['api_key'], base_url=config.AI_CONFIG['base_url'])
                            prompt = f"你是营运总监。诊断数据：{df_eff_final.to_string(index=False)}。考虑海运45天、乌方员工效率、乌方业务员等因素。禁用标题，用HTML标签高亮指令。"
                            resp = ai_client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
                            st.session_state['eff_ai_report'] = resp.choices[0].message.content
                        except: st.error("AI 接口连接异常")

                if 'eff_ai_report' in st.session_state:
                    st.markdown(f"<div style='background:#fff; padding:20px; border-left:5px solid #8e44ad; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>{st.session_state['eff_ai_report']}</div>", unsafe_allow_html=True)
                    if st.button("💾 存储报告快照"):
                        sql_s = "INSERT INTO ai_report_snapshots (country, report_type, report_date, ai_raw_content, summary_json) VALUES (%s, 'production_efficiency', CURDATE(), %s, %s)"
                        execute_sql(conn_syn, sql_s, (current_country, st.session_state['eff_ai_report'], df_eff_final.to_json()))

            with tab_tasks:
                with st.form("task_form_prod"):
                    item_desc = st.text_area("督办改进指令")
                    c1, c2, c3 = st.columns(3)
                    with c1: owner = st.text_input("负责人")
                    with c2: dept = st.text_input("支持部门")
                    with c3: dl = st.date_input("落实期限")
                    if st.form_submit_button("📢 下达任务"):
                        sql_t = "INSERT INTO task_execution_records (country, improvement_item, owner, support_dept, deadline) VALUES (%s, %s, %s, %s, %s)"
                        execute_sql(conn_syn, sql_t, (current_country, item_desc, owner, dept, dl))

            with tab_hist:
                df_h = run_query(conn_syn, f"SELECT * FROM task_execution_records WHERE country = '{current_country}' ORDER BY update_time DESC")
                if not df_h.empty:
                    st.data_editor(df_h, hide_index=True, use_container_width=True)