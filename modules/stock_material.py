import pandas as pd
import streamlit as st
import datetime
from modules.languages import t

def run_query(conn, sql):
    try:
        return pd.read_sql(sql, conn)
    except Exception:
        return pd.DataFrame()

def clean_zero(val):
    if val == 0 or val == 0.0: return None
    return val

# --- 新增：强力清洗函数 ---
def clean_text(text):
    """清洗乱码，只保留 ASCII 字符 (数字、字母、标点)"""
    if pd.isna(text): return ""
    text = str(text)
    # 如果包含非 ASCII 字符，尝试 encode('latin1').decode('gbk') 这种常见修复手段
    # 但最稳妥的是直接移除乱码字符，或者确保它是 UTF-8
    try:
        # 尝试修正常见的 SQL Server 乱码
        return text.encode('latin1').decode('gbk')
    except:
        # 如果修正失败，就原样返回，或者只保留可打印字符
        return text

def show(st, conn, config=None):
    st.markdown(f"##### 🧱 {t('原材料库存查询')}")

    c1, c2, c3, c4, c5 = st.columns([1.5, 1.5, 2, 2, 1])
    
    with c1:
        today = datetime.date.today()
        first_day = today.replace(day=1)
        start_date = st.date_input(t("开始日期"), first_day, key="mat_start")
    with c2:
        end_date = st.date_input(t("结束日期"), today, key="mat_end")
    with c3:
        try:
            df_wh = run_query(conn, "SELECT DISTINCT CAST([仓库名称] AS NVARCHAR(100)) AS [仓库名称] FROM [v_原材料仓库变动查询]")
            wh_list = [t("全部仓库")] + df_wh['仓库名称'].tolist() if not df_wh.empty else [t("全部仓库")]
        except:
            wh_list = [t("全部仓库")]
            
        default_idx = 0
        target_whs = []
        if config and 'business_rules' in config:
            target_whs = config['business_rules'].get('default_wh_material', [])
        
        if not target_whs:
            target_whs = ["辽沈原料仓", "辽沈"]

        found = False
        for target in target_whs:
            for i, real_name in enumerate(wh_list):
                if target in str(real_name):
                    default_idx = i
                    found = True
                    break
            if found: break
             
        selected_wh = st.selectbox(t("仓库"), wh_list, index=default_idx, key="mat_wh")
    
    with c4:
        search_kw = st.text_input(t("搜索 (名称/编号)"), placeholder=t("搜索 (名称/编号)") + "...", key="mat_search")

    with c5:
        st.write("") 
        st.write("") 
        if st.button(t("查询"), type="primary", key="mat_btn"):
            st.session_state['stock_mat_refresh'] = True

    if start_date and end_date:
        calc_start_date = start_date
        if calc_start_date <= datetime.date(2025, 1, 1):
            calc_start_date = datetime.date(2025, 1, 1)

        s_date = calc_start_date.strftime('%Y-%m-%d')
        e_date = end_date.strftime('%Y-%m-%d')
        
        wh_filter = ""
        if selected_wh != t("全部仓库"):
            wh_filter = f"WHERE CAST([仓库名称] AS NVARCHAR(100)) = '{selected_wh}'"

        sql = f"""
        SELECT * FROM (
            SELECT 
                CAST([仓库名称] AS NVARCHAR(100)) AS [仓库名称],
                CAST([存货编号] AS NVARCHAR(100)) AS [存货编号], -- 再次确保 NVARCHAR
                CAST([存货名称] AS NVARCHAR(200)) AS [存货名称],
                
                SUM(CASE WHEN [单据日期] < '{s_date}' THEN [变动数量] ELSE 0 END) AS [期初数量],
                SUM(CASE WHEN [单据日期] < '{s_date}' THEN [变动箱数] ELSE 0 END) AS [期初箱数],
                SUM(CASE WHEN [单据日期] BETWEEN '{s_date}' AND '{e_date}' AND [变动数量] > 0 THEN [变动数量] ELSE 0 END) AS [入库数量],
                SUM(CASE WHEN [单据日期] BETWEEN '{s_date}' AND '{e_date}' AND [变动数量] > 0 THEN [变动箱数] ELSE 0 END) AS [入库箱数],
                ABS(SUM(CASE WHEN [单据日期] BETWEEN '{s_date}' AND '{e_date}' AND [变动数量] < 0 THEN [变动数量] ELSE 0 END)) AS [出库数量],
                ABS(SUM(CASE WHEN [单据日期] BETWEEN '{s_date}' AND '{e_date}' AND [变动数量] < 0 THEN [变动箱数] ELSE 0 END)) AS [出库箱数],
                SUM(CASE WHEN [单据日期] <= '{e_date}' THEN [变动数量] ELSE 0 END) AS [库存数量],
                SUM(CASE WHEN [单据日期] <= '{e_date}' THEN [变动箱数] ELSE 0 END) AS [库存箱数]
            FROM [v_原材料仓库变动查询]
            {wh_filter}
            GROUP BY [仓库名称], [存货编号], [存货名称]
        ) t
        WHERE t.[期初数量] <> 0 OR t.[入库数量] <> 0 OR t.[出库数量] <> 0 OR t.[库存数量] <> 0
        ORDER BY t.[库存数量] DESC
        """
        
        df = run_query(conn, sql)

        if not df.empty:
            # --- 应用清洗函数 ---
            # 尝试修复乱码 (如果还有乱码，就把这行注释掉，说明不是简单的编码问题)
            # df['存货编号'] = df['存货编号'].apply(clean_text) 
            # -------------------

            if search_kw:
                df = df[df['存货名称'].astype(str).str.contains(search_kw, case=False) | 
                        df['存货编号'].astype(str).str.contains(search_kw, case=False)]

            num_cols = ['期初数量', '期初箱数', '入库数量', '入库箱数', '出库数量', '出库箱数', '库存数量', '库存箱数']
            for col in num_cols: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

            total_row = pd.DataFrame(df[num_cols].sum()).T
            total_row['存货名称'] = '🟢 ' + t('合计') # 翻译合计
            total_row['仓库名称'] = ''
            total_row['存货编号'] = ''
            
            for col in num_cols:
                df[col] = df[col].apply(clean_zero)
                total_row[col] = total_row[col].apply(clean_zero)

            df_display = pd.concat([df, total_row], ignore_index=True)

            st.dataframe(
                df_display,
                use_container_width=True,
                height=600,
                hide_index=True,
                column_config={
                    "仓库名称": st.column_config.TextColumn(label=t("仓库名称"), width="small"),
                    "存货编号": st.column_config.TextColumn(label=t("存货编号"), width="small"),
                    "存货名称": st.column_config.TextColumn(label=t("存货名称"), width="medium"),
                    
                    "期初数量": st.column_config.NumberColumn(label=t("期初数量"), format="%d"),
                    "期初箱数": st.column_config.NumberColumn(label=t("期初箱数"), format="%.1f"),
                    
                    "入库数量": st.column_config.NumberColumn(label=t("入库数量"), format="%d"),
                    "入库箱数": st.column_config.NumberColumn(label=t("入库箱数"), format="%.1f"),
                    
                    "出库数量": st.column_config.NumberColumn(label=t("出库数量"), format="%d"),
                    "出库箱数": st.column_config.NumberColumn(label=t("出库箱数"), format="%.1f"),
                    
                    "库存数量": st.column_config.NumberColumn(label=t("库存数量"), format="%d"),
                    "库存箱数": st.column_config.NumberColumn(label=t("库存箱数"), format="%.1f"),
                }
            )
        else:
            st.info(t("无数据。"))