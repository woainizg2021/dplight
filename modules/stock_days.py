# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st
from modules.languages import t as T  # 统一使用 T

# --- 缓存函数 (TTL=3600秒/1小时) ---
# 已修正：严禁使用 data 作为变量名
@st.cache_data(ttl=3600, show_spinner=False) 
def get_cached_records(_conn, sql):
    try:
        return pd.read_sql(sql, _conn)
    except Exception:
        return pd.DataFrame()

# 已修正：传入 current_country 动态判断国家
def show(st, conn_erp, mysql_conf, current_country):
    
    # 1. 动态判断成品前缀 (对应 Ptype.typeid)
    country_upper = current_country.upper()
    if "UGANDA" in country_upper or "乌干达" in country_upper:
        type_pfx = "00002"
    else:
        type_pfx = "00003" # 尼日利亚、肯尼亚、刚果金均为 00003

    # 已修正：提前赋值翻译，避免 f-string 内部嵌套单引号引发 SyntaxError
    title_str = T('可销天数查询')
    update_str = T('数据每小时更新一次')
    st.markdown(f"#### 📦 {title_str} ({update_str})")

    c1, c2, c3 = st.columns([2, 1.5, 1])
    with c1:
        search_kw = st.text_input(T("搜索"), placeholder=T("输入SKU名称后回车..."))
    with c2:
        # 下拉选项保持数据库原始状态中文值，外部组件 Label 进行翻译
        filter_status = st.multiselect(T("状态筛选"), ["热销款", "下单", "排产"], default=["热销款"])
    with c3:
        st.write("")
        if st.button(T("刷新数据"), type="primary"):
            st.cache_data.clear() 
            st.rerun()

    # 2. 核心 SQL 修正：CAST 防乱码 + JOIN 过滤 SKU 归属
    sql = f"""
    SELECT 
        CAST(v.存货名称 AS NVARCHAR(200)) AS 存货名称,
        CAST(v.存货编号 AS VARCHAR(50)) AS 存货编号,
        CAST(v.热销否 AS NVARCHAR(50)) AS 热销否,
        CAST(v.下单否 AS NVARCHAR(50)) AS 下单否,
        CAST(v.排产否 AS NVARCHAR(50)) AS 排产否,
        v.总可销天数, v.总箱数, v.在途可生产箱数, v.在仓可生产箱数, 
        v.[2025年月均销量], v.近90天日均销售箱数, 
        CAST(v.缺货材料 AS NVARCHAR(MAX)) AS 缺货材料, 
        v.最近入库, v.最近箱数
    FROM [v_未来可销天数] v
    -- 核心修正：通过存货编号关联 Ptype，用 RTRIM 去除隐藏空格，并精准匹配当前国家的成品前缀
    INNER JOIN Ptype c ON RTRIM(CAST(v.存货编号 AS NVARCHAR(50))) = RTRIM(CAST(c.UserCode AS NVARCHAR(50)))
    WHERE RTRIM(CAST(c.typeid AS NVARCHAR(50))) LIKE '{type_pfx}%'
    ORDER BY v.[总可销天数] ASC
    """
    
    with st.spinner(T("正在加载数据，或暂无数据...")):
        try:
            records_df = get_cached_records(conn_erp, sql)
        except Exception as e:
            st.error(f"Query Error: {str(e)}")
            records_df = pd.DataFrame()

    if not records_df.empty:
        # 3. 保持原有过滤功能
        if search_kw:
            records_df = records_df[records_df['存货名称'].astype(str).str.contains(search_kw, case=False) | 
                                    records_df['存货编号'].astype(str).str.contains(search_kw, case=False)]
        
        if "热销款" in filter_status:
            records_df = records_df[records_df['热销否'].astype(str).isin(['是', 'Yes'])]
        if "下单" in filter_status:
            records_df = records_df[records_df['下单否'].astype(str).isin(['下单', 'Order'])]
        if "排产" in filter_status:
            records_df = records_df[records_df['排产否'].astype(str).isin(['排产', 'Produce'])]

        # --- 4. 顶部 KPI 展示 ---
        warning_title = T('缺货预警')
        st.markdown(f"##### 🚨 {warning_title}")
        
        need_order = len(records_df[records_df['下单否'].astype(str).isin(['下单', 'Order'])])
        need_produce = len(records_df[records_df['排产否'].astype(str).isin(['排产', 'Produce'])])
        stock_out = len(records_df[records_df['总可销天数'] < 7])

        k1, k2, k3, k4 = st.columns(4)
        with k1: st.metric(T("建议下单"), f"{need_order}")
        with k2: st.metric(T("建议排产"), f"{need_produce}")
        with k3: st.metric(T("极度紧缺 (<7天)"), f"{stock_out}", delta="-Risk", delta_color="inverse")
        with k4:
            avg_days = records_df['总可销天数'].mean() if not records_df.empty else 0
            st.metric(T("平均可销天数"), f"{avg_days:.1f}")

        st.divider()

        # 5. 表格渲染 (统一多语言)
        st.dataframe(
            records_df,
            use_container_width=True,
            height=700,
            hide_index=True,
            column_config={
                "存货名称": st.column_config.TextColumn(label=T("存货名称"), width="medium"),
                "热销否": st.column_config.TextColumn(label=T("热销否"), width="small"),
                "下单否": st.column_config.TextColumn(label=T("下单否"), width="small"), 
                "排产否": st.column_config.TextColumn(label=T("排产否"), width="small"), 
                "总可销天数": st.column_config.NumberColumn(label=T("总可销天数"), format="%.1f"),
                "总箱数": st.column_config.NumberColumn(label=T("总箱数"), format="%.1f"),
                "在途可生产箱数": st.column_config.NumberColumn(label=T("在途可生产箱数"), format="%.1f"),
                "在仓可生产箱数": st.column_config.NumberColumn(label=T("在仓可生产箱数"), format="%.1f"),
                "2025年月均销量": st.column_config.NumberColumn(label=T("2025年月均销量"), format="%.1f"),
                "近90天日均销售箱数": st.column_config.NumberColumn(label=T("近90天日均箱数"), format="%.1f"),
                "缺货材料": st.column_config.TextColumn(label=T("缺货材料"), width="medium"),
                "最近入库": st.column_config.TextColumn(label=T("最近入库日期"), width="small"),
                "最近箱数": st.column_config.NumberColumn(label=T("最近入库箱数"), format="%.1f"),
            }
        )
    else:
        st.info(T("暂无数据"))