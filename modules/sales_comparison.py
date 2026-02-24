# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import pymssql 
import datetime
import calendar
import altair as alt
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
import config
from modules.languages import t as T

# ==========================================
# 1. 核心性能抓取引擎 (严禁使用 DATA 变量)
# ==========================================

def fetch_erp_perf_package(tenant_key, creds, m_val, y_val):
    """
    深度穿透：基于统一后的整数 month_id 匹配目标
    计算准则：Actual = SUM(-Total)，过滤 c.typeid
    """
    day_start = f"{y_val}-{m_val:02d}-01"
    _, last_day_num = calendar.monthrange(y_val, m_val)
    day_end = f"{y_val}-{m_val:02d}-{last_day_num}"

    biz_rules = creds.get('business_rules', {})
    type_pfx = biz_rules.get('finished_types', ['00003'])[0]
    
    perf_payload = {
        'key': tenant_key, 'name': creds['name'], 'currency': creds['currency'],
        'tgt_val': 0.0, 'act_val': 0.0, 'status': 'OK'
    }

    try:
        conn = pymssql.connect(
            server=config.ERP_HOST, port=config.ERP_PORT,
            user=creds['user'], password=creds['pass'],
            database=creds['db'], charset='utf8', timeout=10
        )
        with conn.cursor() as cursor:
            # --- A. 抓取目标 ---
            sql_tgt = f"SELECT TOP 1 total_local FROM monthly_budget WHERE month_id = {m_val}"
            try:
                cursor.execute(sql_tgt)
                row_t = cursor.fetchone()
                if row_t:
                    perf_payload['tgt_val'] = float(row_t[0]) * 10000.0
            except:
                perf_payload['status'] = "View Col Error"

            # --- B. 销售实际 ---
            sql_act = f"""
            SELECT ISNULL(SUM(-b.Total), 0)
            FROM Dlyndx a
            INNER JOIN DlySale b ON a.VchCode = b.VchCode
            INNER JOIN Ptype c ON b.PtypeId = c.typeId
            WHERE a.VchType IN (11, 45) AND a.Draft = 2 AND a.RedWord = 'F'
              AND a.Date >= '{day_start}' AND a.Date <= '{day_end}'
              AND c.typeid LIKE '{type_pfx}%'
            """
            cursor.execute(sql_act)
            row_a = cursor.fetchone()
            perf_payload['act_val'] = float(row_a[0]) if row_a else 0.0

        conn.close()
    except Exception as e:
        perf_payload['status'] = f"Err: {str(e)[:15]}"
    
    return perf_payload

# ==========================================
# 2. 界面展示 (重构为年份+月份选择 & AI深度集成)
# ==========================================

def show(st, authorized_keys):
    st.markdown(f"### 🏆 {T('全球综合业绩对标')} (PK)")

    # --- 1. 顶部控制台重构：加入 AI 按钮与免责提示 ---
    c_y, c_m, c_ai_panel = st.columns([2, 2, 6])
    today = datetime.date.today()
    
    with c_y:
        sel_year = st.selectbox(T("年份") if "年份" in st.session_state else "Year", [2025, 2026, 2027], index=1)
    with c_m:
        month_list = list(range(1, 13))
        sel_month = st.selectbox(T("选择日期"), month_list, index=today.month - 1)
    
    # 在红框位置布置 AI 解读按钮
    with c_ai_panel:
        st.markdown("<div style='padding-top: 28px;'></div>", unsafe_allow_html=True) # 占位对齐下拉框
        btn_col, tip_col = st.columns([4, 6])
        with btn_col:
            run_ai = st.button("🤖 AI智能业绩解读", type="secondary", use_container_width=True)
        with tip_col:
            st.markdown("<div style='padding-top: 8px; color: #888; font-size: 0.85rem;'>💡 提示：AI智能解读，不能作为决策依据，仅作参考。</div>", unsafe_allow_html=True)

    # --- 2. 进度计算与多线程数据并发抓取 ---
    _, days_in_m = calendar.monthrange(sel_year, sel_month)
    if sel_month == today.month and sel_year == today.year:
        time_ratio = (today.day / days_in_m * 100)
    else:
        time_ratio = 100.0 if (sel_year < today.year or (sel_year == today.year and sel_month < today.month)) else 0.0

    active_configs = {k: v for k, v in config.ERP_CREDENTIALS.items() if k in authorized_keys}
    perf_results_stack = []
    
    with st.spinner(T("刷新数据")):
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(fetch_erp_perf_package, k, v, sel_month, sel_year) for k, v in active_configs.items()]
            for f in as_completed(futures):
                perf_results_stack.append(f.result())

    h_tenant = T("账套")
    h_achieve = T("达成率")
    h_actual = T("销售金额") + "(W)"
    h_target = T("目标(万)")
    h_currency = T("货币单位")

    ui_rows = []
    for r in perf_results_stack:
        act_w = r['act_val'] / 10000.0
        tgt_w = r['tgt_val'] / 10000.0
        ach = (act_w / tgt_w * 100) if tgt_w > 0 else 0
        
        ui_rows.append({
            h_tenant: r['name'], h_achieve: ach, h_actual: act_w,
            h_target: tgt_w, h_currency: r['currency'], 'Status': r['status']
        })

    # ================== AI 业绩深度解读逻辑 ==================
    if run_ai and ui_rows:
        results_df_temp = pd.DataFrame(ui_rows).sort_values(h_achieve, ascending=False)
        with st.spinner("AI 全球销售总监正在诊断各战区业绩，请稍候..."):
            try:
                ai_client = OpenAI(api_key=config.AI_CONFIG['api_key'], base_url=config.AI_CONFIG['base_url'])
                
                # 剥离多余字段，只给 AI 喂核心 PK 数据
                perf_str = results_df_temp[[h_tenant, h_target, h_actual, h_achieve]].to_string(index=False)
                
                prompt = f"""
                你是Dplight跨国照明工厂的全球销售与运营总监。请根据系统刚提取的各跨国战区【当月销售业绩PK】数据，写一份【客观、专业、直击痛点且具有执行力】的经营分析报告。
                数据如下：
                1. 【当月时间进度】：{time_ratio:.1f}% （这是核心评判基准！如果某公司的达成率显著低于时间进度，说明业绩拖后腿了；如果超过，说明进展健康。）
                2. 【各战区业绩达成详情】（金额单位：万）：
                {perf_str}

                要求：
                1. 【人设与语气】：语言要干练、一针见血，带有管理者的威严。对事要狠，对人要和（绝对禁用“极差”、“垫底”、“一塌糊涂”等负面或伤人的词汇）。用客观数据说话，直接表扬超前的战区，点出暂时落后的战区。
                2. 给出强有力的销售与运营指令（例如：建议关注经营历程的单据明细、督促核实库存深度、加快渠道下沉、或呼吁总部资源支援）。
                3. 【排版铁律】：**绝对禁止使用任何级别的大标题（即全面禁用 # 或 ## 语法）**。通篇使用常规加粗文字，采用无序列表结构。
                4. 【视觉高亮铁律】：对于文中的**超前或落后的关键数值、具体的督办指令**，你必须使用HTML标签 `<span style='background-color: #ffe58f; color: #000; font-weight: bold; padding: 2px 4px; border-radius: 3px;'>你要高亮的重点内容</span>` 进行背景高亮标识！
                """
                
                response = ai_client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7
                )
                
                ai_content = response.choices[0].message.content
                st.markdown(f"""
                <div style="background-color: #ffffff; color: #000000; padding: 20px 24px; border-radius: 8px; border-left: 4px solid #17a2b8; box-shadow: 0 2px 8px rgba(0,0,0,0.08); font-size: 0.95rem; line-height: 1.6; margin-bottom: 20px; margin-top: 10px;">
                    <div style="font-size: 1.1rem; font-weight: bold; margin-bottom: 12px; color: #222; display: flex; align-items: center;">
                        <span style="margin-right: 8px;">🤖</span> 全球销售总监业绩诊断
                    </div>
                    {ai_content}
                </div>
                """, unsafe_allow_html=True)
                
            except Exception as e:
                st.error(f"🤖 AI 调用出现异常，请稍后重试: {e}")

    # --- 3. 可视化图表与数据表格 ---
    if ui_rows:
        results_df = pd.DataFrame(ui_rows).sort_values(h_achieve, ascending=False)
        st.divider()
        results_df['Color'] = results_df[h_achieve].apply(lambda x: '#2ecc71' if x >= time_ratio else '#e74c3c')
        
        pk_chart = alt.Chart(results_df).mark_bar().encode(
            x=alt.X(h_tenant, sort=None, title=''),
            y=alt.Y(h_achieve, title=h_achieve + ' %'),
            color=alt.Color('Color', scale=None),
            tooltip=[h_tenant, h_achieve, h_actual]
        ).properties(height=350)
        
        # 橙色时间进度参考线
        ref_line = alt.Chart(pd.DataFrame({'y': [time_ratio]})).mark_rule(color='orange', strokeDash=[5,5]).encode(y='y')
        st.altair_chart(pk_chart + ref_line, use_container_width=True)

        st.dataframe(
            results_df, hide_index=True, use_container_width=True,
            column_config={
                h_achieve: st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=120),
                h_actual: st.column_config.NumberColumn(format="%,.2f"),
                h_target: st.column_config.NumberColumn(format="%,.2f")
            }
        )