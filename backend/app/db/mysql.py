import pymysql
from backend.app.core.config import settings

def get_mysql_connection():
    """
    Get connection to the central MySQL database.
    """
    try:
        conn = pymysql.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASS,
            database=settings.MYSQL_DB,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        return conn
    except Exception as e:
        print(f"Error connecting to MySQL: {e}")
        raise e
