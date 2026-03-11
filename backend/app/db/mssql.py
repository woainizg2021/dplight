import pymssql
from typing import Optional
from app.core.config import settings

def get_db_connection(company_key: str):
    """
    Get MSSQL database connection based on company key.
    """
    if company_key not in settings.COMPANY_DB_MAP:
        raise ValueError(f"Invalid company key: {company_key}")

    db_name = settings.COMPANY_DB_MAP[company_key]
    
    # Determine which server to connect to
    if company_key in ["UGANDA", "KENYA"]:
        host = settings.MSSQL_HOST_GROUP1
        user = settings.MSSQL_USER_GROUP1
        password = settings.MSSQL_PASS_GROUP1
        port = settings.MSSQL_PORT_GROUP1
    elif company_key in ["NIGERIA", "DRC", "KENYA_AUDIO"]:
        host = settings.MSSQL_HOST_GROUP2
        user = settings.MSSQL_USER_GROUP2
        password = settings.MSSQL_PASS_GROUP2
        port = settings.MSSQL_PORT_GROUP2
    else:
        raise ValueError(f"No server configuration for company: {company_key}")

    try:
        conn = pymssql.connect(
            server=host,
            user=user,
            password=password,
            database=db_name,
            port=port,
            charset="utf8"
        )
        return conn
    except Exception as e:
        print(f"Error connecting to MSSQL for {company_key}: {e}")
        raise e
