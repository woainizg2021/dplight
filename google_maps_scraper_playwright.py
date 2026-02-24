#!/usr/bin/env python3
"""
Google Maps数据抓取脚本（Playwright版本）
用于搜索乌干达金贾地区的灯具客户联系方式
"""

import time
import pandas as pd
from playwright.sync_api import sync_playwright
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GoogleMapsScraper:
    def __init__(self, headless=True):
        """初始化Playwright"""
        self.headless = headless
        self.browser = None
        self.page = None
        self.playwright = None
    
    def start_browser(self):
        """启动浏览器"""
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.firefox.launch(headless=self.headless)
            self.page = self.browser.new_page()
            
            # 设置用户代理和视口
            self.page.set_viewport_size({"width": 1920, "height": 1080})
            
            logger.info("浏览器启动成功")
            return True
        except Exception as e:
            logger.error(f"浏览器启动失败: {e}")
            return False
    
    def search_businesses(self, location="Jinja, Uganda", business_type="lighting"):
        """搜索特定地区的商家"""
        try:
            # 打开Google Maps
            self.page.goto("https://www.google.com/maps", wait_until="networkidle")
            time.sleep(3)
            
            # 等待搜索框加载并输入
            search_box = self.page.wait_for_selector("#searchboxinput", timeout=10000)
            search_query = f"{business_type} in {location}"
            search_box.fill(search_query)
            
            # 点击搜索按钮
            search_button = self.page.wait_for_selector("#searchbox-searchbutton", timeout=10000)
            search_button.click()
            
            # 等待搜索结果加载
            self.page.wait_for_selector("[role='feed']", timeout=15000)
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
            # 获取商家卡片
            business_cards = self.page.query_selector_all("[role='feed'] [role='article']")
            
            for card in business_cards[:10]:  # 限制前10个结果
                try:
                    business_info = {}
                    
                    # 商家名称
                    name_element = card.query_selector("[role='heading']")
                    business_info['name'] = name_element.inner_text() if name_element else "N/A"
                    
                    # 评分
                    try:
                        rating_element = card.query_selector("[aria-label*='stars']")
                        business_info['rating'] = rating_element.get_attribute('aria-label') if rating_element else "N/A"
                    except:
                        business_info['rating'] = "N/A"
                    
                    # 地址
                    try:
                        address_element = card.query_selector("[aria-label*='Address']")
                        business_info['address'] = address_element.inner_text() if address_element else "N/A"
                    except:
                        business_info['address'] = "N/A"
                    
                    # 类别
                    try:
                        category_element = card.query_selector("[jsaction*='category']")
                        business_info['category'] = category_element.inner_text() if category_element else "N/A"
                    except:
                        business_info['category'] = "N/A"
                    
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
    
    def take_screenshot(self, filename="search_results.png"):
        """截取搜索结果截图"""
        try:
            self.page.screenshot(path=filename)
            logger.info(f"截图已保存: {filename}")
        except Exception as e:
            logger.error(f"截图失败: {e}")
    
    def close(self):
        """关闭浏览器"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        logger.info("浏览器已关闭")

def main():
    """主函数"""
    scraper = GoogleMapsScraper(headless=True)
    
    try:
        # 启动浏览器
        if not scraper.start_browser():
            print("❌ 浏览器启动失败")
            return
        
        # 搜索商家
        print("🔍 正在搜索乌干达金贾地区的灯具商家...")
        if not scraper.search_businesses(location="Jinja, Uganda", business_type="lighting"):
            print("❌ 搜索失败")
            return
        
        # 截取搜索结果
        scraper.take_screenshot("search_results.png")
        
        # 提取信息
        print("📊 正在提取商家信息...")
        businesses = scraper.extract_business_info()
        
        if businesses:
            # 保存到Excel
            scraper.save_to_excel(businesses)
            print(f"\n✅ 成功提取 {len(businesses)} 个商家信息")
            print("📊 数据已保存到: uganda_lighting_businesses.xlsx")
            print("🖼️  截图已保存到: search_results.png")
            
            # 显示预览
            df = pd.DataFrame(businesses)
            print("\n📋 数据预览:")
            print(df.head())
        else:
            print("❌ 未找到商家信息")
            
    except Exception as e:
        logger.error(f"主程序错误: {e}")
        print(f"❌ 程序执行出错: {e}")
    finally:
        scraper.close()

if __name__ == "__main__":
    print("🚀 开始Google Maps数据抓取（Playwright版本）...")
    print("📍 目标: 乌干达金贾地区灯具客户")
    print("🌐 使用浏览器: Firefox")
    print("⏳ 预计耗时: 1-2分钟\n")
    
    main()
    
    print("\n💡 注意事项:")
    print("• 由于Google的反爬虫机制，电话号码可能需要手动点击查看")
    print("• 可以修改脚本参数搜索其他地区或业务类型")
    print("• 截图文件可用于验证搜索结果")