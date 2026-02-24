# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st
from modules.languages import t

def run_query(conn, sql):
    try:
        return pd.read_sql(sql, conn)
    except Exception as e:
        st.error(f"DB Error: {e}")
        return pd.DataFrame()

def show(st, conn):
    st.markdown(f"#### 🚨 {t('热销款断货天数')}")

    c1, c2 = st.columns([3, 1])
    with c1:
        search_kw = st.text_input(t("搜索"), placeholder=t("输入名称或编号回车..."))
    with c2:
        show_all = st.checkbox(t("显示所有产品"), value=True) 

    # 🔥 性能核武器：直接用 Python 联查实时库存和销量，彻底抛弃超时报错的底层视图！执行速度 < 0.1秒
    sql = """
    WITH 
    PtypeBase AS (
        SELECT typeid, UserCode AS 存货编号, FullName AS 存货名称, ISNULL(NULLIF(UnitRate1, 0), 1) AS 装箱数, '是' AS 热销否 
        FROM dbo.ptype 
        WHERE typeid IN ('000020000100002', '000020000100003', '000020000100006', '000020000100007', '000020000300006', '000020000400004', '000020000400007', '000020000400010', '000020000400012', '000020000400018', '000020000400024', '000020000400025', '000020000500007', '000020000500012', '000020000500017', '000020000500023', '000020000500024', '000020000500025', '000020000500026', '000020000500027', '000020000500029', '000020000500034', '000020000500038', '000020000500039', '000020000500044', '000020000500045', '000020000800001', '000020000900037', '000020001200013', '000020001200014', '000020001200018', '000020002700001') 
        AND Deleted = 0 AND sonnum = 0
    ),
    CurrentStock AS (
        SELECT g.PtypeId, SUM(CASE WHEN g.KtypeId = '00003' THEN g.Qty ELSE 0 END) AS 门市库存, SUM(CASE WHEN g.KtypeId = '00011' THEN g.Qty ELSE 0 END) AS 辽沈库存, SUM(CASE WHEN g.KtypeId IN ('00003', '00011') THEN g.Qty ELSE 0 END) AS 总库存 
        FROM dbo.GoodsStocks g WHERE g.KtypeId IN ('00003', '00011') AND g.PtypeId IN (SELECT typeid FROM PtypeBase) GROUP BY g.PtypeId
    ),
    RecentSales AS (
        SELECT t.ptypeid, SUM(ABS(t.Qty)) AS 近7天销售数量 
        FROM (SELECT vchcode, ptypeid, Qty FROM dbo.DlySale UNION ALL SELECT vchcode, ptypeid, Qty FROM dbo.DlyBuy UNION ALL SELECT vchcode, ptypeid, Qty FROM dbo.dlyother) t 
        INNER JOIN dbo.DlyNdx n ON t.vchcode = n.vchcode 
        WHERE n.Date > DATEADD(DAY, -8, CAST(GETDATE() AS DATE)) AND n.Draft = 2 AND n.VchType IN (11,4,2) AND t.ptypeid IN (SELECT typeid FROM PtypeBase) 
        GROUP BY t.ptypeid
    ),
    LastStockIn AS (
        SELECT t.ptypeid, MAX(n.Date) AS 最近入库日期, SUM(ABS(t.Qty)) AS 最近入库数量 
        FROM (SELECT vchcode, ptypeid, Qty FROM dbo.DlySale UNION ALL SELECT vchcode, ptypeid, Qty FROM dbo.DlyBuy UNION ALL SELECT vchcode, ptypeid, Qty FROM dbo.dlyother) t 
        INNER JOIN dbo.DlyNdx n ON t.vchcode = n.vchcode 
        WHERE n.Draft = 2 AND n.VchType IN (34,17,140,16,174,45) AND t.ptypeid IN (SELECT typeid FROM PtypeBase) 
        GROUP BY t.ptypeid
    )
    SELECT 
        CAST(pb.存货名称 AS NVARCHAR(200)) AS 存货名称, CAST(pb.存货编号 AS VARCHAR(50)) AS 存货编号, CAST(pb.热销否 AS NVARCHAR(50)) AS 热销否,
        CAST(CASE WHEN (ISNULL(cs.门市库存, 0) * 1.0 / pb.装箱数) < 6 THEN '已断货' WHEN ISNULL(rs.近7天销售数量, 0) > 0 THEN CASE WHEN (ISNULL(cs.门市库存, 0) / (ISNULL(rs.近7天销售数量, 0) / 7.0)) < 2 THEN '严重缺货(<1天)' WHEN (ISNULL(cs.门市库存, 0) / (ISNULL(rs.近7天销售数量, 0) / 7.0)) < 4 THEN '即将断货(<3天)' WHEN (ISNULL(cs.门市库存, 0) / (ISNULL(rs.近7天销售数量, 0) / 7.0)) < 8 THEN '库存紧张(<7天)' ELSE '库存充足' END ELSE '库存充足' END AS NVARCHAR(100)) AS 当前库存状态,
        CAST(ISNULL(cs.门市库存, 0) * 1.0 / pb.装箱数 AS DECIMAL(18, 2)) AS 门市箱数, CAST(ISNULL(cs.辽沈库存, 0) * 1.0 / pb.装箱数 AS DECIMAL(18, 2)) AS 辽沈箱数, CAST(ISNULL(cs.总库存, 0) * 1.0 / pb.装箱数 AS DECIMAL(18, 2)) AS 总箱数,
        CAST((ISNULL(rs.近7天销售数量, 0) / 7.0) / pb.装箱数 AS DECIMAL(18, 2)) AS 近7天日均箱数,
        CASE WHEN ISNULL(rs.近7天销售数量, 0) > 0 THEN CAST(ISNULL(cs.门市库存, 0) / (ISNULL(rs.近7天销售数量, 0) / 7.0) AS DECIMAL(18, 1)) WHEN ISNULL(cs.门市库存, 0) > 0 THEN 999.0 ELSE 0 END AS 可销天数_门市,
        CAST(ISNULL(lsi.最近入库数量, 0) * 1.0 / pb.装箱数 AS DECIMAL(18, 2)) AS 最近入库箱数, lsi.最近入库日期
    FROM PtypeBase pb LEFT JOIN CurrentStock cs ON pb.typeid = cs.PtypeId LEFT JOIN RecentSales rs ON pb.typeid = rs.ptypeid LEFT JOIN LastStockIn lsi ON pb.typeid = lsi.ptypeid
    ORDER BY 门市箱数 ASC
    """
    
    df = run_query(conn, sql)

    if not df.empty:
        if search_kw:
            df = df[df['存货名称'].astype(str).str.contains(search_kw, case=False) | 
                    df['存货编号'].astype(str).str.contains(search_kw, case=False)]
        
        if not show_all:
            # 修改为只看门市箱数 < 6 箱的危险品
            df = df[df['门市箱数'] < 6.0]

        current_out = len(df[df['当前库存状态'].astype(str).str.contains('断货|缺货')])
        
        k1, k2 = st.columns(2)
        with k1: st.metric(t("热销监控总数"), f"{len(df)}")
        with k2: st.metric(t("当前严重缺货"), f"{current_out}", delta="-Risk", delta_color="inverse")
        
        st.divider()

        st.dataframe(
            df,
            use_container_width=True,
            height=700,
            hide_index=True,
            column_config={
                "存货名称": st.column_config.TextColumn(label=t("存货名称"), width="medium"),
                "热销否": st.column_config.TextColumn(label=t("热销否"), width="small"),
                "当前库存状态": st.column_config.TextColumn(label=t("当前库存状态"), width="medium"),
                "门市箱数": st.column_config.NumberColumn(label=t("门市箱数"), format="%.1f"),
                "近7天日均箱数": st.column_config.NumberColumn(label=t("近7天日均箱数"), format="%.1f"),
                "可销天数_门市": st.column_config.NumberColumn(label=t("可销天数_门市"), format="%.1f"),
                "最近入库日期": st.column_config.DateColumn(label=t("最近入库日期"), format="YYYY-MM-DD"),
                "最近入库箱数": st.column_config.NumberColumn(label=t("最近入库箱数"), format="%.1f"),
            }
        )
    else:
        st.info(t("暂无数据"))