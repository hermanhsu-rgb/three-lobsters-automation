#!/usr/bin/env python3
"""
写入留言板文档
"""
import urllib.request
import json
import os
from dotenv import load_dotenv

load_dotenv('/root/.hermes/.env')

APP_ID = os.environ.get('FEISHU_APP_ID')
APP_SECRET = os.environ.get('FEISHU_APP_SECRET')
def get_token():
    url = 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal'
    data = json.dumps({'app_id': APP_ID, 'app_secret': APP_SECRET}).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        return result.get('tenant_access_token')


def write_to_doc(doc_token, content):
    """向文档追加内容"""
    token = get_token()
    if not token:
        print("[FAIL] 无法获取token")
        return False
    
    # 获取文档blocks
    url = f'https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{doc_token}/children'
    req = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    })
    
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        blocks = result.get('data', {}).get('items', [])
        if blocks:
            last_block_id = blocks[-1].get('block_id')
        else:
            last_block_id = doc_token
    
    # 追加内容
    url = f'https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{last_block_id}/children'
    data = json.dumps({
        'children': [
            {'block_type': 2, 'text': {'elements': [{'text_run': {'content': content}}]}}
        ],
        'index': 0
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    })
    
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        if result.get('code') == 0:
            print(f"[OK] 写入成功: {content}")
            return True
        else:
            print(f"[FAIL] 写入失败: {result}")
            return False


if __name__ == '__main__':
    import sys
    if len(sys.argv) >= 3:
        doc_token = sys.argv[1]
        content = sys.argv[2]
        write_to_doc(doc_token, content)
    else:
        print("用法: python write_to_board.py <doc_token> <content>")