# -*- coding: utf-8 -*-
import pymssql
import requests
import datetime
import sys
import io
import calendar
import random
import config

# 强制设置标准输出为 UTF-8，解决 Linux 下中文乱码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def get_db(k):
    c = config.ERP_CREDENTIALS.get(k)
    return pymssql.connect(
        server=config.ERP_HOST, 
        port=config.ERP_PORT, 
        user=c['user'], 
        password=c['pass'], 
        database=c['db'],
        charset='utf8' 
    )

def send(k, title, txt):
    url = config.REPORT_WEBHOOKS.get(k)
    if url: 
        requests.post(url, json={"msgtype": "markdown", "markdown": {"content": f"### {title}\n{txt}"}})
        print(f"✅ 发送成功: {title}")
    else:
        print(f"❌ 未找到 Webhook配置: {k}")

# --- 1. 生产报表 ---
def run_prod(k):
    today = datetime.datetime.now()
    m_str = today.strftime("%Y-%m")
    m_int = today.month
    
    try:
        conn = get_db(k)
        cur = conn.cursor(as_dict=True)
        # 严格遵守防乱码铁律：RTRIM(CAST())
        sql = f"""
            SELECT 
                t.[产品名称], t.[目标箱数], t.[实际箱数], t.[完成率],
                ISNULL(s.[2025全年销量_箱], 0) as [去年销量]
            FROM v_生产目标进度_sku明细 t
            LEFT JOIN v_dplight_rx32xsxs s ON RTRIM(CAST(t.typeid AS NVARCHAR(50))) = RTRIM(CAST(s.typeid AS NVARCHAR(50)))
            WHERE t.月份数字 = {m_int}
        """
        cur.execute(sql)
        rows = cur.fetchall()
        conn.close()
        
        if not rows: return
        
        total_target = sum(float(r['目标箱数'] or 0) for r in rows)
        total_actual = sum(float(r['实际箱数'] or 0) for r in rows)
        
        last_day = calendar.monthrange(today.year, today.month)[1]
        days_left = max(1, last_day - today.day + 1)
        daily_needed = max(0, (total_target - total_actual) / days_left)
        
        time_progress = (today.day / last_day) * 100
        lagging = [r for r in rows if float(str(r.get('完成率', 0)).replace('%','')) < time_progress]
        zero_prod = [r for r in rows if float(r.get('实际箱数', 0)) <= 0 and float(r.get('目标箱数', 0)) > 0]
        priority_alerts = sorted([r for r in lagging if r['去年销量'] > 0], key=lambda x: x['去年销量'], reverse=True)[:5]

        msg = f"🏭 **生产进度看板 ({m_str})**\n📊 整体进度: `{total_actual:,.0f}` / `{total_target:,.0f}` 箱\n"
        msg += f"📅 **热销款日均需产：`{daily_needed:.1f}` 箱**\n"
        msg += f"----------------\n"
        msg += f"⚠️ **风险摘要：**\n"
        msg += f"> ❌ 滞后型号：`{len(lagging)}` 款\n"
        msg += f"> 🚫 未开工款：`{len(zero_prod)}` 款\n"
        
        if priority_alerts:
            msg += f"\n🔥 **重点款追赶预警：**\n"
            for r in priority_alerts:
                msg += f"> **{r['产品名称']}**\n"
                msg += f"> 🎯{int(float(r['目标箱数']))} | 📦{int(float(r['实际箱数']))} | ⏳{r['完成率']}\n"

        send(k, f"🏭 {k} 生产监控周报", msg)
    except Exception as e:
        print(f"❌ 生产报表报错: {e}")

# --- 2. 销售日报 ---
def run_sales_daily(k):
    now = datetime.datetime.now()
    m_curr = now.strftime("%Y-%m")
    m_prev = (now.replace(day=1) - datetime.timedelta(days=1)).strftime("%Y-%m")
    m_last_year = (now.replace(year=now.year - 1)).strftime("%Y-%m")
    
    try:
        conn = get_db(k)
        cur = conn.cursor(as_dict=True)
        # 注意: 如果 v_销售目标进度查询 未处理单据负数翻转(11, 45)，需底层视图重构
        sql = f"""
            SELECT 月份, 销售额, UGX, 完成率, 月状态
            FROM v_销售目标进度查询 
            WHERE 月份 IN ('{m_curr}', '{m_prev}', '{m_last_year}')
        """
        cur.execute(sql)
        rows = cur.fetchall()
        conn.close()
        
        if not rows: return
        
        data_map = {r['月份']: r for r in rows}
        curr = data_map.get(m_curr)
        if not curr: return
        
        curr_val = float(curr.get('销售额') or 0)
        prev_val = float(data_map.get(m_prev, {}).get('销售额') or 0)
        year_val = float(data_map.get(m_last_year, {}).get('销售额') or 0)
        
        mom_growth = f"{((curr_val - prev_val) / prev_val * 100):+.1f}%" if prev_val else "数据不足"
        yoy_growth = f"{((curr_val - year_val) / year_val * 100):+.1f}%" if year_val else "数据不足"
        
        msg = f"📅 **本月战报 ({m_curr})**\n"
        msg += f"🎯 目标: {curr.get('UGX')}万\n"
        msg += f"💰 已完: `{curr_val}`万\n"
        msg += f"📊 进度: {curr.get('完成率')}%\n"
        msg += f"📈 环比 (vs 上月): `{mom_growth}`\n"
        msg += f"📉 同比 (vs 去年): `{yoy_growth}`\n"
        msg += f"🚩 状态: {curr.get('月状态')}"
        
        send(k, f"📈 {k} 销售战报", msg)
    except Exception as e:
        print(f"❌ 销售报表报错: {e}")

# --- 3. 业务员排行 ---
def run_ranking(k):
    try:
        conn = get_db(k)
        cur = conn.cursor(as_dict=True)
        today = datetime.datetime.now()
        day_of_month = today.day
        days_in_month = calendar.monthrange(today.year, today.month)[1]
        time_passed_pct = (day_of_month / days_in_month) * 100

        safe_rate = "CASE WHEN p.UnitRate1 IS NULL OR ISNUMERIC(p.UnitRate1) = 0 OR CAST(p.UnitRate1 AS DECIMAL(18,4)) = 0 THEN 1 ELSE CAST(p.UnitRate1 AS DECIMAL(18,4)) END"
        
        # 修正：1. 遵守防乱码铁律 RTRIM(CAST())  2. 移除硬编码ID，改用非空过滤以适配多国
        sql = f"""
            SELECT t.业务员, SUM(t.金额) as 总金额, SUM(t.数量 / {safe_rate}) as 总箱数
            FROM v_业务员销售明细 t
            LEFT JOIN Ptype p ON RTRIM(CAST(t.存货编号 AS NVARCHAR(50))) = RTRIM(CAST(p.TypeID AS NVARCHAR(50)))
            WHERE ISNULL(t.业务员, '') <> '' 
              AND DATEDIFF(month, t.日期, GETDATE()) = 0
            GROUP BY t.业务员 
            HAVING SUM(t.金额) > 0
            ORDER BY 总金额 DESC
        """
        cur.execute(sql)
        rows = cur.fetchall()
        conn.close()
        
        if not rows: return

        total_all = sum(r['总金额'] for r in rows)
        projected_final = (total_all / day_of_month) * days_in_month
        
        msg = f"🏆 **业务员排行 (Current Month)**\n"
        msg += f"📅 时间进度: `{time_passed_pct:.1f}%` ({day_of_month}/{days_in_month}天)\n"
        msg += f"----------------"

        prev_amount = 0
        for i, r in enumerate(rows):
            name = r['业务员']
            if name == 'SHOP': name = 'SHOP (门)'
            amount = int(r['总金额'] or 0)
            boxes = float(r['总箱数'] or 0)
            
            icon = "🥇" if i==0 else "🥈" if i==1 else "🥉" if i==2 else "👤"
            gap_str = ""
            if i > 0:
                gap = prev_amount - amount
                gap_str = f" | 🚩距上名: `{gap:,}`"
            
            msg += f"\n{icon} **{name}**\n   💰 `{amount:,}` UGX | 📦 `{boxes:.1f}` Box{gap_str}"
            prev_amount = amount

        msg += f"\n----------------\n"
        msg += f"🌍 **TEAM TOTAL: `{total_all:,}`**\n"
        msg += f"🚀 **月底预测: `{projected_final:,.0f}`**\n"
        
        send(k, f"🏆 {k} 业务员排行", msg)
    except Exception as e:
        print(f"❌ 排行榜报错: {e}")

# --- 4. 每日英语定时推送 (补全目标3) ---
def run_english(k):
    try:
        import pymysql
        # 连接云端 MySQL 获取题库
        conn = pymysql.connect(**config.SHARED_DB_CONFIG)
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT * FROM english_phrases ORDER BY RAND() LIMIT 1")
            row = cur.fetchone()
        conn.close()
        
        if not row: return
        
        # 构建推送内容 (无需调用大模型，直接推标准学习卡片)
        msg = f"### 🇺🇬 每日英语时刻 (Daily English)\n"
        msg += f"**场景**: {row.get('category', '日常交流')}\n"
        msg += f"----------------\n"
        msg += f"🗣️ **{row.get('english_phrase')}**\n\n"
        msg += f"🔊 中文音译: {row.get('chinese_pinyin')}\n"
        msg += f"📝 语境与用法: {row.get('usage_note')}\n\n"
        msg += f"💡 *回复机器人对应的场景词(如'车间')可进行AI对话练习*"
        
        send(k, f"📚 {k} 每日英语", msg)
    except Exception as e:
        print(f"❌ 英语推送报错: {e}")

if __name__ == '__main__':
    if len(sys.argv) > 2:
        action = sys.argv[1]
        country = sys.argv[2]
        if action == 'prod': run_prod(country)
        elif action == 'daily': run_sales_daily(country)
        elif action == 'rank': run_ranking(country)
        elif action == 'english': run_english(country)  # 新增执行入口
    else:
        print("Usage: python report_runner.py [daily/prod/rank/english] [UGANDA/KENYA]")