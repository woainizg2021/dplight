import streamlit as st
import pymysql
import datetime

# ==========================================
# 1. 数据库初始化
# ==========================================
def init_log_table(mysql_conf):
    """初始化日志表"""
    try:
        conn = pymysql.connect(
            host=mysql_conf["host"], port=mysql_conf["port"],
            user=mysql_conf["user"], password=mysql_conf["pass"],
            database="erp_status_db", charset='utf8mb4', autocommit=True
        )
        with conn.cursor() as cursor:
            sql = """
            CREATE TABLE IF NOT EXISTS access_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                access_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address VARCHAR(50),
                country_selected VARCHAR(50),
                page_visited VARCHAR(100),
                user_agent TEXT,
                INDEX idx_time (access_time)
            )
            """
            cursor.execute(sql)
        conn.close()
    except Exception as e:
        print(f"Log Table Init Error: {e}")

# ==========================================
# 2. 获取客户端信息 (修正警告的核心部分)
# ==========================================
def get_remote_ip():
    """获取真实IP (穿透Nginx)"""
    try:
        # 使用新版 API: st.context.headers
        # 这是一个类似字典的对象
        if hasattr(st, "context") and hasattr(st.context, "headers"):
            headers = st.context.headers
            
            # 优先取 X-Forwarded-For (Nginx 传过来的真实IP)
            if "X-Forwarded-For" in headers:
                return headers["X-Forwarded-For"].split(',')[0]
            
            # 其次取 X-Real-Ip
            if "X-Real-Ip" in headers:
                return headers["X-Real-Ip"]
                
        return "Unknown"
    except Exception:
        return "Unknown"

def get_user_agent():
    """获取浏览器和设备信息"""
    try:
        if hasattr(st, "context") and hasattr(st.context, "headers"):
            return st.context.headers.get("User-Agent", "Unknown")
        return "Unknown"
    except Exception:
        return "Unknown"

# ==========================================
# 3. 记录日志
# ==========================================
def log_access(mysql_conf, country, page):
    """记录访问日志"""
    # 简单的 Session 锁，防止同一页面操作频繁写入数据库 (比如点击查询按钮)
    # 只有当 页面 或 国家 改变，或每小时才记录一次
    log_key = f"log_{country}_{page}_{datetime.datetime.now().strftime('%Y%m%d%H')}"
    
    if log_key in st.session_state:
        return

    try:
        ip = get_remote_ip()
        ua = get_user_agent()
        
        conn = pymysql.connect(
            host=mysql_conf["host"], port=mysql_conf["port"],
            user=mysql_conf["user"], password=mysql_conf["pass"],
            database="erp_status_db", charset='utf8mb4', autocommit=True
        )
        with conn.cursor() as cursor:
            sql = "INSERT INTO access_logs (ip_address, country_selected, page_visited, user_agent) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, (ip, country, page, ua))
        conn.close()
        
        # 标记已记录
        st.session_state[log_key] = True
        
    except Exception as e:
        print(f"Logging Failed: {e}")