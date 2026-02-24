# -*- coding: utf-8 -*-
import streamlit as st

# ==========================================
# 跨国 ERP 报表系统 - 全量多语言词典
# ==========================================

# 核心词典：中文 -> 英文
DICT = {
    # --- 菜单 / Menus ---
    "今日销售查询": "Daily Sales Inquiry",
    "销售查询": "Sales Query",
    "原材料库存查询": "Material Stock",
    "成品库存查询": "Product Stock",
    "出入库明细查询": "In/Out Detail",
    "销售目标进度查询": "Sales Target KPI",
    "生产目标进度查询": "Production Target KPI",
    "可销天数查询": "Stock Days Analysis",
    "单据核对系统": "Receipt Audit",
    "BOM结构查询": "BOM Query",
    "存货销售排行榜": "Product Ranking",
    "业务员销售排行榜": "Salesman Ranking",
    "大类销售排行榜": "Category Ranking",
    "客户销售排行榜": "Customer Ranking",
    "应收款查询": "AR (Receivables)",
    "费用查询": "Expenses Query",
    "热销款断货天数": "Stockout Alert",
    "资金查询": "Cash & Bank",
    "系统日志": "System Logs",
    "计件工资表": "Piecework Wage",
    "新品状况表": "New Products",
    "近5次生产入库": "Last 5 Production",
    "五司销售业绩看板": "Global Sales Performance",
    "经营历程": "Business History",

    # --- 绩效对标专用 (Sales Comparison / PK) ---
    "全球综合业绩对标": "Global Performance Benchmark",
    "达成率": "Achievement Rate",
    "目标(万)": "Target (10k)",
    "整体完成率": "Overall Completion Rate",
    "时间进度": "Time Progress",
    "尼日利亚": "Nigeria",
    "乌干达": "Uganda",
    "肯尼亚": "Kenya",
    "肯尼亚音响厂": "Kenya Audio Factory",
    "刚果金": "DRC",
    "本月概况": "Monthly Overview",
    "全年明细表": "Annual Detailed Table",

    # --- 生产模块 (Production) ---
    "本月生产概况": "Monthly Production Overview",
    "实际完成": "Actual Completion",
    "总目标箱数": "Total Target Cartons",
    "箱": "Ctns",

    # --- 搜索与过滤 (Search & Filter) ---
    "模糊搜索 (支持空格分隔多条件，如: 采购 张三)": "Fuzzy Search (Space-separated, e.g., Purchase Zhang)",
    "状态筛选": "Status Filter",
    "数据每小时更新一次": "Data updated every hour",

    # --- 费用与财务 (Finance Details) ---
    "现金流出明细 (精细化四账户)": "Cash Outflow Details (4-Account Refinement)",
    "各项费用支出明细 (源自原始视图)": "Expense Details (From Original View)",
    "今日暂无原始视图费用记录": "No expense records found in the original view today.",
    "所选日期范围内没有单据记录": "No document records within the selected date range.",

    # --- 缺货预警 (Stockout Alert) ---
    "缺货预警": "Stockout Warning",
    "热销款": "Hot Items",
    "建议排产": "Recommended Production",
    "建议下单": "Recommended Ordering",
    "极度紧缺 (<7天)": "Extreme Shortage (<7 Days)",
    "平均可销天数": "Avg Sales Days",

    # --- 销售查询页面 (Sales Today) ---
    "销售单号": "Order No.",
    "手工单号": "Manual No.",
    "销售金额": "Sales Amt",
    "现金": "Cash",
    "应收账款": "Accounts Receivable",
    "收回欠款": "Payment Received",
    "银行(支票)": "Bank/Cheque",
    "客户": "Customer",
    "核对": "Check",
    "型号": "Model/SKU",
    "装箱数": "Pack Rate",
    "总数量": "Total Qty",
    "总价": "Total Amt",
    "单价": "Unit Price",
    "箱数": "Cartons",
    "日期": "Date",
    "查询": "Search",
    "选择日期": "Select Date",
    "选择月份": "Select Month",
    "年份": "Year",
    "加载中...": "Loading...",
    "今日暂无流水数据": "No transactions today.",
    "暂无型号统计": "No model statistics.",

    # --- 合计与汇总 (Summary) ---
    "合计": "TOTAL",
    "数值": "Values",
    "今日费用": "Today's Exp",
    "合计箱数": "Total Cartons",
    "合计总价": "Grand Total",

    # --- 库存 (Stock) ---
    "仓库名称": "Warehouse",
    "存货编号": "Item Code",
    "存货名称": "Item Name",
    "库存数量": "Stock Qty",
    "库存箱数": "Stock Ctns",

    # --- 通用 (General) ---
    "无数据。": "No Data.",
    "暂无数据": "No Data Available",
    "账套": "Tenant",
    "货币单位": "Currency",
    "刷新数据": "Refresh",
    "搜索": "Search",
}

def t(text):
    """翻译函数：输入中文，返回英文（如果当前语言是English）"""
    if st.session_state.get('language') == 'English':
        # 1. 尝试直接匹配
        if text in DICT:
            return DICT[text]
        
        # 2. 清理装饰性图标并匹配
        clean_text = text.replace("📊 ", "").replace("💰 ", "").replace("🔑 ", "").replace("🏆 ", "").replace("🎯 ", "").replace("📅 ", "").replace("📋 ", "").strip()
        
        if clean_text in DICT:
            return DICT[clean_text]
        
        return text
    return text

def trans_df(df):
    """自动翻译 DataFrame 的列名"""
    if st.session_state.get('language') == 'English':
        map_dict = {col: t(col) for col in df.columns}
        return df.rename(columns=map_dict)
    return df