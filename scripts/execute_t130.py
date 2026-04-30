#!/usr/bin/env python3
"""
执行任务T130 - 写入留言板
"""
import os
import json
import urllib.request

# 从.env加载环境变量
def load_env():
    env_paths = [
        '/root/.hermes/.env',
        '/home/vip/.hermes/.env',
        os.path.expanduser('~/.hermes/.env')
    ]
    for path in env_paths:
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        if key not in os.environ:
                            os.environ[key] = value
            break

load_env()

FEISHU_APP_ID = os.environ.get('FEISHU_APP_ID', '')
FEISHU_APP_SECRET = os.environ.get('FEISHU_APP_SECRET', '')

def get_token():
    """获取飞书token"""
    url = 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal'
    data = json.dumps({
        'app_id': FEISHU_APP_ID,
        'app_secret': FEISHU_APP_SECRET
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, headers={
        'Content-Type': 'application/json'
    })
    
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        return result.get('tenant_access_token')

def append_to_doc(token, doc_id, content):
    """追加内容到文档"""
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
    data = json.dumps({
        'children': [{'block_type': 2, 'text': {'elements': [{'text_run': {'content': content}}]}}]
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json; charset=utf-8'
    }, method='POST')
    
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        return result.get('code') == 0

# 执行
token = get_token()
if token:
    doc_id = 'TEX4dNfijoZOKWxB6jMccJO6nCr'
    content = '✅ T130完成'
    if append_to_doc(token, doc_id, content):
        print(f"[成功] 已写入留言板: {content}")
    else:
        print("[失败] 写入失败")
else:
    print("[失败] 获取token失败")