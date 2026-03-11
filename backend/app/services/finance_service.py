from typing import Dict, Any, Optional, List
from datetime import datetime, date
from app.db.mssql import get_db_connection
from app.models.schemas import ARAging, ARQuery, FinanceExpense, FinanceCash, FinanceVoucher
import logging

logger = logging.getLogger(__name__)

class FinanceService:
    def get_ar_aging(self, company_key: str) -> ARAging:
        """Get accounts receivable aging analysis."""
        try:
            conn = get_db_connection(company_key)
            
            with conn.cursor(as_dict=True) as cursor:
                # Get AR aging data
                sql_ar_aging = """
                    SELECT 
                        b.FullName as customer_name,
                        b.UserCode as customer_code,
                        SUM(CASE WHEN DATEDIFF(day, d.Date, GETDATE()) <= 30 THEN ABS(d.Total) ELSE 0 END) as current_30,
                        SUM(CASE WHEN DATEDIFF(day, d.Date, GETDATE()) BETWEEN 31 AND 60 THEN ABS(d.Total) ELSE 0 END) as days_31_60,
                        SUM(CASE WHEN DATEDIFF(day, d.Date, GETDATE()) BETWEEN 61 AND 90 THEN ABS(d.Total) ELSE 0 END) as days_61_90,
                        SUM(CASE WHEN DATEDIFF(day, d.Date, GETDATE()) > 90 THEN ABS(d.Total) ELSE 0 END) as over_90,
                        SUM(ABS(d.Total)) as total_ar,
                        COUNT(DISTINCT d.VchCode) as invoice_count
                    FROM Dlyndx d
                    JOIN Btype b ON d.BtypeId = b.TypeId
                    WHERE d.VchType = 12  -- Sales invoices
                    AND d.Draft = 2
                    AND d.Total < 0  -- Outstanding amounts (negative)
                    GROUP BY b.FullName, b.UserCode
                    HAVING SUM(ABS(d.Total)) > 0
                    ORDER BY total_ar DESC
                """
                
                cursor.execute(sql_ar_aging)
                rows = cursor.fetchall()
                
                customers = []
                for row in rows:
                    customers.append({
                        "customer_name": row['customer_name'],
                        "customer_code": row['customer_code'],
                        "current_30": float(row['current_30'] or 0),
                        "days_31_60": float(row['days_31_60'] or 0),
                        "days_61_90": float(row['days_61_90'] or 0),
                        "over_90": float(row['over_90'] or 0),
                        "total_ar": float(row['total_ar'] or 0),
                        "invoice_count": int(row['invoice_count'] or 0),
                        "overdue_60_plus": float(row['days_61_90'] or 0) + float(row['over_90'] or 0)
                    })
                
                # Calculate totals
                totals = {
                    "total_ar": sum(c['total_ar'] for c in customers),
                    "current_30": sum(c['current_30'] for c in customers),
                    "days_31_60": sum(c['days_31_60'] for c in customers),
                    "days_61_90": sum(c['days_61_90'] for c in customers),
                    "over_90": sum(c['over_90'] for c in customers),
                    "overdue_60_plus": sum(c['overdue_60_plus'] for c in customers)
                }
                
                return ARAging(
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
    
    def get_ar_query(self, company_key: str, start_date: str, end_date: str) -> ARQuery:
        """Get detailed accounts receivable transactions."""
        try:
            conn = get_db_connection(company_key)
            
            with conn.cursor(as_dict=True) as cursor:
                sql_ar_query = """
                    SELECT 
                        d.VchCode as voucher_code,
                        d.Date as transaction_date,
                        b.FullName as customer_name,
                        b.UserCode as customer_code,
                        CAST(d.Memo AS NVARCHAR(500)) as description,
                        ABS(d.Total) as amount,
                        DATEDIFF(day, d.Date, GETDATE()) as days_overdue,
                        CASE 
                            WHEN d.Total < 0 THEN 'Outstanding'
                            ELSE 'Paid'
                        END as status
                    FROM Dlyndx d
                    JOIN Btype b ON d.BtypeId = b.TypeId
                    WHERE d.VchType = 12  -- Sales invoices
                    AND d.Draft = 2
                    AND d.Date BETWEEN %s AND %s
                    ORDER BY d.Date DESC, d.VchCode DESC
                """
                
                cursor.execute(sql_ar_query, (start_date, end_date))
                rows = cursor.fetchall()
                
                transactions = []
                for row in rows:
                    transactions.append({
                        "voucher_code": row['voucher_code'],
                        "transaction_date": row['transaction_date'].strftime('%Y-%m-%d') if row['transaction_date'] else '',
                        "customer_name": row['customer_name'],
                        "customer_code": row['customer_code'],
                        "description": row['description'],
                        "amount": float(row['amount'] or 0),
                        "days_overdue": int(row['days_overdue'] or 0),
                        "status": row['status']
                    })
                
                return ARQuery(
                    company_key=company_key,
                    start_date=start_date,
                    end_date=end_date,
                    transactions=transactions
                )
                
        except Exception as e:
            logger.error(f"Error fetching AR query for {company_key}: {e}")
            raise e
        finally:
            if 'conn' in locals():
                conn.close()
    
    def get_expense_report(self, company_key: str, year: int, month: int) -> FinanceExpense:
        """Get expense report for specified period."""
        try:
            conn = get_db_connection(company_key)
            
            with conn.cursor(as_dict=True) as cursor:
                start_date = f"{year}-{month:02d}-01"
                end_date = f"{year}-{month:02d}-31"
                
                sql_expense = """
                    SELECT 
                        atype.FullName as account_name,
                        atype.UserCode as account_code,
                        SUM(ABS(d.DebitTotal)) as expense_amount,
                        COUNT(DISTINCT d.VchCode) as transaction_count
                    FROM t_cw_dly d
                    JOIN t_cw_dlyndx ndx ON d.vchcode = ndx.vchcode
                    JOIN t_cw_atype atype ON d.atypeid = atype.TypeId
                    WHERE ndx.Draft = 2
                    AND d.date BETWEEN %s AND %s
                    AND atype.TypeId LIKE '0000100002%'  -- Expense accounts
                    GROUP BY atype.FullName, atype.UserCode
                    HAVING SUM(ABS(d.DebitTotal)) > 0
                    ORDER BY expense_amount DESC
                """
                
                cursor.execute(sql_expense, (start_date, end_date))
                rows = cursor.fetchall()
                
                expenses = []
                for row in rows:
                    expenses.append({
                        "account_name": row['account_name'],
                        "account_code": row['account_code'],
                        "expense_amount": float(row['expense_amount'] or 0),
                        "transaction_count": int(row['transaction_count'] or 0)
                    })
                
                # Calculate totals
                total_expense = sum(e['expense_amount'] for e in expenses)
                total_transactions = sum(e['transaction_count'] for e in expenses)
                
                return FinanceExpense(
                    company_key=company_key,
                    year=year,
                    month=month,
                    expenses=expenses,
                    total_expense=total_expense,
                    total_transactions=total_transactions
                )
                
        except Exception as e:
            logger.error(f"Error fetching expense report for {company_key}: {e}")
            raise e
        finally:
            if 'conn' in locals():
                conn.close()
    
    def get_cash_report(self, company_key: str) -> FinanceCash:
        """Get cash position and bank balance report."""
        try:
            conn = get_db_connection(company_key)
            
            with conn.cursor(as_dict=True) as cursor:
                # Get current bank balances
                sql_bank_balance = """
                    SELECT 
                        bank.FullName as bank_name,
                        bank.UserCode as bank_code,
                        SUM(CASE WHEN d.VchType = 1 THEN d.Total ELSE 0 END) as opening_balance,
                        SUM(CASE WHEN d.VchType = 101 THEN ABS(d.Total) ELSE 0 END) as receipts,
                        SUM(CASE WHEN d.VchType = 102 THEN ABS(d.Total) ELSE 0 END) as payments,
                        SUM(d.Total) as current_balance
                    FROM Dlyndx d
                    JOIN Btype bank ON d.BtypeId = bank.TypeId
                    WHERE bank.TypeId LIKE '00007%'  -- Bank accounts
                    AND d.Draft = 2
                    GROUP BY bank.FullName, bank.UserCode
                    ORDER BY current_balance DESC
                """
                
                cursor.execute(sql_bank_balance)
                rows = cursor.fetchall()
                
                bank_accounts = []
                for row in rows:
                    bank_accounts.append({
                        "bank_name": row['bank_name'],
                        "bank_code": row['bank_code'],
                        "opening_balance": float(row['opening_balance'] or 0),
                        "receipts": float(row['receipts'] or 0),
                        "payments": float(row['payments'] or 0),
                        "current_balance": float(row['current_balance'] or 0)
                    })
                
                # Calculate totals
                total_balance = sum(b['current_balance'] for b in bank_accounts)
                total_receipts = sum(b['receipts'] for b in bank_accounts)
                total_payments = sum(b['payments'] for b in bank_accounts)
                
                return FinanceCash(
                    company_key=company_key,
                    bank_accounts=bank_accounts,
                    total_balance=total_balance,
                    total_receipts=total_receipts,
                    total_payments=total_payments
                )
                
        except Exception as e:
            logger.error(f"Error fetching cash report for {company_key}: {e}")
            raise e
        finally:
            if 'conn' in locals():
                conn.close()
    
    def get_voucher_list(self, company_key: str, start_date: str, end_date: str) -> FinanceVoucher:
        """Get accounting vouchers list for specified period."""
        try:
            conn = get_db_connection(company_key)
            
            with conn.cursor(as_dict=True) as cursor:
                sql_vouchers = """
                    SELECT 
                        v.VchCode as voucher_code,
                        v.Date as voucher_date,
                        CAST(v.Memo AS NVARCHAR(500)) as description,
                        v.Total as voucher_amount,
                        v.VchType as voucher_type,
                        CASE v.VchType
                            WHEN 1 THEN '期初余额'
                            WHEN 11 THEN '销售出库'
                            WHEN 12 THEN '销售退货'
                            WHEN 101 THEN '收款单'
                            WHEN 102 THEN '付款单'
                            ELSE '其他'
                        END as voucher_type_name,
                        v.Draft as draft_status
                    FROM Dlyndx v
                    WHERE v.Date BETWEEN %s AND %s
                    AND v.Draft = 2
                    ORDER BY v.Date DESC, v.VchCode DESC
                """
                
                cursor.execute(sql_vouchers, (start_date, end_date))
                rows = cursor.fetchall()
                
                vouchers = []
                for row in rows:
                    vouchers.append({
                        "voucher_code": row['voucher_code'],
                        "voucher_date": row['voucher_date'].strftime('%Y-%m-%d') if row['voucher_date'] else '',
                        "description": row['description'],
                        "voucher_amount": float(row['voucher_amount'] or 0),
                        "voucher_type": row['voucher_type'],
                        "voucher_type_name": row['voucher_type_name'],
                        "draft_status": int(row['draft_status'] or 0)
                    })
                
                return FinanceVoucher(
                    company_key=company_key,
                    start_date=start_date,
                    end_date=end_date,
                    vouchers=vouchers
                )
                
        except Exception as e:
            logger.error(f"Error fetching voucher list for {company_key}: {e}")
            raise e
        finally:
            if 'conn' in locals():
                conn.close()

finance_service = FinanceService()