import pandas as pd
import streamlit as st
from modules.languages import t

def run_query(conn, sql):
    try:
        return pd.read_sql(sql, conn)
    except Exception as e:
        st.error(f"SQL Error: {e}")
        return pd.DataFrame()

def clean_zero(val):
    if val == 0 or val == 0.0: return None
    return val

def show(st, conn, config=None):
    # 翻译标题
    st.markdown(f"#### 🧩 {t('BOM结构查询')}")

    # 获取当前国家的默认仓库 (用于显示列名和查询库存)
    # 默认值 (乌干达)
    wh_mat = "辽沈原料仓"
    wh_prod = ["门市仓库", "辽沈成品仓"] # 成品可能有多个
    
    if config and 'business_rules' in config:
        # 获取原料仓 (取列表第一个作为代表)
        m_list = config['business_rules'].get('default_wh_material', [])
        if m_list: wh_mat = m_list[0]
        
        # 获取成品仓 (取前两个作为代表)
        p_list = config['business_rules'].get('default_wh_finished', [])
        if p_list: wh_prod = p_list

    c1, c2, c3 = st.columns([1.5, 3, 1])
    with c1:
        # 翻译单选框
        options = ["查成品结构 (BOM)", "查原料用途 (反查)"]
        query_type_label = st.radio(t("查询模式"), options, horizontal=True, label_visibility="collapsed", format_func=lambda x: t(x))
        # 反向映射回中文 key，方便下面逻辑判断
        query_type = "查成品结构 (BOM)" if "BOM" in query_type_label else "查原料用途 (反查)"
    
    with c2:
        ph = t("输入成品型号") if query_type == "查成品结构 (BOM)" else t("输入原料名称")
        # 回车即查
        search_kw = st.text_input(t("搜索"), placeholder=ph + "...", key="bom_search")

    with c3:
        st.write("")
        if st.button(t("查询"), type="primary", key="bom_btn"):
            st.session_state['bom_refresh'] = True

    if search_kw:
        col_left, col_right = st.columns([2, 1])

        if query_type == "查成品结构 (BOM)":
            # 模式 A：查成品
            # 动态生成 SQL：库存列名跟随配置
            # 注意：这里我们尽量模糊匹配仓库名，或者直接用 GoodsStocks 汇总
            # 为了简单通用，这里展示该成品所需的原料的总库存 (不分仓库，或者匹配默认仓)
            
            # 这里简化逻辑：原料库存 = 汇总所有原料仓 (TypeID=00001) 的库存
            # 这样不用担心仓库名写死的问题
            
            sql = f"""
            SELECT 
                CAST(Main.UserCode AS VARCHAR(50)) AS [成品编号],
                CAST(Main.FullName AS NVARCHAR(200)) AS [成品名称],
                CAST(Mat.UserCode AS VARCHAR(50)) AS [原料编号],
                CAST(Mat.FullName AS NVARCHAR(200)) AS [原料名称],
                CAST(Mat.Standard AS NVARCHAR(100)) AS [规格],
                CAST(Mat.Unit1 AS NVARCHAR(20)) AS [单位],
                
                CAST(Det.Qty AS DECIMAL(18,4)) AS [单件用量],
                
                -- 原料库存 (汇总该原料所有仓库的库存)
                ISNULL((SELECT SUM(Qty) FROM GoodsStocks WHERE PtypeId = Mat.typeid), 0) AS [原料库存],
                
                CASE WHEN ISNULL(Det.Qty, 0) = 0 THEN 0 
                     ELSE FLOOR(ISNULL((SELECT SUM(Qty) FROM GoodsStocks WHERE PtypeId = Mat.typeid), 0) / Det.Qty) 
                END AS [可产套数]

            FROM Ptype Main
            INNER JOIN T_SC_BOM_Ndx Ndx ON Main.typeid = Ndx.PtypeID
            INNER JOIN T_SC_BOM_Detail Det ON Ndx.ID = Det.ParID
            INNER JOIN Ptype Mat ON Det.PtypeID = Mat.typeid
            
            WHERE (Main.UserCode LIKE '%{search_kw}%' OR Main.FullName LIKE '%{search_kw}%')
              AND Main.typeid LIKE '00002%' 
              AND Main.leveal = 3 
            ORDER BY Main.UserCode, Mat.UserCode
            """
            
            df = run_query(conn, sql)
            
            if not df.empty:
                df['单件用量'] = df['单件用量'].apply(clean_zero)
                df['原料库存'] = df['原料库存'].apply(clean_zero)
                df['可产套数'] = df['可产套数'].apply(clean_zero)

                st.dataframe(
                    df,
                    use_container_width=True,
                    height=600,
                    hide_index=True,
                    column_config={
                        "成品编号": st.column_config.TextColumn(label=t("成品编号"), width="small"),
                        "原料编号": st.column_config.TextColumn(label=t("原料编号"), width="small"),
                        "成品名称": st.column_config.TextColumn(label=t("成品名称"), width="medium"),
                        "原料名称": st.column_config.TextColumn(label=t("原料名称"), width="medium"),
                        "规格": st.column_config.TextColumn(label=t("规格"), width="small"),
                        "单位": st.column_config.TextColumn(label=t("单位"), width="small"),
                        
                        "单件用量": st.column_config.NumberColumn(label=t("单件用量"), format="%.4f"),
                        "原料库存": st.column_config.NumberColumn(label=t("原料库存"), format="%d"),
                        "可产套数": st.column_config.ProgressColumn(
                            label=t("可产套数"),
                            format="%d", 
                            min_value=0, 
                            max_value=int(df['可产套数'].max()) if df['可产套数'].max() else 1000,
                        ),
                    }
                )
            else:
                st.info(t("无数据。"))

        else:
            # 模式 B：查原料 (反向)
            # 成品库存：展示配置中前两个仓库的库存
            
            # 动态构建 SQL 选择列
            wh1_name = wh_prod[0] if len(wh_prod) > 0 else "Warehouse 1"
            wh2_name = wh_prod[1] if len(wh_prod) > 1 else "Warehouse 2"
            
            sql = f"""
            SELECT 
                CAST(Mat.UserCode AS VARCHAR(50)) AS [原料编号],
                CAST(Mat.FullName AS NVARCHAR(200)) AS [原料名称],
                CAST(Main.UserCode AS VARCHAR(50)) AS [成品编号],
                CAST(Main.FullName AS NVARCHAR(200)) AS [成品名称],
                
                CAST(Det.Qty AS DECIMAL(18,4)) AS [单件用量],
                
                -- 动态匹配仓库 1
                CAST(ISNULL((SELECT SUM(Qty) FROM GoodsStocks gs LEFT JOIN Stock s ON gs.KtypeId=s.typeId WHERE gs.PtypeId = Main.typeid AND s.FullName LIKE '%{wh1_name}%'), 0) / NULLIF(Main.UnitRate1, 0) AS DECIMAL(18,1)) AS [仓1],
                
                -- 动态匹配仓库 2
                CAST(ISNULL((SELECT SUM(Qty) FROM GoodsStocks gs LEFT JOIN Stock s ON gs.KtypeId=s.typeId WHERE gs.PtypeId = Main.typeid AND s.FullName LIKE '%{wh2_name}%'), 0) / NULLIF(Main.UnitRate1, 0) AS DECIMAL(18,1)) AS [仓2]

            FROM Ptype Mat
            INNER JOIN T_SC_BOM_Detail Det ON Mat.typeid = Det.PtypeID
            INNER JOIN T_SC_BOM_Ndx Ndx ON Det.ParID = Ndx.ID
            INNER JOIN Ptype Main ON Ndx.PtypeID = Main.typeid
            
            WHERE (Mat.UserCode LIKE '%{search_kw}%' OR Mat.FullName LIKE '%{search_kw}%')
              AND Main.typeid LIKE '00002%'  
              AND Main.leveal = 3 
              AND Mat.typeid NOT LIKE '00002%' 
            ORDER BY Mat.UserCode, Main.UserCode
            """
            
            df = run_query(conn, sql)
            
            if not df.empty:
                df['单件用量'] = df['单件用量'].apply(clean_zero)
                df['仓1'] = df['仓1'].apply(clean_zero)
                df['仓2'] = df['仓2'].apply(clean_zero)

                st.dataframe(
                    df,
                    use_container_width=True,
                    height=600,
                    hide_index=True,
                    column_config={
                        "原料编号": st.column_config.TextColumn(label=t("原料编号"), width="small"),
                        "成品编号": st.column_config.TextColumn(label=t("成品编号"), width="small"),
                        "原料名称": st.column_config.TextColumn(label=t("原料名称"), width="medium"),
                        "成品名称": st.column_config.TextColumn(label=t("成品名称"), width="medium"),
                        
                        "单件用量": st.column_config.NumberColumn(label=t("单件用量"), format="%.4f"),
                        
                        # 动态列名
                        "仓1": st.column_config.NumberColumn(label=f"{wh1_name} ({t('箱数')})", format="%.1f"),
                        "仓2": st.column_config.NumberColumn(label=f"{wh2_name} ({t('箱数')})", format="%.1f"),
                    }
                )
            else:
                st.info(t("无数据。"))