# -*- coding: utf-8 -*-
# config.py - Dplight 全球核心配置

# ==================== 1. AI 配置 ====================
AI_CONFIG = {
    "api_key": "sk-bc25ffa2c6644689b8ec1b8314b80c48", 
    "base_url": "https://api.deepseek.com"
}

# ==================== 2. 云数据库 (新加坡) ====================
SHARED_DB_CONFIG = {
    'host': '10.3.4.6',
    'port': 3306,
    'user': 'root',
    'password': 'Mediasoft,.123',
    'database': 'hy_gjp_syn',
    'raise_on_warnings': True
}

# ==================== 3. ERP 连接 ====================
ERP_HOST = 'cmal_hk001-ww.rwxyun.site'
ERP_PORT = 3433

# ==================== 4. 多租户映射 ====================
TENANTS = {
    '1036911956161458': 'UGANDA',
}

# ==================== 5. ERP 凭证库 (核心业务配置) ====================
ERP_CREDENTIALS = {
    'UGANDA': { 
        'name': '🇺🇬 乌干达', 
        'currency': 'UGX', 
        'user': 'ywszmjckyxgs_ggfn599939', 'pass': '0Nk107HO-321S!-_', 'db': 'CMCSYUN532502',
        'business_rules': {
            'finished_types': ['00002'], 
            'material_types': ['00001', '00003', '00004', '00005', '00006'],
            'default_wh_finished': ['门市仓库', '辽沈成品仓'],
            'default_wh_material': ['辽沈原料仓']
        }
    },
    
    'NIGERIA': { 
        'name': '🇳🇬 尼日利亚', 
        'currency': 'NGN', 
        'user': 'hzgjmy616329', 'pass': 'axup_-22637483', 'db': 'CMCSYUN355738',
        'business_rules': {
            'finished_types': ['00003'],
            'material_types': ['00001', '00127', '00002'],
            'default_wh_finished': ['Alaba仓库', '工厂成品仓'],
            'default_wh_material': ['工厂原料仓', 'ALLIPU注塑仓库']
        }
    },
    
    'KENYA': { 
        'name': '🇰🇪 肯尼亚', 
        'currency': 'KES', 
        'user': 'ywszmjckyxgs_ggfn599939', 'pass': '0Nk107HO-321S!-_', 'db': 'CMCSYUN4348395',
        'business_rules': {
            'finished_types': ['00003'],
            'material_types': ['00001', '00004', '00005', '00007', '00009', '00010', '00011', '00012', '00013', '00002'],
            'default_wh_finished': ['肯尼亚成品仓库'],
            'default_wh_material': ['肯尼亚原料仓库', '福盛仓库', '义乌仓库']
        }
    },
    
    'DRC': { 
        'name': '🇨🇩 刚果金', 
        'currency': 'USD', 
        'user': 'hzgjmy616329', 'pass': 'axup_-22637483', 'db': 'CMCSYUN983044',
        'business_rules': {
            'finished_types': ['00002'],
            'material_types': ['00001'],
            'default_wh_finished': [],
            'default_wh_material': []
        }
    },
    
    'KENYA_AUDIO': { 
        'name': '🇰🇪 肯尼亚音响厂', 
        'currency': 'KES', 
        'user': 'hzgjmy616329', 'pass': 'axup_-22637483', 'db': 'CMCSYUN650929',
        'business_rules': {
            'finished_types': ['00002'],
            'material_types': ['00001'],
            'default_wh_finished': [],
            'default_wh_material': []
        }
    }
}
DEFAULT_TENANT_KEY = 'UGANDA'

# ==================== 6. WhatsApp Token ====================
ACCESS_TOKEN = "EAAcsondWjEwBQuXQCrxaLFLaCwfQd2AQe1iaRa1GX9yxHJgqoZAgKNgZBvwJxE7TrIm68Tk8wHJrN7muwJN2FJTi4wXChuMiI5NMXyGiFEE1GPB8mUQJTkVQTHli2nznUGy4RGu2STsqXimqrUvxvZAL7dm1C3mpTeH55XYSnc8ZB4myx5rLa0iZA59DbjgZDZD"
VERIFY_TOKEN = "123321"

# ==================== 7. 企业微信应用配置 ====================
WX_CORP_ID = "wwb359b2ee13420d5c"

WX_AGENTS = {
    '1000002': { 'token': 'UvmhUYxAyBWUW', 'aes_key': 'grnJavgMnaq29Gcfn5HZkYvdGT1AOtYOehvtACDObkl', 'tenant_key': 'UGANDA' },
    '1000003': { 'token': '', 'aes_key': '', 'tenant_key': 'KENYA' }
}

# ==================== 8. 群机器人 Webhook ====================
REPORT_WEBHOOKS = {
    'UGANDA': "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=d553db4b-92b0-4e02-a42f-e2503efaad93",
    'KENYA': ""
}

# ==================== 9. 用户权限 (Web登录) ====================
USER_ACCESS = {
    # 密码 : [可访问的 Tenant Key]
    "ug888,": ["UGANDA"],
    "ng999.": ["NIGERIA"],
    "ky888,.": ["KENYA", "KENYA_AUDIO"], 
    "boss888": ["UGANDA", "NIGERIA", "KENYA", "KENYA_AUDIO", "DRC"], 
    "demo888,": ["UGANDA"]
}

# ==================== 10. 敏感报表配置 ====================
SENSITIVE_MENUS = [
    "应收款查询", 
    "费用查询", 
    "资金查询", 
    "计件工资表", 
    "系统日志"
]

# 默认解锁密码 (模块内部使用)
DEFAULT_PASSWORD = "f888"