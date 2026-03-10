from datetime import datetime, date
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from backend.app.db.mssql import get_db_connection
from backend.app.db.mysql import get_mysql_connection
from backend.app.core.cache import cache_service
from backend.app.core.config import settings
from backend.app.models.schemas import MonthlyCompareResponse, MonthlyCompareData
import logging

logger = logging.getLogger(__name__)

class MonthlyCompareService:
    
    # 公司名称映射
    COMPANY_NAMES = {
        "UGANDA": {"short_name": "乌干达", "full_name": "乌干达灯具制造"},
        "NIGERIA": {"short_name": "尼日利亚", "full_name": "尼日利亚灯具制造"},
        "KENYA": {"short_name": "肯尼亚", "full_name": "肯尼亚灯具制造"},
        "KENYA_AUDIO": {"short_name": "肯尼亚音箱", "full_name": "肯尼亚音箱制造"},
        "DRC": {"short_name": "刚果金", "full_name": "刚果金灯具制造"}
    }
    
    def get_monthly_compare(self, year: int, month: int) -> MonthlyCompareResponse:
        """获取月度对比数据 - 5家公司P&L横向对比"""
        
        cache_key = f"dashboard:monthly:{year}:{month}"
        
        # 尝试缓存
        cached = cache_service.get(cache_key)
        if cached:
            return MonthlyCompareResponse(**cached)
        
        # 并行获取所有公司数据
        data = []
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_company = {
                executor.submit(self._get_company_monthly_data, company, year, month): company
                for company in settings.COMPANY_DB_MAP.keys()
            }
            
            for future in future_to_company:
                company_key = future_to_company[future]
                try:
                    company_data = future.result()
                    data.append(company_data)
                except Exception as e:
                    logger.error(f"获取 {company_key} 月度数据失败: {e}")
                    # 返回错误状态的数据
                    data.append(self._get_error_company_data(company_key))
        
        # 按指定顺序排序
        order = ['UGANDA', 'NIGERIA', 'KENYA', 'KENYA_AUDIO', 'DRC']
        data.sort(key=lambda x: order.index(x.company_key) if x.company_key in order else 99)
        
        result = MonthlyCompareResponse(data=data)
        
        # 缓存结果 (1小时TTL)
        cache_service.set(cache_key, result.model_dump(), settings.MONTHLY_CACHE_TTL)
        
        return result
    
    def _get_company_monthly_data(self, company_key: str, year: int, month: int) -> MonthlyCompareData:
        """获取单个公司月度数据"""
        
        # 计算日期范围
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        conn = None
        try:
            conn = get_db_connection(company_key)
            with conn.cursor(as_dict=True) as cursor:
                
                # 1. 收入 (销售收入)
                sql_revenue = """
                    SELECT SUM(ABS(Total)) as revenue
                    FROM Dlyndx 
                    WHERE VchType = 11 AND Draft = 2 
                    AND Date BETWEEN %s AND %s
                """
                cursor.execute(sql_revenue, (start_str, f"{end_str} 23:59:59"))
                row = cursor.fetchone()
                revenue = float(row['revenue']) if row and row['revenue'] else 0.0
                
                # 2. 销售成本 (COGS) - 从销售成本科目获取
                sql_cogs = """
                    SELECT SUM(ABS(d.Amount)) as cogs
                    FROM DlyA d
                    JOIN Dlyndx n ON d.VchCode = n.VchCode
                    WHERE n.VchType = 11 AND n.Draft = 2 
                    AND d.AtypeId LIKE '0000200001%' -- 销售成本科目
                    AND n.Date BETWEEN %s AND %s
                """
                cursor.execute(sql_cogs, (start_str, f"{end_str} 23:59:59"))
                row = cursor.fetchone()
                cogs = float(row['cogs']) if row and row['cogs'] else 0.0
                
                # 3. 营业费用 (OPEX) - 从费用科目获取
                sql_opex = """
                    SELECT SUM(ABS(d.Amount)) as opex
                    FROM DlyA d
                    JOIN Dlyndx n ON d.VchCode = n.VchCode
                    WHERE n.Draft = 2 
                    AND d.AtypeId IN (
                        '000010000100001', '000010000100002', '000010000100003', '000010000100004',
                        '000010000200001', '000010000200002', '000010000200003', '000010000200004',
                        '000010000300001', '000010000300002', '000010000300003', '000010000300004'
                    ) -- 各类费用科目
                    AND n.Date BETWEEN %s AND %s
                """
                cursor.execute(sql_opex, (start_str, f"{end_str} 23:59:59"))
                row = cursor.fetchone()
                opex = float(row['opex']) if row and row['opex'] else 0.0
                
                # 4. 计算财务指标
                gross_profit = revenue - cogs
                gross_margin = (gross_profit / revenue * 100) if revenue > 0 else 0.0
                ebit = gross_profit - opex
                net_profit = ebit  # 简化处理，假设税前利润等于EBIT
                net_margin = (net_profit / revenue * 100) if revenue > 0 else 0.0
                
                # 5. 人均产值 (需要员工数据)
                revenue_per_person = self._get_revenue_per_person(company_key, year, month, revenue)
                
                # 6. DSO (应收账款周转天数)
                dso = self._calculate_dso(company_key, cursor, year, month, revenue)
                
                # 7. DIO (库存周转天数)
                dio = self._calculate_dio(company_key, cursor, year, month, cogs)
                
                return MonthlyCompareData(
                    company_key=company_key,
                    revenue=revenue,
                    cogs=cogs,
                    gross_profit=gross_profit,
                    gross_margin=gross_margin,
                    opex=opex,
                    ebit=ebit,
                    net_profit=net_profit,
                    net_margin=net_margin,
                    revenue_per_person=revenue_per_person,
                    dso=dso,
                    dio=dio
                )
                
        except Exception as e:
            logger.error(f"获取 {company_key} 月度数据失败: {e}")
            raise e
        finally:
            if conn:
                conn.close()
    
    def _get_revenue_per_person(self, company_key: str, year: int, month: int, revenue: float) -> float:
        """计算人均产值"""
        try:
            conn_mysql = get_mysql_connection()
            with conn_mysql.cursor() as cursor:
                # 获取当月平均员工数
                sql = """
                    SELECT AVG(employee_count) as avg_employees
                    FROM hr_monthly_stats 
                    WHERE company_key = %s AND year = %s AND month = %s
                """
                cursor.execute(sql, (company_key, year, month))
                row = cursor.fetchone()
                
                if row and row['avg_employees'] and float(row['avg_employees']) > 0:
                    avg_employees = float(row['avg_employees'])
                    return revenue / avg_employees
                else:
                    return 0.0
            
            conn_mysql.close()
        except Exception as e:
            logger.warning(f"计算人均产值失败 {company_key}: {e}")
            return 0.0
    
    def _calculate_dso(self, company_key: str, cursor, year: int, month: int, revenue: float) -> float:
        """计算应收账款周转天数 (DSO)"""
        try:
            # 获取月末应收账款余额
            end_date = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year + 1, 1, 1) - timedelta(days=1)
            end_str = end_date.strftime('%Y-%m-%d')
            
            # 计算平均应收账款 (期初+期末)/2
            sql_avg_ar = """
                SELECT 
                    (期初应收 + 期末应收) / 2.0 as avg_ar
                FROM v_应收应付汇总
                WHERE 统计日期 = %s
            """
            cursor.execute(sql_avg_ar, (end_str,))
            row = cursor.fetchone()
            
            avg_ar = float(row['avg_ar']) if row and row['avg_ar'] else 0.0
            
            # DSO = (平均应收账款 / 月收入) * 30天
            if revenue > 0 and avg_ar > 0:
                return (avg_ar / revenue) * 30.0
            else:
                return 0.0
                
        except Exception as e:
            logger.warning(f"计算DSO失败 {company_key}: {e}")
            return 0.0
    
    def _calculate_dio(self, company_key: str, cursor, year: int, month: int, cogs: float) -> float:
        """计算库存周转天数 (DIO)"""
        try:
            # 获取月末库存余额
            end_date = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year + 1, 1, 1) - timedelta(days=1)
            end_str = end_date.strftime('%Y-%m-%d')
            
            # 计算平均库存 (期初+期末)/2
            sql_avg_inventory = """
                SELECT 
                    (期初库存 + 期末库存) / 2.0 as avg_inventory
                FROM v_库存汇总
                WHERE 统计日期 = %s
            """
            cursor.execute(sql_avg_inventory, (end_str,))
            row = cursor.fetchone()
            
            avg_inventory = float(row['avg_inventory']) if row and row['avg_inventory'] else 0.0
            
            # DIO = (平均库存 / 月销售成本) * 30天
            if cogs > 0 and avg_inventory > 0:
                return (avg_inventory / cogs) * 30.0
            else:
                return 0.0
                
        except Exception as e:
            logger.warning(f"计算DIO失败 {company_key}: {e}")
            return 0.0
    
    def _get_error_company_data(self, company_key: str) -> MonthlyCompareData:
        """返回错误状态的公司数据"""
        return MonthlyCompareData(
            company_key=company_key,
            revenue=0.0,
            cogs=0.0,
            gross_profit=0.0,
            gross_margin=0.0,
            opex=0.0,
            ebit=0.0,
            net_profit=0.0,
            net_margin=0.0,
            revenue_per_person=0.0,
            dso=0.0,
            dio=0.0
        )

# 创建服务实例
monthly_compare_service = MonthlyCompareService()

def get_monthly_compare_service():
    return monthly_compare_service