# -*- coding: utf-8 -*-
import requests
import mysql.connector
import pymssql
import re
import sys
import math
import logging
import json
import socket
import struct
import base64
import hashlib
import traceback
import xml.etree.ElementTree as ET
from datetime import datetime
from flask import Flask, request
from openai import OpenAI
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import config

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

client = OpenAI(api_key=config.AI_CONFIG['api_key'], base_url=config.AI_CONFIG['base_url'])
REGISTRATION_CACHE = {} 
AI_KNOWLEDGE_BASE = ""

# --- 别名与字段映射 ---
TABLE_ALIASES = {
    '欠款': 'v_应收应付', '应收': 'v_应收应付', '资金': 'v_门市资金日报表',
    '日报': 'v_门市资金日报表', '收款': 'v_客户收款表', '销售': 'v_2026年销售明细',
    '库存': 'v_成品存货库存余额表', '存货': 'v_成品存货库存余额表',
    '滞销': 'v_滞销存货表', '出入库': 'V_门市仓库每日出入库箱数',
    '热销': 'v_热销30款状态分析', '成品': 'v_成品出入库汇总表',
    '原材料': 'v_原材料出入库汇总表', '在仓': 'v_在仓可生产数',
    '缺料': 'v_在仓缺料查询表', '可销': 'v_未来可销天数', '天数': 'v_未来可销天数'
}
SUMMARY_FIELDS = ["仓库名称", "存货编号", "存货名称", "期初数量", "期初箱数", "入库数量", "入库箱数", "出库数量", "出库箱数", "库存数量", "库存箱数"]
SALES_DAYS_FIELDS = ["存货名称", "存货编号", "总箱数", "总可销天数", "在途可生产箱数", "在仓可生产箱数", "下单否", "排产否"]
SCENE_TRIGGERS = {'工厂': '工厂', '管理': '工厂', '车间': '工厂','海关': '海关', '餐饮': '餐饮', '商务': '商务', '照明': '照明', '工资': '工资', '购物': '购物'}
GENERAL_ENGLISH_TRIGGERS = ['英语', 'english', '学英语', '单词', '短语', '下一条', '继续']

def get_cloud_db(): return mysql.connector.connect(**config.SHARED_DB_CONFIG)
def get_erp_connection(key):
    c = config.ERP_CREDENTIALS.get(key, config.ERP_CREDENTIALS[config.DEFAULT_TENANT_KEY])
    return pymssql.connect(server=config.ERP_HOST, port=config.ERP_PORT, user=c['user'], password=c['pass'], database=c['db'])
def get_tenant_key(pid): return config.TENANTS.get(pid, config.DEFAULT_TENANT_KEY)

# --- 1. 英语教学模块 ---
def handle_english_learning(cat=None):
    try:
        conn = get_cloud_db()
        cur = conn.cursor(dictionary=True)
        rows = []
        if cat: 
            cur.execute(f"SELECT * FROM english_phrases WHERE category LIKE '%{cat}%' ORDER BY RAND() LIMIT 1")
            rows = cur.fetchall()
        if not rows:
            cur.execute("SELECT * FROM english_phrases ORDER BY RAND() LIMIT 1")
            rows = cur.fetchall()
        conn.close()
        
        if not rows: return "📚 题库建设中..."
        r = rows[0]
        base = f"### 🇺🇬 {r.get('category')}\n🗣️ **{r.get('english_phrase')}**\n🔊 {r.get('chinese_pinyin')}\n📝 {r.get('usage_note')}"
        prompt = f"我是乌干达工厂管理者。请教：'{r.get('english_phrase')}'。1.中文意思 2.当地口音例句 3.工头语气。"
        
        try:
            ai_resp = client.chat.completions.create(model="deepseek-chat", messages=[{"role":"user","content":prompt}], temperature=1.2).choices[0].message.content
        except Exception: ai_resp = "(AI 解析暂时不可用)"
        return base + "\n----\n" + ai_resp
    except Exception as e:
        logging.error(f"❌ 英语报错: {e}")
        return "AI 繁忙"

# --- 2. 报表查询模块 ---
def build_erp_sql(table, keys, tenant):
    cols = []
    if table in ['v_成品出入库汇总表', 'v_原材料出入库汇总表']: cols = SUMMARY_FIELDS
    elif table == 'v_未来可销天数': cols = SALES_DAYS_FIELDS
    else:
        try:
            conn = get_erp_connection(tenant)
            cur = conn.cursor(as_dict=True)
            cur.execute(f"SELECT TOP 1 * FROM {table}")
            cols = list(cur.fetchone().keys())
            conn.close()
        except: pass
    if not cols: return None
    
    sel = ", ".join(cols)
    sql = f"SELECT TOP 5 {sel} FROM {table}"
    if keys:
        conds = []
        for w in keys:
            conds.append(f"({' OR '.join([f'{c} LIKE \'%{w}%\'' for c in cols])})")
        sql += f" WHERE {' AND '.join(conds)}"
    return sql + f" ORDER BY {cols[0]} DESC"

def format_rows(table, rows):
    res = f"### 📂 {table.replace('v_', '')}\n"
    for r in rows:
        res += "----\n"
        for k, v in r.items():
            if '日期' in k: v = str(v).split(' ')[0]
            if '数量' in k or '金额' in k or '箱数' in k: res += f"{k}: **{v}**\n"
            else: res += f"{k}: {v}\n"
    return res + "\n"

# --- 3. 查产品/库存核心 (隐私铁律保护) ---
def process_product_query(text, tenant):
    # 提取型号
    clean = text.lower().replace('stock','').replace('库存','').strip()
    keys = [k for k in re.split(r'[,\s]+', clean) if len(k)>1]
    if not keys: return None
    
    # 明确是否要显示库存
    is_stock = 'stock' in text.lower() or '库存' in text
    cred = config.ERP_CREDENTIALS[tenant]
    
    # A. 查 MySQL (价格)
    local = {}
    try:
        conn = get_cloud_db()
        cur = conn.cursor(dictionary=True)
        price_clauses = [f"model_name LIKE '%{k}%'" for k in keys]
        sql = f"SELECT model_name, FORMAT(price_tier_1,0) as p1, packing_info FROM uganda_price_list WHERE {' OR '.join(price_clauses)} LIMIT 20"
        cur.execute(sql)
        for r in cur.fetchall(): local[str(r['model_name']).strip().upper()] = r
        conn.close()
    except Exception as e: logging.error(f"MySQL Error: {e}")
    
    # B. 查 ERP (证明产品存在并获取库存)
    remote = {}
    try:
        conn = get_erp_connection(tenant)
        cur = conn.cursor(as_dict=True)
        stock_clauses = [f"ModelNo LIKE '%{k}%'" for k in keys]
        sql = f"SELECT ModelNo, WarehouseName, Qty, Cartons FROM v_成品存货库存余额表 WHERE {' OR '.join(stock_clauses)}"
        cur.execute(sql)
        for r in cur.fetchall():
            m = str(r['ModelNo']).strip().upper()
            if m not in remote: remote[m] = []
            if r['Qty'] > 0:
                ctn = round(float(r['Cartons']),1) if r['Cartons'] else 0
                remote[m].append(f"{r['WarehouseName']}: {int(r['Qty'])} PCS ({ctn} CTN)")
        conn.close()
    except Exception as e: logging.error(f"MSSQL Error: {e}")
        
    models = set(local.keys()) | set(remote.keys())
    if not models: return None
    
    # C. 拼接回复
    res = f"🔎 {cred['name']}:\n"
    for m in sorted(models):
        res += f"\n📦 *{m}*"
        # 1. 报价格
        if m in local: res += f"\n💰 {cred['currency']} {local[m]['p1']} | {local[m]['packing_info']}"
        else: res += "\n💰 价格未录入系统"
        # 2. 报库存 (仅当用户要求查库存时，才透出数据)
        if is_stock:
            if m in remote and remote[m]:
                res += "\n🟢 Stock:"
                for l in remote[m]: res += f"\n   - {l}"
            else: res += "\n⚪ No Stock"
            
    return res

# --- 4. 企微分发逻辑 ---
def handle_wechat_logic(content, user, tenant):
    # 🔥 核心修复：清洗企业微信的 @机器人 字符
    content = re.sub(r'@\S+', '', content).strip()
    logging.info(f"👔 企微 [{tenant}] 查询: {content}")
    
    # 英语
    is_eng = False
    cat = None
    for k, v in SCENE_TRIGGERS.items():
        if k in content: is_eng=True; cat=v; break
    if not is_eng: 
        for k in GENERAL_ENGLISH_TRIGGERS:
            if k in content: is_eng=True; break
    if is_eng: return handle_english_learning(cat)

    # 报表
    tables = []
    keys = []
    for w in content.split():
        found = False
        for a, t in TABLE_ALIASES.items():
            if a in w:
                tables.append(t)
                cw = w.replace(a, '').replace('查', '')
                if cw: keys.append(cw)
                found = True
        if not found: keys.append(w)
    
    if tables:
        reply = ""
        for t in list(set(tables)):
            sql = build_erp_sql(t, keys, tenant)
            if not sql: continue
            try:
                conn = get_erp_connection(tenant)
                cur = conn.cursor(as_dict=True)
                cur.execute(sql)
                reply += format_rows(t, cur.fetchall())
                conn.close()
            except Exception as e: logging.error(f"❌ 报表查询报错: {e}")
        return reply if reply else "📭 无数据"

    # 产品
    return process_product_query(content, tenant) or "🤖 请尝试：'查库存 5098' 或 '英语'"

# --- 5. AI 营销模块 ---
def load_ai():
    global AI_KNOWLEDGE_BASE
    try:
        conn = get_erp_connection('UGANDA')
        cur = conn.cursor(as_dict=True)
        cur.execute("SELECT TOP 20 CategoryName, ModelNo FROM v_滞销AI推荐表")
        items = [f"{r['CategoryName']} {r['ModelNo']}" for r in cur.fetchall()]
        conn.close()
        AI_KNOWLEDGE_BASE = "Promo: " + ", ".join(items)
        logging.info(f"✅ 营销数据加载成功")
    except: 
        AI_KNOWLEDGE_BASE = ""

def get_ai_response(text):
    prompt = f"Role: Sales. {AI_KNOWLEDGE_BASE}. If 'Yes', ask Location. If 'Join', ask Name."
    try:
        return client.chat.completions.create(model="deepseek-chat", messages=[{"role":"system","content":prompt},{"role":"user","content":text}], temperature=1).choices[0].message.content
    except: return "Busy"

# --- 6. 加密组件 ---
class WXBizMsgCrypt:
    def __init__(self, token, encoding_aes_key, receive_id):
        self.key = base64.b64decode(encoding_aes_key + "=")
        self.token = token
        self.receive_id = receive_id.encode("utf-8")
    def get_signature(self, timestamp, nonce, encrypt):
        sort_list = [self.token, timestamp, nonce, encrypt]
        sort_list.sort()
        sha = hashlib.sha1()
        sha.update("".join(sort_list).encode("utf-8"))
        return sha.hexdigest()
    def decrypt(self, text, signature, timestamp, nonce):
        my_sig = self.get_signature(timestamp, nonce, text)
        if my_sig != signature: raise Exception("Sig Error")
        cryptor = Cipher(algorithms.AES(self.key), modes.CBC(self.key[:16]), backend=default_backend()).decryptor()
        plain_text = cryptor.update(base64.b64decode(text)) + cryptor.finalize()
        pad = plain_text[-1]
        content = plain_text[:-pad]
        xml_len = socket.ntohl(struct.unpack("I", content[16:20])[0])
        return content[20 : 20 + xml_len].decode("utf-8")

# ==================== 7. 路由入口 ====================
@app.route('/webhook', methods=['GET', 'POST'])
def whatsapp_webhook():
    if request.method == 'GET':
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if token == config.VERIFY_TOKEN: return challenge, 200
        return "Forbidden", 403

    try:
        data = request.json
        if data.get('object') == 'whatsapp_business_account':
            for entry in data['entry']:
                for change in entry['changes']:
                    val = change['value']
                    bot_id = val.get('metadata', {}).get('phone_number_id')
                    tenant = get_tenant_key(bot_id)
                    if val.get('messages'):
                        msg = val['messages'][0]
                        phone = msg['from']
                        
                        if msg['type'] == 'text':
                            txt = msg['text']['body'].strip()
                            if txt.lower() in ['join', 'register']:
                                REGISTRATION_CACHE[phone] = {'s': 1}
                                send_wa(phone, "Shop Name:", bot_id)
                            elif phone in REGISTRATION_CACHE:
                                s = REGISTRATION_CACHE[phone]
                                if s['s']==1:
                                    REGISTRATION_CACHE[phone]={'s':2, 'n':txt}
                                    send_wa(phone, "Send Location:", bot_id)
                            else:
                                resp = process_product_query(txt, tenant)
                                if not resp: resp = get_ai_response(txt)
                                send_wa(phone, resp, bot_id)
                        elif msg['type'] == 'location': pass # LBS 略
    except Exception as e: logging.error(f"WA Error: {e}")
    return "OK", 200

@app.route('/wechat', methods=['GET', 'POST'])
def wechat_webhook():
    agent = request.args.get('agent_id')
    if not agent or agent not in config.WX_AGENTS: return "403", 403
    conf = config.WX_AGENTS[agent]
    wxcrypt = WXBizMsgCrypt(conf['token'], conf['aes_key'], config.WX_CORP_ID)
    
    if request.method == 'GET':
        try: return wxcrypt.decrypt(request.args.get('echostr'), request.args.get('msg_signature'), request.args.get('timestamp'), request.args.get('nonce'))
        except: return "Verify Failed", 403

    try:
        req_json = request.get_json(force=True, silent=True)
        if req_json:
            decrypted = wxcrypt.decrypt(req_json.get('encrypt'), request.args.get('msg_signature'), request.args.get('timestamp'), request.args.get('nonce'))
            msg = json.loads(decrypted)
            if msg.get('msgtype') == 'text':
                txt = msg['text']['content']
                reply = handle_wechat_logic(txt, msg['from']['userid'], conf['tenant_key'])
                if reply and msg.get('response_url'):
                    requests.post(msg['response_url'], json={"msgtype": "markdown", "markdown": {"content": reply}})
            return "success"
    except Exception as e: logging.error(f"WX Error: {e}")
    return "success"

def send_wa(to, body, sid):
    url = f"https://graph.facebook.com/v17.0/{sid}/messages"
    try: requests.post(url, headers={"Authorization": f"Bearer {config.ACCESS_TOKEN}", "Content-Type": "application/json"}, json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": body}})
    except: pass

if __name__ == '__main__':
    load_ai()
    app.run(host='0.0.0.0', port=8084)