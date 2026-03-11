from typing import Dict, Any, Optional, List
from datetime import datetime, date
from app.db.mssql import get_db_connection
from app.db.mysql import get_mysql_connection
from app.models.schemas import ARQuery, ARAging
import logging

logger = logging.getLogger(__name__)

class ARAPService:
    """
    Service for Accounts Receivable and Payable queries and analysis.
    This service provides comprehensive AR/AP functionality migrated from Streamlit modules.
    """
    
    def get_ar_query(self, company_key: str, start_date: str, end_date: str) -> ARQuery:
        """
        Get detailed accounts receivable transactions with AI analysis capabilities.
        Migrated from Streamlit arap_query.py module.
        """
        try:
            conn = get_db_connection(company_key)
            
            with conn.cursor(as_dict=True) as cursor:
                # Get AR transactions with detailed information
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
                        END as status,
                        CASE 
                            WHEN DATEDIFF(day, d.Date, GETDATE()) <= 30 THEN 'Current'
                            WHEN DATEDIFF(day, d.Date, GETDATE()) BETWEEN 31 AND 60 THEN '31-60 Days'
                            WHEN DATEDIFF(day, d.Date, GETDATE()) BETWEEN 61 AND 90 THEN '61-90 Days'
                            ELSE 'Over 90 Days'
                        END as aging_bucket
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
                        "status": row['status'],
                        "aging_bucket": row['aging_bucket']
                    })
                
                # Calculate summary statistics
                summary = self._calculate_ar_summary(transactions)
                
                return ARQuery(
                    company_key=company_key,
                    start_date=start_date,
                    end_date=end_date,
                    transactions=transactions,
                    summary=summary
                )
                
        except Exception as e:
            logger.error(f"Error fetching AR query for {company_key}: {e}")
            raise e
        finally:
            if 'conn' in locals():
                conn.close()
    
    def get_ar_aging_analysis(self, company_key: str) -> ARAging:
        """
        Get comprehensive AR aging analysis with customer breakdown.
        Enhanced version of the original AR aging functionality.
        """
        try:
            conn = get_db_connection(company_key)
            
            with conn.cursor(as_dict=True) as cursor:
                # Get detailed AR aging by customer with risk assessment
                sql_ar_aging = """
                    SELECT 
                        b.FullName as customer_name,
                        b.UserCode as customer_code,
                        b.Contact as contact_person,
                        b.Tel as contact_phone,
                        SUM(CASE WHEN DATEDIFF(day, d.Date, GETDATE()) <= 30 THEN ABS(d.Total) ELSE 0 END) as current_30,
                        SUM(CASE WHEN DATEDIFF(day, d.Date, GETDATE()) BETWEEN 31 AND 60 THEN ABS(d.Total) ELSE 0 END) as days_31_60,
                        SUM(CASE WHEN DATEDIFF(day, d.Date, GETDATE()) BETWEEN 61 AND 90 THEN ABS(d.Total) ELSE 0 END) as days_61_90,
                        SUM(CASE WHEN DATEDIFF(day, d.Date, GETDATE()) > 90 THEN ABS(d.Total) ELSE 0 END) as over_90,
                        SUM(ABS(d.Total)) as total_ar,
                        COUNT(DISTINCT d.VchCode) as invoice_count,
                        MAX(d.Date) as last_transaction_date,
                        AVG(ABS(d.Total)) as avg_invoice_amount
                    FROM Dlyndx d
                    JOIN Btype b ON d.BtypeId = b.TypeId
                    WHERE d.VchType = 12  -- Sales invoices
                    AND d.Draft = 2
                    AND d.Total < 0  -- Outstanding amounts (negative)
                    GROUP BY b.FullName, b.UserCode, b.Contact, b.Tel
                    HAVING SUM(ABS(d.Total)) > 0
                    ORDER BY total_ar DESC
                """
                
                cursor.execute(sql_ar_aging)
                rows = cursor.fetchall()
                
                customers = []
                for row in rows:
                    overdue_60_plus = float(row['days_61_90'] or 0) + float(row['over_90'] or 0)
                    risk_level = self._assess_customer_risk(row)
                    
                    customers.append({
                        "customer_name": row['customer_name'],
                        "customer_code": row['customer_code'],
                        "contact_person": row['contact_person'],
                        "contact_phone": row['contact_phone'],
                        "current_30": float(row['current_30'] or 0),
                        "days_31_60": float(row['days_31_60'] or 0),
                        "days_61_90": float(row['days_61_90'] or 0),
                        "over_90": float(row['over_90'] or 0),
                        "total_ar": float(row['total_ar'] or 0),
                        "invoice_count": int(row['invoice_count'] or 0),
                        "last_transaction_date": row['last_transaction_date'].strftime('%Y-%m-%d') if row['last_transaction_date'] else '',
                        "avg_invoice_amount": float(row['avg_invoice_amount'] or 0),
                        "overdue_60_plus": overdue_60_plus,
                        "risk_level": risk_level
                    })
                
                # Calculate comprehensive totals
                totals = {
                    "total_ar": sum(c['total_ar'] for c in customers),
                    "current_30": sum(c['current_30'] for c in customers),
                    "days_31_60": sum(c['days_31_60'] for c in customers),
                    "days_61_90": sum(c['days_61_90'] for c in customers),
                    "over_90": sum(c['over_90'] for c in customers),
                    "overdue_60_plus": sum(c['overdue_60_plus'] for c in customers),
                    "total_invoices": sum(c['invoice_count'] for c in customers),
                    "avg_invoice_amount": sum(c['avg_invoice_amount'] for c in customers) / len(customers) if customers else 0
                }
                
                # Calculate risk metrics
                risk_metrics = self._calculate_risk_metrics(customers, totals)
                
                return ARAging(
                    company_key=company_key,
                    customers=customers,
                    totals=totals,
                    risk_metrics=risk_metrics
                )
                
        except Exception as e:
            logger.error(f"Error fetching AR aging analysis for {company_key}: {e}")
            raise e
        finally:
            if 'conn' in locals():
                conn.close()
    
    def _calculate_ar_summary(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate summary statistics for AR transactions."""
        if not transactions:
            return {
                "total_amount": 0,
                "outstanding_amount": 0,
                "paid_amount": 0,
                "overdue_amount": 0,
                "current_amount": 0,
                "avg_days_overdue": 0,
                "transaction_count": 0
            }
        
        total_amount = sum(t['amount'] for t in transactions)
        outstanding_amount = sum(t['amount'] for t in transactions if t['status'] == 'Outstanding')
        paid_amount = sum(t['amount'] for t in transactions if t['status'] == 'Paid')
        overdue_amount = sum(t['amount'] for t in transactions if t['days_overdue'] > 30)
        current_amount = sum(t['amount'] for t in transactions if t['days_overdue'] <= 30)
        avg_days_overdue = sum(t['days_overdue'] for t in transactions) / len(transactions)
        
        return {
            "total_amount": total_amount,
            "outstanding_amount": outstanding_amount,
            "paid_amount": paid_amount,
            "overdue_amount": overdue_amount,
            "current_amount": current_amount,
            "avg_days_overdue": avg_days_overdue,
            "transaction_count": len(transactions)
        }
    
    def _assess_customer_risk(self, customer_data: Dict[str, Any]) -> str:
        """Assess customer risk level based on payment history."""
        total_ar = float(customer_data['total_ar'] or 0)
        days_61_90 = float(customer_data['days_61_90'] or 0)
        over_90 = float(customer_data['over_90'] or 0)
        avg_invoice_amount = float(customer_data['avg_invoice_amount'] or 0)
        
        # Risk assessment logic
        if over_90 > 0:
            return "High Risk"
        elif days_61_90 > 0:
            return "Medium Risk"
        elif total_ar > avg_invoice_amount * 3:  # High balance relative to average
            return "Watch List"
        else:
            return "Low Risk"
    
    def _calculate_risk_metrics(self, customers: List[Dict[str, Any]], totals: Dict[str, float]) -> Dict[str, Any]:
        """Calculate comprehensive risk metrics."""
        
        # Risk distribution
        risk_distribution = {
            "high_risk": len([c for c in customers if c['risk_level'] == "High Risk"]),
            "medium_risk": len([c for c in customers if c['risk_level'] == "Medium Risk"]),
            "watch_list": len([c for c in customers if c['risk_level'] == "Watch List"]),
            "low_risk": len([c for c in customers if c['risk_level'] == "Low Risk"])
        }
        
        # Aging percentages
        aging_percentages = {
            "current_pct": (totals['current_30'] / totals['total_ar'] * 100) if totals['total_ar'] > 0 else 0,
            "days_31_60_pct": (totals['days_31_60'] / totals['total_ar'] * 100) if totals['total_ar'] > 0 else 0,
            "days_61_90_pct": (totals['days_61_90'] / totals['total_ar'] * 100) if totals['total_ar'] > 0 else 0,
            "over_90_pct": (totals['over_90'] / totals['total_ar'] * 100) if totals['total_ar'] > 0 else 0
        }
        
        # Collection efficiency
        collection_efficiency = {
            "current_collection_rate": 100 - aging_percentages['days_31_60_pct'],
            "overdue_rate": aging_percentages['days_61_90_pct'] + aging_percentages['over_90_pct'],
            "bad_debt_risk": aging_percentages['over_90_pct']
        }
        
        return {
            "risk_distribution": risk_distribution,
            "aging_percentages": aging_percentages,
            "collection_efficiency": collection_efficiency
        }

arap_service = ARAPService()