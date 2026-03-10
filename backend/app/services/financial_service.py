from typing import Dict, Any, Optional, List
from datetime import datetime, date
from backend.app.db.mssql import get_db_connection
from backend.app.db.mysql import get_mysql_connection
from backend.app.models.schemas import ARAgingReport, ExpenseReport, CashReport, VoucherReport
import logging

logger = logging.getLogger(__name__)

class FinancialService:
    def get_ar_aging(self, company_key: str) -> ARAgingReport:
        """Get accounts receivable aging report."""
        try:
            conn = get_db_connection(company_key)
            
            with conn.cursor(as_dict=True) as cursor:
                sql_ar_aging = """
                    SELECT 
                        b.FullName as customer_name,
                        b.UserCode as customer_code,
                        SUM(CASE WHEN DATEDIFF(day, d.Date, GETDATE()) <= 30 THEN ABS(s.Total) ELSE 0 END) as current_amount,
                        SUM(CASE WHEN DATEDIFF(day, d.Date, GETDATE()) BETWEEN 31 AND 60 THEN ABS(s.Total) ELSE 0 END) as days_31_60,
                        SUM(CASE WHEN DATEDIFF(day, d.Date, GETDATE()) BETWEEN 61 AND 90 THEN ABS(s.Total) ELSE 0 END) as days_61_90,
                        SUM(CASE WHEN DATEDIFF(day, d.Date, GETDATE()) > 90 THEN ABS(s.Total) ELSE 0 END) as over_90_days,
                        SUM(ABS(s.Total)) as total_ar,
                        COUNT(DISTINCT d.VchCode) as invoice_count
                    FROM DlySale s
                    JOIN Dlyndx d ON s.VchCode = d.VchCode
                    JOIN Btype b ON d.BtypeId = b.TypeId
                    WHERE d.VchType = 11 
                    AND d.Draft = 2
                    AND s.Total < 0 -- Sales (negative in DlySale)
                    AND d.Date >= DATEADD(month, -6, GETDATE()) -- Last 6 months
                    GROUP BY b.FullName, b.UserCode
                    HAVING SUM(ABS(s.Total)) > 0
                    ORDER BY total_ar DESC
                """
                
                cursor.execute(sql_ar_aging)
                rows = cursor.fetchall()
                
                customers = []
                for row in rows:
                    customers.append({
                        "customer_name": row['customer_name'],
                        "customer_code": row['customer_code'],
                        "current_amount": float(row['current_amount']),
                        "days_31_60": float(row['days_31_60']),
                        "days_61_90": float(row['days_61_90']),
                        "over_90_days": float(row['over_90_days']),
                        "total_ar": float(row['total_ar']),
                        "invoice_count": int(row['invoice_count']),
                        "is_overdue": float(row['days_61_90']) + float(row['over_90_days']) > 0
                    })
                
                # Calculate totals
                totals = {
                    "total_current": sum(c['current_amount'] for c in customers),
                    "total_31_60": sum(c['days_31_60'] for c in customers),
                    "total_61_90": sum(c['days_61_90'] for c in customers),
                    "total_over_90": sum(c['over_90_days'] for c in customers),
                    "total_ar": sum(c['total_ar'] for c in customers),
                    "overdue_customers": sum(1 for c in customers if c['is_overdue'])
                }
                
                return ARAgingReport(
                    company_key=company_key,
                    customers=customers,
                    totals=totals
                )
                
        except Exception as e:
            logger.error(f"Error fetching AR aging for {company_key}: {e}")
            raise e
        finally:
            if 'conn' in locals():
                conn.close()
    
    def get_expense_report(self, company_key: str, year: int, month: int) -> ExpenseReport:
        """Get expense report for the month."""
        try:
            conn = get_db_connection(company_key)
            
            with conn.cursor(as_dict=True) as cursor:
                start_date = f"{year}-{month:02d}-01"
                end_date = f"{year}-{month:02d}-31"
                
                sql_expenses = """
                    SELECT 
                        a.FullName as account_name,
                        a.UserCode as account_code,
                        SUM(ABS(d.DebitTotal)) as total_amount,
                        COUNT(DISTINCT d.vchcode) as transaction_count,
                        AVG(ABS(d.DebitTotal)) as avg_amount
                    FROM t_cw_dly d
                    JOIN t_cw_dlyndx ndx ON d.vchcode = ndx.vchcode
                    JOIN t_cw_atype a ON d.atypeid = a.atypeid
                    WHERE ndx.Draft = 2
                    AND d.date BETWEEN %s AND %s
                    AND RTRIM(d.atypeid) LIKE '0000100002%' -- Expense accounts
                    GROUP BY a.FullName, a.UserCode
                    HAVING SUM(ABS(d.DebitTotal)) > 0
                    ORDER BY total_amount DESC
                """
                
                cursor.execute(sql_expenses, (start_date, end_date))
                rows = cursor.fetchall()
                
                expenses = []
                for row in rows:
                    expenses.append({
                        "account_name": row['account_name'],
                        "account_code": row['account_code'],
                        "total_amount": float(row['total_amount']),
                        "transaction_count": int(row['transaction_count']),
                        "avg_amount": float(row['avg_amount'])
                    })
                
                # Calculate totals
                totals = {
                    "total_expenses": sum(e['total_amount'] for e in expenses),
                    "total_transactions": sum(e['transaction_count'] for e in expenses),
                    "avg_expense": sum(e['total_amount'] for e in expenses) / len(expenses) if expenses else 0
                }
                
                return ExpenseReport(
                    company_key=company_key,
                    expenses=expenses,
                    totals=totals
                )
                
        except Exception as e:
            logger.error(f"Error fetching expense report for {company_key}: {e}")
            raise e
        finally:
            if 'conn' in locals():
                conn.close()
    
    def get_cash_report(self, company_key: str) -> CashReport:
        """Get cash and bank balance report."""
        try:
            conn = get_db_connection(company_key)
            
            with conn.cursor(as_dict=True) as cursor:
                sql_cash = """
                    SELECT 
                        a.FullName as account_name,
                        a.UserCode as account_code,
                        SUM(d.EndDebitTotal - d.EndCreditTotal) as current_balance,
                        SUM(d.BeginDebitTotal - d.BeginCreditTotal) as opening_balance,
                        COUNT(DISTINCT d.vchcode) as transaction_count
                    FROM t_cw_dly d
                    JOIN t_cw_dlyndx ndx ON d.vchcode = ndx.vchcode
                    JOIN t_cw_atype a ON d.atypeid = a.atypeid
                    WHERE ndx.Draft = 2
                    AND RTRIM(d.atypeid) LIKE '0000100003%' -- Cash and bank accounts
                    GROUP BY a.FullName, a.UserCode
                    HAVING ABS(SUM(d.EndDebitTotal - d.EndCreditTotal)) > 0
                    ORDER BY current_balance DESC
                """
                
                cursor.execute(sql_cash)
                rows = cursor.fetchall()
                
                accounts = []
                for row in rows:
                    accounts.append({
                        "account_name": row['account_name'],
                        "account_code": row['account_code'],
                        "current_balance": float(row['current_balance']),
                        "opening_balance": float(row['opening_balance']),
                        "transaction_count": int(row['transaction_count']),
                        "balance_change": float(row['current_balance']) - float(row['opening_balance'])
                    })
                
                # Calculate totals
                totals = {
                    "total_current_balance": sum(a['current_balance'] for a in accounts),
                    "total_opening_balance": sum(a['opening_balance'] for a in accounts),
                    "total_balance_change": sum(a['balance_change'] for a in accounts),
                    "account_count": len(accounts)
                }
                
                return CashReport(
                    company_key=company_key,
                    accounts=accounts,
                    totals=totals
                )
                
        except Exception as e:
            logger.error(f"Error fetching cash report for {company_key}: {e}")
            raise e
        finally:
            if 'conn' in locals():
                conn.close()
    
    def get_voucher_report(self, company_key: str, start_date: str, end_date: str) -> VoucherReport:
        """Get voucher list for the period."""
        try:
            conn = get_db_connection(company_key)
            
            with conn.cursor(as_dict=True) as cursor:
                sql_vouchers = """
                    SELECT 
                        ndx.VchCode as voucher_code,
                        ndx.VchType as voucher_type,
                        ndx.Date as voucher_date,
                        ndx.Explain as description,
                        ndx.Total as total_amount,
                        ndx.Draft as status,
                        COUNT(d.vchcode) as line_count
                    FROM t_cw_dlyndx ndx
                    JOIN t_cw_dly d ON ndx.vchcode = d.vchcode
                    WHERE ndx.Date BETWEEN %s AND %s
                    AND ndx.Draft = 2 -- Posted vouchers only
                    GROUP BY ndx.VchCode, ndx.VchType, ndx.Date, ndx.Explain, ndx.Total, ndx.Draft
                    ORDER BY ndx.Date DESC, ndx.VchCode DESC
                """
                
                cursor.execute(sql_vouchers, (start_date, end_date))
                rows = cursor.fetchall()
                
                vouchers = []
                for row in rows:
                    vouchers.append({
                        "voucher_code": row['voucher_code'],
                        "voucher_type": self._get_voucher_type_name(row['voucher_type']),
                        "voucher_date": row['voucher_date'].strftime('%Y-%m-%d') if isinstance(row['voucher_date'], (datetime, date)) else str(row['voucher_date']),
                        "description": row['description'],
                        "total_amount": abs(float(row['total_amount'])),
                        "status": "已记账" if row['status'] == 2 else "草稿",
                        "line_count": int(row['line_count'])
                    })
                
                # Calculate totals
                totals = {
                    "total_vouchers": len(vouchers),
                    "total_amount": sum(v['total_amount'] for v in vouchers),
                    "avg_amount": sum(v['total_amount'] for v in vouchers) / len(vouchers) if vouchers else 0
                }
                
                return VoucherReport(
                    company_key=company_key,
                    vouchers=vouchers,
                    totals=totals
                )
                
        except Exception as e:
            logger.error(f"Error fetching voucher report for {company_key}: {e}")
            raise e
        finally:
            if 'conn' in locals():
                conn.close()
    
    def _get_voucher_type_name(self, voucher_type: int) -> str:
        """Get voucher type name from code."""
        type_names = {
            1: "收款凭证",
            2: "付款凭证", 
            3: "转账凭证",
            4: "记账凭证",
            11: "销售出库单",
            12: "采购入库单",
            13: "销售退货单",
            14: "采购退货单"
        }
        return type_names.get(voucher_type, f"其他({voucher_type})")

financial_service = FinancialService()