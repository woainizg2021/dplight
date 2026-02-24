# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st
import datetime
import calendar
from modules.languages import t as T  # 统一使用 T 简化翻译

def run_query(conn, sql):
    """
    执行 ERP 查询并返回数据帧 (严禁使用 DATA 变量名)
    """
    try:
        return pd.read_sql(sql, conn)
    except Exception as e:
        st.error(f"Inventory Query Error: {e}")
        return pd.DataFrame()

def clean_zero_values(val):
    """清理表格中的 0 值，使其更清爽"""
    if val == 0 or val == 0.0: return None
    return val

def show(st, conn_erp, tenant_config=None):
    # 1. 翻译模块标题
    st.markdown(f"##### 🏭 {T('成品库存查询')}")

    # 2. 搜索控制栏
    col1, col2, col3, col4, col5 = st.columns([1.5, 1.5, 2, 2, 1])
    
    with col1:
        today_date = datetime.date.today()
        first_day_of_month = today_date.replace(day=1)
        start_date = st.date_input(T("开始日期"), first_day_of_month, key="fin_start")
    with col2:
        end_date = st.date_input(T("结束日期"), today_date, key="fin_end")
    
    with col3:
        try:
            # 仓库列表提取，强制使用 NVARCHAR 防止乱码
            sql_wh = "SELECT DISTINCT CAST([仓库名称] AS NVARCHAR(100)) AS [仓库名称] FROM [v_成品仓库变动查询]"
            wh_records_df = run_query(conn_erp, sql_wh)
            wh_dropdown_list = [T("全部仓库")] + wh_records_df['仓库名称'].tolist() if not wh_records_df.empty else [T("全部仓库")]
        except:
            wh_dropdown_list = [T("全部仓库")]
        
        # 智能默认仓库匹配逻辑
        default_wh_index = 0
        preferred_whs = []
        if tenant_config and 'business_rules' in tenant_config:
            preferred_whs = tenant_config['business_rules'].get('default_wh_finished', [])
        
        if not preferred_whs:
            preferred_whs = ["门市仓库", "门市"]

        # 执行匹配
        found_match = False
        for target in preferred_whs:
            for i, name in enumerate(wh_dropdown_list):
                if target in str(name):
                    default_wh_index = i
                    found_match = True
                    break
            if found_match: break
             
        selected_warehouse = st.selectbox(T("仓库"), wh_dropdown_list, index=default_wh_index, key="fin_wh")
    
    with col4:
        keyword_search = st.text_input(T("搜索 (名称/编号)"), placeholder=T("搜索 (名称/编号)") + "...", key="fin_search")

    with col5:
        st.write("") 
        st.write("") 
        if st.button(T("查询"), type="primary", key="fin_btn"):
            st.session_state['stock_finish_refresh_flag'] = True

    # 3. 执行核心 SQL 逻辑
    if start_date and end_date:
        # 安全日期过滤 (防止查过早的数据导致系统变慢)
        safe_start = start_date if start_date >= datetime.date(2025, 1, 1) else datetime.date(2025, 1, 1)
        s_date_str = safe_start.strftime('%Y-%m-%d')
        e_date_str = end_date.strftime('%Y-%m-%d')
        
        # 仓库过滤条件构建
        filter_clause = ""
        if selected_warehouse != T("全部仓库"):
            filter_clause = f"WHERE CAST([仓库名称] AS NVARCHAR(100)) = N'{selected_warehouse}'"

        # 核心 SQL: 存货编号字段修正为 NVARCHAR
        sql_inventory = f"""
        SELECT * FROM (
            SELECT 
                CAST([仓库名称] AS NVARCHAR(100)) AS [仓库名称],
                CAST([存货编号] AS NVARCHAR(50)) AS [存货编号], -- 关键修复点：VARCHAR -> NVARCHAR 防止乱码
                CAST([存货名称] AS NVARCHAR(200)) AS [存货名称],
                
                SUM(CASE WHEN [单据日期] < '{s_date_str}' THEN [变动数量] ELSE 0 END) AS [期初数量],
                SUM(CASE WHEN [单据日期] < '{s_date_str}' THEN [变动箱数] ELSE 0 END) AS [期初箱数],
                SUM(CASE WHEN [单据日期] BETWEEN '{s_date_str}' AND '{e_date_str}' AND [变动数量] > 0 THEN [变动数量] ELSE 0 END) AS [入库数量],
                SUM(CASE WHEN [单据日期] BETWEEN '{s_date_str}' AND '{e_date_str}' AND [变动数量] > 0 THEN [变动箱数] ELSE 0 END) AS [入库箱数],
                ABS(SUM(CASE WHEN [单据日期] BETWEEN '{s_date_str}' AND '{e_date_str}' AND [变动数量] < 0 THEN [变动数量] ELSE 0 END)) AS [出库数量],
                ABS(SUM(CASE WHEN [单据日期] BETWEEN '{s_date_str}' AND '{e_date_str}' AND [变动数量] < 0 THEN [变动箱数] ELSE 0 END)) AS [出库箱数],
                SUM(CASE WHEN [单据日期] <= '{e_date_str}' THEN [变动数量] ELSE 0 END) AS [库存数量],
                SUM(CASE WHEN [单据日期] <= '{e_date_str}' THEN [变动箱数] ELSE 0 END) AS [库存箱数]
            FROM [v_成品仓库变动查询]
            {filter_clause}
            GROUP BY [仓库名称], [存货编号], [存货名称]
        ) t
        WHERE t.[期初数量] <> 0 OR t.[入库数量] <> 0 OR t.[出库数量] <> 0 OR t.[库存数量] <> 0
        ORDER BY t.[库存数量] DESC
        """
        
        stock_result_df = run_query(conn_erp, sql_inventory)

        if not stock_result_df.empty:
            # 前端模糊搜索过滤
            if keyword_search:
                stock_result_df = stock_result_df[
                    stock_result_df['存货名称'].astype(str).str.contains(keyword_search, case=False) | 
                    stock_result_df['存货编号'].astype(str).str.contains(keyword_search, case=False)
                ]

            # 4. 数据汇总行处理
            numeric_fields = ['期初数量', '期初箱数', '入库数量', '入库箱数', '出库数量', '出库箱数', '库存数量', '库存箱数']
            for col in numeric_fields: stock_result_df[col] = pd.to_numeric(stock_result_df[col], errors='coerce').fillna(0)

            sum_row = pd.DataFrame(stock_result_df[numeric_fields].sum()).T
            sum_row['存货名称'] = f"🟢 {T('合计')}"
            sum_row['仓库名称'] = ''
            sum_row['存货编号'] = ''
            
            # 清理 0 值
            for col in numeric_fields:
                stock_result_df[col] = stock_result_df[col].apply(clean_zero_values)
                sum_row[col] = sum_row[col].apply(clean_zero_values)

            final_display_df = pd.concat([stock_result_df, sum_row], ignore_index=True)

            # 5. 渲染表格
            st.dataframe(
                final_display_df,
                use_container_width=True,
                height=600,
                hide_index=True,
                column_config={
                    "仓库名称": st.column_config.TextColumn(label=T("仓库名称"), width="small"),
                    "存货编号": st.column_config.TextColumn(label=T("存货编号"), width="small"),
                    "存货名称": st.column_config.TextColumn(label=T("存货名称"), width="medium"),
                    
                    "期初数量": st.column_config.NumberColumn(label=T("期初数量"), format="%d"),
                    "期初箱数": st.column_config.NumberColumn(label=T("期初箱数"), format="%.1f"),
                    "入库数量": st.column_config.NumberColumn(label=T("入库数量"), format="%d"),
                    "入库箱数": st.column_config.NumberColumn(label=T("入库箱数"), format="%.1f"),
                    "出库数量": st.column_config.NumberColumn(label=T("出库数量"), format="%d"),
                    "出库箱数": st.column_config.NumberColumn(label=T("出库箱数"), format="%.1f"),
                    "库存数量": st.column_config.NumberColumn(label=T("库存数量"), format="%d"),
                    "库存箱数": st.column_config.NumberColumn(label=T("库存箱数"), format="%.1f"),
                }
            )
        else:
            st.info(T("无数据。"))