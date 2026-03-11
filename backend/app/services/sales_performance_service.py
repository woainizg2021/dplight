from datetime import datetime, date
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from app.db.mssql import get_db_connection
from app.db.mysql import get_mysql_connection
from app.core.cache import cache_service
from app.core.config import settings
from app.models.schemas import SalesPerformanceResponse, SalesPerformanceData
import logging

logger = logging.getLogger(__name__)

class SalesPerformanceService:
    
    # 公司名称映射
    COMPANY_NAMES = {
        "UGANDA": {"short_name": "乌干达", "full_name": "乌干达灯具制造"},
        "NIGERIA": {"short_name": "尼日利亚", "full_name": "尼日利亚灯具制造"},
        "KENYA": {"short_name": "肯尼亚", "full_name": "肯尼亚灯具制造"},
        "KENYA_AUDIO": {"short_name": "肯尼亚音箱", "full_name": "肯尼亚音箱制造"},
        "DRC": {"short_name": "刚果金", "full_name": "刚果金灯具制造"}
    }
    
    def get_sales_performance(self, year: int, month: int, period_type: str = "month") -> SalesPerformanceResponse:
        """获取销售绩效数据 - 各公司目标vs实际完成情况"""
        
        cache_key = f"dashboard:sales-performance:{year}:{month}:{period_type}"
        
        # 尝试缓存
        cached = cache_service.get(cache_key)
        if cached:
            return SalesPerformanceResponse(**cached)
        
        # 并行获取所有公司数据
        data = []
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_company = {
                executor.submit(self._get_company_sales_performance, company, year, month, period_type): company
                for company in settings.COMPANY_DB_MAP.keys()
            }
            
            for future in future_to_company:
                company_key = future_to_company[future]
                try:
                    company_data = future.result()
                    data.append(company_data)
                except Exception as e:
                    logger.error(f"获取 {company_key} 销售绩效数据失败: {e}")
                    # 返回错误状态的数据
                    data.append(self._get_error_company_data(company_key))
        
        # 按指定顺序排序
        order = ['UGANDA', 'NIGERIA', 'KENYA', 'KENYA_AUDIO', 'DRC']
        data.sort(key=lambda x: order.index(x.company_key) if x.company_key in order else 99)
        
        result = SalesPerformanceResponse(data=data)
        
        # 缓存结果 (1小时TTL)
        cache_service.set(cache_key, result.model_dump(), settings.MONTHLY_CACHE_TTL)
        
        return result
    
    def _get_company_sales_performance(self, company_key: str, year: int, month: int, period_type: str) -> SalesPerformanceData:
        """获取单个公司销售绩效数据"""
        
        # 根据period_type确定日期范围
        if period_type == "quarter":
            # 季度数据
            quarter = (month - 1) // 3 + 1
            start_month = (quarter - 1) * 3 + 1
            end_month = quarter * 3
            
            start_date = date(year, start_month, 1)
            if end_month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, end_month + 1, 1) - timedelta(days=1)
        elif period_type == "year":
            # 年度数据
            start_date = date(year, 1, 1)
            end_date = date(year, 12, 31)
        else:
            # 月度数据 (默认)
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
                
                # 1. 实际销售额
                sql_actual = """
                    SELECT SUM(ABS(Total)) as actual_sales
                    FROM Dlyndx 
                    WHERE VchType = 11 AND Draft = 2 
                    AND Date BETWEEN %s AND %s
                """
                cursor.execute(sql_actual, (start_str, f"{end_str} 23:59:59"))
                row = cursor.fetchone()
                actual = float(row['actual_sales']) if row and row['actual_sales'] else 0.0
                
                # 2. 销售目标 (从MySQL预算表)
                target = self._get_sales_target(company_key, year, month, period_type)
                
                # 3. 完成率
                completion_rate = (actual / target * 100) if target > 0 else 0.0
                
                # 4. 同比 (与去年同期对比)
                yoy = self._calculate_yoy(company_key, cursor, year, month, period_type, actual)
                
                # 5. 环比 (与上期对比)
                mom = self._calculate_mom(company_key, cursor, year, month, period_type, actual)
                
                return SalesPerformanceData(
                    company_key=company_key,
                    target=target,
                    actual=actual,
                    completion_rate=completion_rate,
                    yoy=yoy,
                    mom=mom
                )
                
        except Exception as e:
            logger.error(f"获取 {company_key} 销售绩效数据失败: {e}")
            raise e
        finally:
            if conn:
                conn.close()
    
    def _get_sales_target(self, company_key: str, year: int, month: int, period_type: str) -> float:
        """获取销售目标"""
        try:
            conn_mysql = get_mysql_connection()
            with conn_mysql.cursor() as cursor:
                
                if period_type == "quarter":
                    quarter = (month - 1) // 3 + 1
                    sql = """
                        SELECT SUM(target_amount) as total_target
                        FROM sales_targets 
                        WHERE company_key = %s AND year = %s 
                        AND QUARTER(STR_TO_DATE(CONCAT(year, '-', month, '-01'), '%Y-%m-%d')) = %s
                        GROUP BY company_key, year, QUARTER(STR_TO_DATE(CONCAT(year, '-', month, '-01'), '%Y-%m-%d'))
                    """
                    cursor.execute(sql, (company_key, year, quarter))
                elif period_type == "year":
                    sql = """
                        SELECT SUM(target_amount) as total_target
                        FROM sales_targets 
                        WHERE company_key = %s AND year = %s
                        GROUP BY company_key, year
                    """
                    cursor.execute(sql, (company_key, year))
                else:
                    sql = """
                        SELECT target_amount
                        FROM sales_targets 
                        WHERE company_key = %s AND year = %s AND month = %s
                    """
                    cursor.execute(sql, (company_key, year, month))
                
                row = cursor.fetchone()
                target = float(row['total_target']) if row and row.get('total_target') else (
                    float(row['target_amount']) if row and row.get('target_amount') else 0.0
                )
                
                conn_mysql.close()
                return target
                
        except Exception as e:
            logger.warning(f"获取销售目标失败 {company_key}: {e}")
            return 0.0
    
    def _calculate_yoy(self, company_key: str, cursor, year: int, month: int, period_type: str, current_actual: float) -> float:
        """计算同比增长率"""
        try:
            # 去年同期数据
            last_year = year - 1
            
            if period_type == "quarter":
                quarter = (month - 1) // 3 + 1
                start_month = (quarter - 1) * 3 + 1
                end_month = quarter * 3
                
                start_date = date(last_year, start_month, 1)
                if end_month == 12:
                    end_date = date(last_year + 1, 1, 1) - timedelta(days=1)
                else:
                    end_date = date(last_year, end_month + 1, 1) - timedelta(days=1)
            elif period_type == "year":
                start_date = date(last_year, 1, 1)
                end_date = date(last_year, 12, 31)
            else:
                start_date = date(last_year, month, 1)
                if month == 12:
                    end_date = date(last_year + 1, 1, 1) - timedelta(days=1)
                else:
                    end_date = date(last_year, month + 1, 1) - timedelta(days=1)
            
            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            
            sql_last_year = """
                SELECT SUM(ABS(Total)) as last_year_sales
                FROM Dlyndx 
                WHERE VchType = 11 AND Draft = 2 
                AND Date BETWEEN %s AND %s
            """
            cursor.execute(sql_last_year, (start_str, f"{end_str} 23:59:59"))
            row = cursor.fetchone()
            last_year_actual = float(row['last_year_sales']) if row and row['last_year_sales'] else 0.0
            
            # 计算同比增长率
            if last_year_actual > 0:
                return ((current_actual - last_year_actual) / last_year_actual * 100)
            else:
                return 0.0
                
        except Exception as e:
            logger.warning(f"计算同比增长率失败 {company_key}: {e}")
            return 0.0
    
    def _calculate_mom(self, company_key: str, cursor, year: int, month: int, period_type: str, current_actual: float) -> float:
        """计算环比增长率"""
        try:
            # 上期数据
            if period_type == "quarter":
                current_quarter = (month - 1) // 3 + 1
                if current_quarter > 1:
                    last_quarter = current_quarter - 1
                    last_year = year
                else:
                    last_quarter = 4
                    last_year = year - 1
                
                start_month = (last_quarter - 1) * 3 + 1
                end_month = last_quarter * 3
                
                start_date = date(last_year, start_month, 1)
                if end_month == 12:
                    end_date = date(last_year + 1, 1, 1) - timedelta(days=1)
                else:
                    end_date = date(last_year, end_month + 1, 1) - timedelta(days=1)
            elif period_type == "year":
                # 年度环比就是同比
                return self._calculate_yoy(company_key, cursor, year, month, period_type, current_actual)
            else:
                # 月度环比
                if month > 1:
                    last_month = month - 1
                    last_year = year
                else:
                    last_month = 12
                    last_year = year - 1
                
                start_date = date(last_year, last_month, 1)
                if last_month == 12:
                    end_date = date(last_year + 1, 1, 1) - timedelta(days=1)
                else:
                    end_date = date(last_year, last_month + 1, 1) - timedelta(days=1)
            
            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            
            sql_last_period = """
                SELECT SUM(ABS(Total)) as last_period_sales
                FROM Dlyndx 
                WHERE VchType = 11 AND Draft = 2 
                AND Date BETWEEN %s AND %s
            """
            cursor.execute(sql_last_period, (start_str, f"{end_str} 23:59:59"))
            row = cursor.fetchone()
            last_period_actual = float(row['last_period_sales']) if row and row['last_period_sales'] else 0.0
            
            # 计算环比增长率
            if last_period_actual > 0:
                return ((current_actual - last_period_actual) / last_period_actual * 100)
            else:
                return 0.0
                
        except Exception as e:
            logger.warning(f"计算环比增长率失败 {company_key}: {e}")
            return 0.0
    
    def _get_error_company_data(self, company_key: str) -> SalesPerformanceData:
        """返回错误状态的公司数据"""
        return SalesPerformanceData(
            company_key=company_key,
            target=0.0,
            actual=0.0,
            completion_rate=0.0,
            yoy=0.0,
            mom=0.0
        )

# 创建服务实例
sales_performance_service = SalesPerformanceService()

def get_sales_performance_service():
    return sales_performance_service