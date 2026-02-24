# -*- coding: utf-8 -*-
import pandas as pd  # 已修正：之前错误的 import pd as pd
import streamlit as st
import datetime
import calendar
from modules.languages import t as T

# ==========================================
# 1. 内部数据库工具函数 (严禁使用 DATA)
# ==========================================
def run_erp_query(conn, sql):
    """
    执行 ERP 数据库查询，返回 DataFrame
    """
    try:
        return pd.read_sql(sql, conn)
    except Exception as e:
        st.error(f"SQL 查询异常: {str(e)}")
        return pd.DataFrame()

# ==========================================
# 2. 主页面显示逻辑
# ==========================================
def show(st, conn_erp, mysql_conf, current_country):
    
    # 【防串台探针】
    try:
        db_name = run_erp_query(conn_erp, "SELECT DB_NAME() AS db").iloc[0, 0]
    except:
        db_name = "Unknown"

    st.markdown(f"#### 🎯 {T('销售目标进度查询')} ({current_country} | 🗄️ {db_name})")

    # --- 1. 动态判断成品前缀 (对应 Ptype.typeid) ---
    country_upper = current_country.upper()
    # 乌干达为 00002，其余(尼日利亚/肯尼亚)为 00003
    type_pfx = "00002" if ("UGANDA" in country_upper or "乌干达" in country_upper) else "00003"

    # --- 2. 获取基础时间信息 ---
    today = datetime.date.today()
    curr_year, curr_month = today.year, today.month

    # --- 3. 读取目标视图 (统一后的 month_id 为整数, 列名为 total_local) ---
    #
    sql_budget = "SELECT * FROM monthly_budget ORDER BY month_id"
    budget_records_df = run_erp_query(conn_erp, sql_budget)
    
    if budget_records_df.empty:
        st.info(T("未读取到目标视图数据，请检查数据库配置"))
        return

    # --- 4. 提取 ERP 全年实际业绩 (核心修正) ---
    # 1. SUM(-Total) 翻转负数存储
    # 2. c.typeid 过滤成品分类
    with st.spinner(T("正在核算全年实际业绩...")):
        sql_actual = f"""
        SELECT 
            MONTH(d.Date) AS m_id,
            SUM(-s.Total) AS monthly_actual
        FROM Dlyndx d
        INNER JOIN DlySale s ON s.VchCode = d.VchCode
        INNER JOIN Ptype c ON s.PtypeId = c.typeid
        WHERE YEAR(d.Date) = {curr_year}
          AND d.VchType IN (11, 45) AND d.Draft = 2 AND d.RedWord = 'F'
          AND c.typeid LIKE '{type_pfx}%'
        GROUP BY MONTH(d.Date)
        """
        actual_raw_results = run_erp_query(conn_erp, sql_actual)
        actual_map = dict(zip(actual_raw_results['m_id'], actual_raw_results['monthly_actual'])) if not actual_raw_results.empty else {}

    # --- 5. 动态计算所有指标 (Python 内存引擎) ---
    perf_table_list = []
    # 确定货币标签
    curr_label = "UGX" if "UGANDA" in country_upper else ("NGN" if "NIGERIA" in country_upper else "LOCAL")

    for _, budget_row in budget_records_df.iterrows():
        m_id = int(budget_row['month_id']) # 匹配统一后的整数月份
        
        # 目标金额 (视图单位为“万”)
        val_base = float(budget_row['total_local'])
        val_stretch = float(budget_row.get('total_local_stretch', val_base))
        val_rmb = float(budget_row['total_rmb'])
        
        # 实际业绩 (元转为万)
        actual_wan = float(actual_map.get(m_id, 0.0)) / 10000.0
        
        # 时间日历计算
        _, month_days = calendar.monthrange(curr_year, m_id)
        if m_id < curr_month:
            remain_days, time_pct = 0, 100.0
        elif m_id == curr_month:
            remain_days = month_days - today.day
            time_pct = (today.day / month_days) * 100.0
        else:
            remain_days = month_days, 0.0
            remain_days, time_pct = month_days, 0.0
            
        # 进度与差额
        ach_rate = (actual_wan / val_base * 100.0) if val_base > 0 else 0.0
        gap_val = actual_wan - val_base 
        
        # 状态判定
        if m_id > curr_month: 
            status_tag = T("未开始")
        elif ach_rate >= time_pct: 
            status_tag = T("超额")
        else: 
            status_tag = T("滞后")
            
        # 剩余日均销量需求
        req_daily = (abs(gap_val) / remain_days) if (gap_val < 0 and remain_days > 0) else 0.0
        
        perf_table_list.append({
            T("月份"): f"{curr_year}-{m_id:02d}",
            T("RMB目标"): val_rmb,
            curr_label + T("目标"): val_base,
            curr_label + T("冲刺"): val_stretch,
            T("实际销售"): actual_wan,
            T("完成率"): ach_rate,
            T("月差额"): gap_val,
            T("月时间进度"): time_pct,
            T("月状态"): status_tag,
            T("月剩余天数"): remain_days,
            T("剩余天数平均销量"): req_daily
        })
        
    final_output_df = pd.DataFrame(perf_table_list)

    # --- 6. UI: 本月概况 ---
    st.markdown(f"##### 📅 {T('本月概况')}")
    curr_m_str = f"{curr_year}-{curr_month:02d}"
    curr_month_row = final_output_df[final_output_df[T('月份')] == curr_m_str]
    
    if not curr_month_row.empty:
        p_row = curr_month_row.iloc[0]
        m1, m2, m3, m4 = st.columns(4)
        
        # 已修正：通过预定义变量解决 f-string 引号嵌套冲突
        col_name_base = curr_label + T("目标")
        
        m1.metric(T("本月目标"), f"{p_row[col_name_base]:,.0f} W")
        m2.metric(T("实际销售"), f"{p_row[T('实际销售')]:,.2f} W", f"{p_row[T('月差额')]:,.2f} W")
        
        ach_val, time_val = p_row[T('完成率')], p_row[T('月时间进度')]
        m3.metric(T("完成率"), f"{ach_val:,.1f}%", f"{T('时间进度')}: {time_val:,.1f}%", 
                  delta_color="normal" if ach_val >= time_val else "off")
        
        if p_row[T('月剩余天数')] > 0:
            m4.metric(T("剩余天数需销"), f"{p_row[T('剩余天数平均销量')]:,.2f} W/Day", f"{T('剩')} {p_row[T('月剩余天_d') if '月剩余天_d' in p_row else '月剩余天数']:,.0f} {T('天')}")
        else:
            m4.metric(T("本月结束"), T("已结算"))

    st.divider()

    # --- 7. UI: 全年明细表 (带进度条) ---
    st.markdown(f"##### 📋 {T('全年明细表')}")
    st.dataframe(
        final_output_df,
        use_container_width=True, height=480, hide_index=True,
        column_config={
            T("完成率"): st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=120),
            T("实际销售"): st.column_config.NumberColumn(format="%.2f"),
            T("月差额"): st.column_config.NumberColumn(format="%.2f"),
            T("月时间进度"): st.column_config.NumberColumn(format="%.1f%%")
        }
    )