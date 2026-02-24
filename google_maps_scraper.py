#!/usr/bin/env python3
"""
Google Maps数据抓取脚本
用于搜索乌干达金贾地区的灯具客户联系方式
"""

import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GoogleMapsScraper:
    def __init__(self, headless=True):
        """初始化浏览器驱动"""
        self.options = Options()
        if headless:
            self.options.add_argument('--headless')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-blink-features=AutomationControlled')
        self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = None
        self.wait = None
    
    def start_browser(self):
        """启动浏览器"""
        try:
            self.driver = webdriver.Chrome(options=self.options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 10)
            logger.info("浏览器启动成功")
            return True
        except Exception as e:
            logger.error(f"浏览器启动失败: {e}")
            return False
    
    def search_businesses(self, location="Jinja, Uganda", business_type="lighting"):
        """搜索特定地区的商家"""
        try:
            # 打开Google Maps
            self.driver.get("https://www.google.com/maps")
            time.sleep(3)
            
            # 搜索框输入
            search_box = self.wait.until(
                EC.presence_of_element_located((By.ID, "searchboxinput"))
            )
            search_query = f"{business_type} in {location}"
            search_box.clear()
            search_box.send_keys(search_query)
            
            # 点击搜索按钮
            search_button = self.wait.until(
                EC.element_to_be_clickable((By.ID, "searchbox-searchbutton"))
            )
            search_button.click()
            time.sleep(5)
            
            logger.info(f"搜索完成: {search_query}")
            return True
            
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return False
    
    def extract_business_info(self):
        """提取商家信息"""
        businesses = []
        
        try:
            # 等待商家列表加载
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[role='feed']"))
            )
            
            # 获取商家卡片
            business_cards = self.driver.find_elements(By.CSS_SELECTOR, "[role='feed'] [role='article']")
            
            for card in business_cards[:10]:  # 限制前10个结果
                try:
                    business_info = {}
                    
                    # 商家名称
                    name_element = card.find_element(By.CSS_SELECTOR, "[role='heading']")
                    business_info['name'] = name_element.text if name_element else "N/A"
                    
                    # 评分
                    try:
                        rating_element = card.find_element(By.CSS_SELECTOR, "[aria-label*='stars']")
                        business_info['rating'] = rating_element.get_attribute('aria-label')
                    except:
                        business_info['rating'] = "N/A"
                    
                    # 地址
                    try:
                        address_element = card.find_element(By.CSS_SELECTOR, "[aria-label*='Address']")
                        business_info['address'] = address_element.text
                    except:
                        business_info['address'] = "N/A"
                    
                    # 电话号码（需要点击查看详情）
                    business_info['phone'] = "需要手动点击查看"
                    
                    businesses.append(business_info)
                    logger.info(f"提取商家: {business_info['name']}")
                    
                except Exception as e:
                    logger.warning(f"提取商家信息失败: {e}")
                    continue
            
            return businesses
            
        except Exception as e:
            logger.error(f"提取商家信息失败: {e}")
            return []
    
    def save_to_excel(self, businesses, filename="uganda_lighting_businesses.xlsx"):
        """保存数据到Excel"""
        try:
            df = pd.DataFrame(businesses)
            df.to_excel(filename, index=False)
            logger.info(f"数据已保存到: {filename}")
            return True
        except Exception as e:
            logger.error(f"保存Excel失败: {e}")
            return False
    
    def close(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            logger.info("浏览器已关闭")

def main():
    """主函数"""
    scraper = GoogleMapsScraper(headless=True)
    
    try:
        # 启动浏览器
        if not scraper.start_browser():
            return
        
        # 搜索商家
        if not scraper.search_businesses(location="Jinja, Uganda", business_type="lighting"):
            return
        
        # 提取信息
        businesses = scraper.extract_business_info()
        
        if businesses:
            # 保存到Excel
            scraper.save_to_excel(businesses)
            print(f"\n✅ 成功提取 {len(businesses)} 个商家信息")
            print("📊 数据已保存到: uganda_lighting_businesses.xlsx")
            
            # 显示预览
            df = pd.DataFrame(businesses)
            print("\n📋 数据预览:")
            print(df.head())
        else:
            print("❌ 未找到商家信息")
            
    except Exception as e:
        logger.error(f"主程序错误: {e}")
    finally:
        scraper.close()

if __name__ == "__main__":
    print("🚀 开始Google Maps数据抓取...")
    print("📍 目标: 乌干达金贾地区灯具客户")
    print("⏳ 预计耗时: 1-2分钟\n")
    
    main()
    
    print("\n💡 注意事项:")
    print("• 由于Google的反爬虫机制，电话号码可能需要手动点击查看")
    print("• 建议使用有头模式进行更详细的数据提取")
    print("• 可以修改脚本参数搜索其他地区或业务类型")