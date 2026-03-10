import sys
import os
from pathlib import Path

# Add project root to sys.path to import root config
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Import from root config
try:
    from config import (
        ERP_CREDENTIALS,
        SHARED_DB_CONFIG,
        AI_CONFIG,
        ERP_HOST,
        ERP_PORT,
        ACCESS_TOKEN,
        VERIFY_TOKEN,
        WX_APP_CONFIG,
        WX_AGENTS,
        REPORT_WEBHOOKS,
        USER_ACCESS,
        SENSITIVE_MENUS,
        DEFAULT_PASSWORD,
        PROFIT_SECRET_KEY,
        CLOUD_360_CONFIG
    )
    from business_config import (
        TENANTS,
        DEFAULT_TENANT_KEY,
        ERP_BUSINESS_RULES,
        FACTORY_META,
        HOT_SELLING_IDS,
        WX_CORP_ID
    )
except ImportError as e:
    print(f"Error importing root config: {e}")
    # Fallback or raise error
    raise

# Redis Configuration (from env or default)
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# Cache TTL
DASHBOARD_CACHE_TTL = int(os.getenv("DASHBOARD_CACHE_TTL", 600))  # 10 minutes
MONTHLY_CACHE_TTL = int(os.getenv("MONTHLY_CACHE_TTL", 3600))     # 1 hour

# App Settings
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
