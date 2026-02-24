import pandas as pd
import streamlit as st
import datetime
import calendar
from modules.languages import t

def run_query(conn, sql):
    try:
        return pd.read_sql(sql, conn)
    except Exception as e:
        st.error(f"⚠️ 数据载入失败: {str(e)}")
        return pd.DataFrame()

def show(st, conn):
    st.markdown(f"#### 🏭 {t('生产目标进度查询')} ({t('SKU 汇总')})")

    # --- 1. 筛选与搜索区 ---
    c1, c2, c3 = st.columns([1.5, 3, 1])
    with c1:
        current_month = datetime.date.today().month
        month_options = list(range(1, 13))
        selected_month = st.selectbox(t("选择月份"), month_options, index=current_month-1, format_func=lambda x: f"{x} {t('月')}")
    
    with c2:
        search_kw = st.text_input(t("搜索"), placeholder=t("输入产品名称或大类区域") + "...")

    with c3:
        st.write("")
        if st.button(t("查询"), type="primary", key="prod_btn"):
            st.session_state['prod_refresh'] = True

    # --- 2. 构造 SQL (整合生产、库存、销售) ---
    sql = f"""
    SELECT 
        base.[大类], base.[存货名称],
        base.[门市仓库_CTN], base.[辽沈成品仓_CTN], base.[合计库存_CTN],
        ISNULL(sales.[2025全年销量_箱], 0) AS [25销],
        ISNULL(sales.[2026全年销量_箱], 0) AS [26销],
        ISNULL(sales.[当月销量_箱], 0) AS [月销],
        base.[2026全年目标_CTN] AS [年目标],
        base.[2026年累计生产_CTN] AS [年实际],
        CAST(CASE WHEN base.[2026全年目标_CTN] = 0 THEN 0 
             ELSE (base.[2026年累计生产_CTN] * 1.0 / base.[2026全年目标_CTN]) * 100 END AS DECIMAL(10,2)) AS [年完成率],
        detail.[目标箱数] AS [月目标], detail.[实际箱数] AS [月实际],
        detail.[差额] AS [月差额], detail.[完成率] AS [月完成率],
        base.[typeid]
    FROM [v_dplight_scmbjdb] base
    INNER JOIN [v_生产目标进度_sku明细] detail ON base.[typeid] = detail.[typeid]
    LEFT JOIN [v_dplight_rx32xsxs] sales ON base.[typeid] = sales.[typeid]
    WHERE detail.[月份数字] = {selected_month}
    ORDER BY detail.[实际箱数] DESC
    """
    
    df = run_query(conn, sql)

    if not df.empty:
        # 搜索过滤
        if search_kw:
            df = df[(df['存货名称'].str.contains(search_kw, case=False, na=False)) | 
                    (df['大类'].str.contains(search_kw, case=False, na=False))]

        # --- 3. 核心逻辑处理 (序号 + 状态翻译) ---
        df.insert(0, '序号', range(1, len(df) + 1))
        
        today = datetime.date.today()
        _, days_in_month = calendar.monthrange(today.year, today.month)
        
        # 计算时间进度
        if selected_month < today.month: time_progress = 100.0
        elif selected_month > today.month: time_progress = 0.0
        else: time_progress = (today.day / days_in_month) * 100

        def get_monthly_status(rate):
            if selected_month > today.month: return t("未开始")
            return t("超额") if rate >= time_progress else t("滞后")
        df['月状态'] = df['月完成率'].apply(get_monthly_status)

        # --- 4. 异常指标计算 (用于红框汇总和高亮) ---
        # A. 整体汇总 (定义变量解决 NameError)
        total_target = df['月目标'].sum()
        total_actual = df['月实际'].sum()
        total_rate = (total_actual / total_target * 100) if total_target > 0 else 0

        # B. 每日需追赶 (今日起每日需产量)
        days_left = max(1, days_in_month - today.day + 1) if selected_month == today.month else days_in_month
        daily_needed = max(0, (total_target - total_actual) / days_left) if selected_month >= today.month else 0
        
        # C. 重点款滞后 (25年销量Top10且目前滞后的ID)
        top_10_ids = df.nlargest(10, '25销')['typeid'].tolist()
        pri_lag_ids = df[(df['typeid'].isin(top_10_ids)) & (df['月状态'] == t("滞后"))]['typeid'].tolist()
        
        # D. 产销倒挂 (产量 < 销量)
        gap_ids = df[(df['月实际'] < df['月销']) & (df['月目标'] > 0)]['typeid'].tolist()
        
        # E. 0 库存 (合计库存 <= 0)
        zero_stock_ids = df[df['合计库存_CTN'] <= 0]['typeid'].tolist()
        
        # F. 0 生产 (月产为0)
        zero_prod_ids = df[(df['月实际'] <= 0) & (df['月目标'] > 0)]['typeid'].tolist()

        # --- 5. 顶部概况 & 鞭策性异常统计 ---
        st.markdown(f"##### 📊 {selected_month} {t('月生产概况')}")
        k1, k2, k3 = st.columns(3)
        with k1: st.metric(t("总目标箱数"), f"{total_target:,.0f} {t('箱')}")
        with k2: st.metric(t("实际完成"), f"{total_actual:,.0f} {t('箱')}", f"{total_actual - total_target:,.0f}")
        with k3:
            state_color = "normal" if total_rate >= time_progress else "off"
            st.metric(t("整体完成率"), f"{total_rate:.1f}%", f"{t('进度')}: {time_progress:.1f}%", delta_color=state_color)

        st.write("")
        m1, m2, m3, m4, m5 = st.columns([1.2, 1, 1, 1, 1])
        with m1:
            st.markdown(f"📅 **{t('每日需产')}**: `{daily_needed:,.0f}`")
            st.caption("今日起每日最低产出量")
        with m2:
            st.markdown(f"🔥 **{t('重点款滞后')}**: :red[`{len(pri_lag_ids)}`]")
            st.caption("25年Top10销量的滞后款")
        with m3:
            st.markdown(f"🔄 **{t('产销倒挂')}**: :orange[`{len(gap_ids)}`]")
            st.caption("本月产量低于销量型号")
        with m4:
            st.markdown(f"🚨 **{t('0 库存')}**: :violet[`{len(zero_stock_ids)}`]")
            st.caption("合计库存为0或负数款")
        with m5:
            st.markdown(f"🚫 **{t('0 生产')}**: :blue[`{len(zero_prod_ids)}`]")
            st.caption("本月有目标但未开工")

        # --- 6. 交互高亮开关 ---
        st.write("")
        sw1, sw2, sw3, sw4 = st.columns(4)
        with sw1: h_pri = st.toggle(t("高亮重点滞后"), value=False, key="h1")
        with sw2: h_gap = st.toggle(t("高亮产销倒挂"), value=False, key="h2")
        with sw3: h_stock = st.toggle(t("高亮0库存款"), value=False, key="h3")
        with sw4: h_prod = st.toggle(t("高亮0生产款"), value=False, key="h4")

        st.divider()

        # --- 7. 多色上色逻辑 (统一左对齐) ---
        def apply_multi_color(row):
            base_style = 'text-align: left;'
            # 优先级：重点款滞后 > 0库存 > 产销倒挂 > 0生产
            if h_pri and row['typeid'] in pri_lag_ids:
                return [base_style + 'background-color: #fff0f0; color: #d63031; font-weight: bold;'] * len(row)
            if h_stock and row['typeid'] in zero_stock_ids:
                return [base_style + 'background-color: #f3f0ff; color: #7950f2; font-weight: bold;'] * len(row)
            if h_gap and row['typeid'] in gap_ids:
                return [base_style + 'background-color: #fff9db; color: #f08c00; font-weight: bold;'] * len(row)
            if h_prod and row['typeid'] in zero_prod_ids:
                return [base_style + 'background-color: #e3fafc; color: #0b7285; font-weight: bold;'] * len(row)
            return [base_style] * len(row)

        styled_df = df.style.apply(apply_multi_color, axis=1)
        
        st.dataframe(
            styled_df,
            use_container_width=True,
            height=600,
            hide_index=True,
            column_order=["序号", "大类", "存货名称", "门市仓库_CTN", "辽沈成品仓_CTN", "合计库存_CTN", 
                          "25销", "26销", "月销", "年目标", "年实际", "年完成率", 
                          "月目标", "月实际", "月差额", "月完成率", "月状态"],
            column_config={
                "序号": st.column_config.NumberColumn(label="#", width=10),
                "大类": st.column_config.TextColumn(label=t("大类"), width=70),
                "存货名称": st.column_config.TextColumn(label=t("产品名称"), width=110),
                "门市仓库_CTN": st.column_config.NumberColumn(label=t("门市"), format="%d", width=40),
                "辽沈成品仓_CTN": st.column_config.NumberColumn(label=t("辽沈"), format="%d", width=40),
                "合计库存_CTN": st.column_config.NumberColumn(label=t("总库"), format="%d", width=40),
                "25销": st.column_config.NumberColumn(label=t("25年销"), format="%d", width=45),
                "26销": st.column_config.NumberColumn(label=t("26年销"), format="%d", width=45),
                "月销": st.column_config.NumberColumn(label=t("月销"), format="%d", width=45),
                "年目标": st.column_config.NumberColumn(label=t("年产目标"), format="%d", width=55),
                "年实际": st.column_config.NumberColumn(label=t("年实产"), format="%d", width=55),
                "年完成率": st.column_config.NumberColumn(label=t("年产率%"), format="%.1f%%", width=35),
                "月目标": st.column_config.NumberColumn(label=t("月产目标"), format="%d", width=55),
                "月实际": st.column_config.NumberColumn(label=t("月实产"), format="%d", width=55),
                "月差额": st.column_config.NumberColumn(label=t("月差"), format="%d", width=45),
                "月完成率": st.column_config.ProgressColumn(label=t("月进度"), format="%.1f%%", min_value=0, max_value=120, width="small"),
                "月状态": st.column_config.TextColumn(label=t("状态"), width=45),
            }
        )
    else:
        st.info(f"{selected_month} {t('暂无数据')}")