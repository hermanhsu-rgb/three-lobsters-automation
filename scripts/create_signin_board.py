#!/usr/bin/env python3
"""
爱马仕PM专用 - 每6小时创建新签到留言板
"""
import urllib.request
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('/root/.hermes/.env')

APP_ID = os.environ.get('FEISHU_APP_ID')
APP_SECRET = os.environ.get('FEISHU_APP_SECRET')
SIGNIN_FOLDER_ID = 'TUcWf6Kyql4d6gdi1nWc7TxVnDe'


def get_token():
    url = 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal'
    data = json.dumps({'app_id': APP_ID, 'app_secret': APP_SECRET}).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        return result.get('tenant_access_token')


def get_time_period():
    """获取当前时段开始时间"""
    hour = datetime.now().hour
    if 0 <= hour < 6:
        return '00'
    elif 6 <= hour < 12:
        return '06'
    elif 12 <= hour < 18:
        return '12'
    else:
        return '18'


def create_signin_board():
    """创建新时段签到留言板"""
    token = get_token()
    if not token:
        print("[FAIL] 无法获取token")
        return False
    
    today = datetime.now().strftime('%Y-%m-%d')
    period_start = get_time_period()
    doc_name = f'签到留言板 - {today}-{period_start}'
    
    # 创建文档
    print(f"[创建] {doc_name}")
    url = 'https://open.feishu.cn/open-apis/docx/v1/documents'
    data = json.dumps({
        'folder_token': SIGNIN_FOLDER_ID,
        'title': doc_name
    }).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    })
    
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        if result.get('code') != 0:
            print(f"[FAIL] 创建失败: {result}")
            return False
        
        doc_id = result.get('data', {}).get('document', {}).get('document_id')
        print(f"[OK] 文档ID: {doc_id}")
    
    # 写入初始内容
    url = f'https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children'
    data = json.dumps({
        'children': [
            {'block_type': 2, 'text': {'elements': [{'text_run': {'content': f'📋 三小龙虾签到留言板 - {today} {period_start}时段\n\n'}}]}},
            {'block_type': 2, 'text': {'elements': [{'text_run': {'content': '签到：\n'}}]}},
            {'block_type': 2, 'text': {'elements': [{'text_run': {'content': '任务分配：\n'}}]}},
            {'block_type': 2, 'text': {'elements': [{'text_run': {'content': '任务示例：T1: 任务内容 → 🐂阿呆/🦜小结巴\n'}}]}},
            {'block_type': 2, 'text': {'elements': [{'text_run': {'content': '\n交付记录：\n'}}]}}
        ]
    }).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    })
    
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        if result.get('code') == 0:
            print(f"[OK] 初始内容已写入")
            return True
        else:
            print(f"[FAIL] 写入失败: {result}")
            return False


if __name__ == '__main__':
    print(f"{'='*50}")
    print(f"[爱马仕] 创建新时段签到留言板")
    print(f"{'='*50}")
    create_signin_board()
