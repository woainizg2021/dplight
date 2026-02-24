# -*- coding: utf-8 -*-
import streamlit as st
import pymssql
import pymysql
import config 
# 引入翻译模块 languages
from modules import sales_today, stock_finished, stock_material, stock_io_detail, security, bom_query, sales_target, production_target, stock_days, doc_check, rank_sku, rank_salesman, rank_category, rank_customer, arap_query, sys_logs, expense_query, stock_out_days, fund_query, languages, business_history, voucher_list
from modules import sales_comparison 
from modules import completion_bill_generate
from modules import pick_bill_generate
from modules import production_efficiency

# ==========================================
# 1. 页面配置
# ==========================================
st.set_page_config(
    page_title="Dplight ERP", 
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .block-container {padding-top: 2rem; padding-bottom: 1rem;}
        h4 {margin-top: 5px; padding-top: 5px; line-height: 2.5; font-size: 1rem; font-weight: bold; color: #333; margin-bottom: 1rem;}
        div[data-testid="stDataEditor"] {font-size: 0.9rem;}
        div[data-testid="stDataFrame"] {font-size: 0.9rem;}
    </style>
""", unsafe_allow_html=True)

# 简写翻译函数
T = languages.t

# ==========================================
# 2. 数据库工具
# ==========================================

# ERP MSSQL 连接池
@st.cache_resource(ttl=600)
def get_mssql_conn(tenant_key):
    creds = config.ERP_CREDENTIALS.get(tenant_key)
    if not creds: return None
    try:
        conn = pymssql.connect(server=config.ERP_HOST, port=config.ERP_PORT, user=creds['user'], password=creds['pass'], database=creds['db'], charset='utf8')
        return conn
    except Exception as e:
        st.error(f"ERP Connection Failed: {e}")
        return None

# 全量 ERP 连接池 (用于跨公司分析)
@st.cache_resource(ttl=3600)
def get_all_tenant_connections():
    conns_pool = {}
    for t_key, creds in config.ERP_CREDENTIALS.items():
        try:
            conn_item = pymssql.connect(
                server=config.ERP_HOST,
                port=config.ERP_PORT,
                user=creds['user'],
                password=creds['pass'],
                database=creds['db'],
                charset='utf8'
            )
            conns_pool[creds['name']] = conn_item 
        except Exception as e:
            print(f"[{creds['name']}] Connection Failed: {e}")
    return conns_pool

# MySQL 管理库连接 (hy_gjp_syn)
@st.cache_resource(ttl=3600)
def get_mysql_syn_conn():
    mysql_conf = config.SHARED_DB_CONFIG
    try:
        return pymysql.connect(
            host=mysql_conf['host'],
            user=mysql_conf['user'],
            password=mysql_conf['password'],
            database='hy_gjp_syn',
            charset='utf8mb4',
            autocommit=True
        )
    except Exception as e:
        st.error(f"MySQL Syn Connection Failed: {e}")
        return None

# ==========================================
# 3. 登录与权限逻辑
# ==========================================

def login_screen():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.title("🌍 Dplight ERP")
        st.info("Please enter your access password / 请输入访问密码")
        
        with st.form(key='auth_form'):
            pwd = st.text_input("Password / 密码", type="password", key="login_pwd")
            submit_btn = st.form_submit_button("Login / 登录", type="primary", use_container_width=True)
        
        if submit_btn:
            if pwd in config.USER_ACCESS:
                st.session_state['user_tenants'] = config.USER_ACCESS[pwd]
                st.session_state['logged_in'] = True
                st.rerun() 
            else:
                st.error("Invalid Password / 密码错误")

# ==========================================
# 4. 主程序入口
# ==========================================

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    login_screen()
    st.stop() 

# 初始化语言状态
if 'language' not in st.session_state:
    st.session_state['language'] = '中文'

with st.sidebar:
    st.header("🌍 Dplight ERP")
    
    lang_opt = st.radio(
        "Language / 语言", 
        ["中文", "English"], 
        horizontal=True,
        index=0 if st.session_state['language'] == '中文' else 1,
        key="lang_radio"
    )
    
    if st.session_state['language'] != lang_opt:
        st.session_state['language'] = lang_opt
        st.rerun()
    
    if st.button(f"🚪 {T('退出登录')}"):
        st.session_state['logged_in'] = False
        st.rerun()
    
    st.markdown("---")
    
    allowed_keys = st.session_state['user_tenants']
    tenant_options = {v['name']: k for k, v in config.ERP_CREDENTIALS.items() if k in allowed_keys}
    
    if not tenant_options:
        st.error("No Tenant Permission.")
        st.stop()
        
    selected_name = st.selectbox(T("账套"), list(tenant_options.keys()), index=0)
    selected_key = tenant_options[selected_name]
    current_config = config.ERP_CREDENTIALS[selected_key]
    
    st.markdown("---")
    st.markdown(f"### {T('功能列表')}")
    
    menu_list = [
         "工厂人效对比",  
         "五司销售绩效看板",
         "经营历程",
         "生成完工验收单","生产领料单",
         "销售查询", 
         "原材料库存查询", "成品库存查询", "出入库明细查询",    
         "销售目标进度查询", "生产目标进度查询", "可销天数查询",
         "单据核对系统", "BOM结构查询",
         "存货销售排行榜", "业务员销售排行榜", "大类销售排行榜", "客户销售排行榜",
         "应收款查询", "费用查询", "热销款断货天数", "资金查询", "凭证列表","系统日志"
    ]
    
    display_menu = []
    sensitive_set = set(config.SENSITIVE_MENUS) 

    for m in menu_list:
        display_text = m
        if m in sensitive_set:
            display_text = f"🔑 {m}"
        display_menu.append(display_text)

    selected_display = st.radio(T("导航"), display_menu, format_func=lambda x: T(x), label_visibility="collapsed")
    selected_menu = selected_display.replace("🔑 ", "")
    
    st.caption(f"{T('当前')}: {selected_name} ({current_config.get('currency', '')})")

# 建立 ERP 连接
conn_erp = get_mssql_conn(selected_key)

if conn_erp:
    mysql_conf = config.SHARED_DB_CONFIG
    # 初始化 MySQL 管理库连接
    conn_syn = get_mysql_syn_conn()
    # 定义当前国家变量
    current_country = selected_name 

    try:
        security.init_log_table(mysql_conf)
        security.log_access(mysql_conf, selected_name, selected_menu)
    except: pass
    
    is_unlocked = True
    if selected_menu in config.SENSITIVE_MENUS and selected_menu != "系统日志":
        is_unlocked = False
        st.markdown(f"### 🔒 {T('访问受限')}: {T(selected_menu)}")
        st.info(T("此报表包含敏感财务数据，请输入密码。"))
        
        with st.form(key=f'auth_{selected_menu}'):
            pwd = st.text_input(T("解锁密码"), type="password")
            submit = st.form_submit_button(T("登录"))
        
        if submit and pwd == config.DEFAULT_PASSWORD:
            is_unlocked = True
        elif submit:
            st.error(T("密码错误"))

    if is_unlocked:
        if selected_menu == "销售查询":
            sales_today.show(st, conn_erp, mysql_conf, selected_name)

        elif selected_menu == "五司销售绩效看板":
            sales_comparison.show(st, st.session_state['user_tenants'])
            
        elif selected_menu == "工厂人效对比":
            # 获取全局跨公司连接池并传入人效模块
            tenant_conns_pool = get_all_tenant_connections()
            # 传递修复后的参数
            production_efficiency.show(st, tenant_conns_pool, conn_syn, current_country)

        elif selected_menu == "经营历程":
            business_history.show(st, conn_erp)
        
        elif selected_menu == "生成完工验收单":  
            completion_bill_generate.show(st, conn_erp)
            
        elif selected_menu == "成品库存查询":
            stock_finished.show(st, conn_erp, current_config)

        elif selected_menu == "生产领料单":  
            pick_bill_generate.show(st, conn_erp)
            
        elif selected_menu == "原材料库存查询":
            stock_material.show(st, conn_erp, current_config)
            
        elif selected_menu == "出入库明细查询":
            stock_io_detail.show(st, conn_erp)
            
        elif selected_menu == "销售目标进度查询":
            sales_target.show(st, conn_erp, mysql_conf, selected_name)
            
        elif selected_menu == "生产目标进度查询":
            production_target.show(st, conn_erp)
            
        elif selected_menu == "可销天数查询":
            stock_days.show(st, conn_erp, mysql_conf, selected_name)
            
        elif selected_menu == "BOM结构查询":
            bom_query.show(st, conn_erp)
            
        elif selected_menu == "存货销售排行榜":
            rank_sku.show(st, conn_erp)
            
        elif selected_menu == "业务员销售排行榜":
            rank_salesman.show(st, conn_erp)
            
        elif selected_menu == "大类销售排行榜":
            rank_category.show(st, conn_erp)
            
        elif selected_menu == "客户销售排行榜":
            rank_customer.show(st, conn_erp)
            
        elif selected_menu == "应收款查询":
            arap_query.show(st, conn_erp)
            
        elif selected_menu == "费用查询":
            expense_query.show(st, conn_erp)
            
        elif selected_menu == "热销款断货天数":
            stock_out_days.show(st, conn_erp)
            
        elif selected_menu == "资金查询":
            fund_query.show(st, conn_erp)

        elif selected_menu == "凭证列表":          
            voucher_list.show(st, conn_erp)       
            
        elif selected_menu == "单据核对系统":
            db_auth_conf = {'host':config.ERP_HOST, 'port':config.ERP_PORT, 'user':current_config['user'], 'pass':current_config['pass'], 'db':current_config['db']}
            doc_check.show(st, db_auth_conf)
            
        elif selected_menu == "系统日志":
            sys_logs.show(st, mysql_conf)
            
    else:
        st.write("")