from typing import List, Dict, Optional, Any, Union
from pydantic import BaseModel, Field
from datetime import date, datetime

# Auth
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None
    allowed_companies: List[str] = []
    is_superuser: bool = False

class User(BaseModel):
    username: str
    role: str # shareholder, manager, viewer
    allowed_companies: List[str]
    is_superuser: bool = False

class UserInDB(User):
    hashed_password: str

# Dashboard Types
class DashboardAlert(BaseModel):
    type: str # stock, sales, ar, cash
    msg: str

class CompanyDashboardData(BaseModel):
    key: str
    short_name: str
    full_name: str
    currency: str
    today_sales: float
    mtd_sales: float
    mtd_target: float
    today_production: float
    bank_balance: float
    alerts: List[DashboardAlert]

class SalesTrend(BaseModel):
    dates: List[str]
    UGANDA: List[float] = []
    NIGERIA: List[float] = []
    KENYA: List[float] = []
    KENYA_AUDIO: List[float] = []
    DRC: List[float] = []

class DashboardResponse(BaseModel):
    updated_at: str
    companies: List[CompanyDashboardData]
    sales_trend: SalesTrend

# Monthly Compare
class MonthlyCompareData(BaseModel):
    company_key: str
    revenue: float
    cogs: float
    gross_profit: float
    gross_margin: float
    opex: float
    ebit: float
    net_profit: float
    net_margin: float
    revenue_per_person: float
    dso: float
    dio: float

class MonthlyCompareResponse(BaseModel):
    data: List[MonthlyCompareData]

# Sales Performance
class SalesPerformanceData(BaseModel):
    company_key: str
    target: float
    actual: float
    completion_rate: float
    yoy: float # Year over Year
    mom: float # Month over Month

class SalesPerformanceResponse(BaseModel):
    data: List[SalesPerformanceData]

# Financial Overview
class FinancialOverview(BaseModel):
    company_key: str
    pnl_summary: Dict[str, float] # Revenue, COGS, GP, OPEX, EBIT, NP
    cost_structure: Dict[str, float] # Material, Labor, Overhead
    budget_variance: Dict[str, float] # Actual vs Budget
    month_comparison: Dict[str, float] # Current vs Last Month

# Production Overview
class ProductionOverview(BaseModel):
    company_key: str
    machines: List[Dict[str, Any]] # name, output, utilization, defect_rate
    trend: Dict[str, List[float]] # last 3 months

# Sales Overview
class SalesOverview(BaseModel):
    company_key: str
    by_sku: List[Dict[str, Any]]
    by_channel: List[Dict[str, Any]]
    month_comparison: Dict[str, Any]

# Common Request Models
class DateRequest(BaseModel):
    date: date

class MonthRequest(BaseModel):
    year: int
    month: int
    company_key: Optional[str] = None

class CacheFlushRequest(BaseModel):
    pattern: str

# Finance & AR
class ARAging(BaseModel):
    company_key: str
    current: float
    days_30: float
    days_60: float
    days_90: float
    days_over_90: float
    total: float

class ARQuery(BaseModel):
    company_key: Optional[str]
    customer_id: Optional[str]

class FinanceExpense(BaseModel):
    id: str
    date: date
    category: str
    amount: float
    description: str
    company_key: str

class FinanceCash(BaseModel):
    company_key: str
    currency: str
    balance: float
    bank_name: str

class FinanceVoucher(BaseModel):
    id: str
    date: date
    type: str
    amount: float
    status: str
    company_key: str

# Inventory
class InventoryReport(BaseModel):
    company_key: str
    raw_materials: List[Dict[str, Any]]
    semi_finished: List[Dict[str, Any]]
    finished_goods: List[Dict[str, Any]]
    summary: Dict[str, Any]
