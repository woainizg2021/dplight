from typing import Generator
import pymssql
import pymysql
from backend.app.config import (
    ERP_CREDENTIALS,
    SHARED_DB_CONFIG,
    ERP_HOST,
    ERP_PORT
)

class DBConnectionError(Exception):
    pass

def get_mssql_connection(company_code: str):
    """
    Get MSSQL connection for a specific company.
    
    Args:
        company_code (str): The company identifier key (e.g., 'UGANDA', 'NIGERIA').
    
    Returns:
        pymssql.Connection: The database connection.
        
    Raises:
        DBConnectionError: If connection fails or company_code is invalid.
    """
    creds = ERP_CREDENTIALS.get(company_code)
    if not creds:
        raise DBConnectionError(f"Invalid company code: {company_code}")
    
    try:
        conn = pymssql.connect(
            server=ERP_HOST,
            port=ERP_PORT,
            user=creds['user'],
            password=creds['pass'],
            database=creds['db'],
            charset='utf8'
        )
        return conn
    except Exception as e:
        raise DBConnectionError(f"Failed to connect to MSSQL for {company_code}: {str(e)}")

def get_mysql_connection():
    """
    Get connection to the shared MySQL database.
    
    Returns:
        pymysql.Connection: The database connection.
    """
    try:
        conn = pymysql.connect(
            host=SHARED_DB_CONFIG['host'],
            port=SHARED_DB_CONFIG['port'],
            user=SHARED_DB_CONFIG['user'],
            password=SHARED_DB_CONFIG['password'],
            database=SHARED_DB_CONFIG['database'],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True
        )
        return conn
    except Exception as e:
        raise DBConnectionError(f"Failed to connect to MySQL: {str(e)}")

# Dependency Injection for FastAPI
def get_db(company_code: str):
    conn = get_mssql_connection(company_code)
    try:
        yield conn
    finally:
        conn.close()

def get_shared_db():
    conn = get_mysql_connection()
    try:
        yield conn
    finally:
        conn.close()
