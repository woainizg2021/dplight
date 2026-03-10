from typing import List, Optional, Dict
from pydantic import AnyHttpUrl, EmailStr, validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Dplight ERP"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str] | str:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # MSSQL Database Group 1 (UGANDA, KENYA)
    MSSQL_HOST_GROUP1: str
    MSSQL_USER_GROUP1: str
    MSSQL_PASS_GROUP1: str
    MSSQL_PORT_GROUP1: int = 3433

    # MSSQL Database Group 2 (NIGERIA, DRC, KENYA_AUDIO)
    MSSQL_HOST_GROUP2: str
    MSSQL_USER_GROUP2: str
    MSSQL_PASS_GROUP2: str
    MSSQL_PORT_GROUP2: int = 3433

    # Company DB Mapping
    COMPANY_DB_MAP: Dict[str, str] = {
        "UGANDA": "CMCSYUN532502",
        "KENYA": "CMCSYUN4348395",
        "NIGERIA": "CMCSYUN355738",
        "DRC": "CMCSYUN983044",
        "KENYA_AUDIO": "CMCSYUN650929"
    }

    # MySQL Database (Tencent Cloud)
    MYSQL_HOST: str
    MYSQL_PORT: int = 23459
    MYSQL_USER: str
    MYSQL_PASS: str
    MYSQL_DB: str = "hy_gjp_syn"
    MYSQL_DB_FEEDBACK: str = "dplight_feedback"

    # Redis
    REDIS_HOST: str
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    DASHBOARD_CACHE_TTL: int = 600  # 10 minutes
    MONTHLY_CACHE_TTL: int = 3600   # 1 hour

    # AI
    DEEPSEEK_API_KEY: str
    DEEPSEEK_BASE_URL: str

    # WeCom Webhooks
    WX_WEBHOOK_UGANDA: str
    WX_WEBHOOK_KENYA: str

    # Sensitive Passwords
    DEFAULT_PASSWORD: str
    PROFIT_SECRET_KEY: str

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
