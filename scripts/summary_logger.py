#!/usr/bin/env python3
"""
执行摘要记录器 - 三小龙虾通用
每10分钟记录自己的执行摘要到当天的记事文档
"""

import os
import json
import requests
from datetime import datetime, timedelta

# ============ 配置 ============
WHO_AM_I = os.environ.get('WHO_AM_I', 'adai')  # adai / xiaojieba / aimashu

# 飞书配置
FEISHU_APP_ID = os.environ.get('FEISHU_APP_ID')
FEISHU_APP_SECRET = os.environ.get('FEISHU_APP_SECRET')

# 文件夹Token（三小龙虾自动化项目）
PROJECT_FOLDER_TOKEN = 'P9Q1fSCyrlS0lqd8Y9Tcfbncnl9'

# 本地执行记录
SUMMARY_LOG = os.path.expanduser(f'~/.hermes/logs/summary_{WHO_AM_I}.json')

# 名字映射
NAME_MAP = {
    'adai': '阿呆',
    'xiaojieba': '小结巴',
    'aimashu': '爱马仕'
}

# ============ 飞书API ============
def get_feishu_token():
    """获取飞书access_token"""
    url = 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal'
    resp = requests.post(url, json={
        'app_id': FEISHU_APP_ID,
        'app_secret': FEISHU_APP_SECRET
    }, timeout=30)
    return resp.json().get('tenant_access_token')

def find_today_doc(token, date_str):
    """查找当天的记事文档"""
    url = f'https://open.feishu.cn/open-apis/drive/v1/files'
    headers = {'Authorization': f'Bearer {token}'}
    params = {
        'folder_id': PROJECT_FOLDER_TOKEN,
        'page_size': 50
    }
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    files = resp.json().get('data', {}).get('files', [])
    
    # 匹配当天文档：执行摘要-YYYY-MM-DD
    doc_name = f'执行摘要-{date_str}'
    for f in files:
        if doc_name in f.get('name', ''):
            return f.get('token'), f.get('name')
    return None, None

def create_today_doc(token, date_str):
    """创建当天的记事文档"""
    url = 'https://open.feishu.cn/open-apis/docx/v1/documents'
    headers = {'Authorization': f'Bearer {token}'}
    doc_name = f'执行摘要-{date_str}'
    resp = requests.post(url, headers=headers, json={
        'document': {
            'title': doc_name,
            'folder_id': PROJECT_FOLDER_TOKEN
        }
    }, timeout=30)
    result = resp.json()
    return result.get('data', {}).get('document', {}).get('document_id'), doc_name

def append_to_doc(token, doc_id, content):
    """追加内容到文档末尾"""
    url = f'https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/batch_update'
    headers = {'Authorization': f'Bearer {token}'}
    
    # 先获取文档blocks
    blocks_url = f'https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks'
    resp = requests.get(blocks_url, headers=headers, timeout=30)
    blocks = resp.json().get('data', {}).get('items', [])
    
    if not blocks:
        return False
    
    # 找到最后一个block
    last_block_id = blocks[-1].get('block_id')
    
    # 追加内容
    update_url = f'https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{last_block_id}/children/append'
    resp = requests.post(update_url, headers=headers, json={
        'children': [
            {
                'block_type': 3,  # Text block
                'text': {
                    'elements': [{'text_run': {'content': content}}]
                }
            }
        ],
        'index': 0
    }, timeout=30)
    return resp.status_code == 200

# ============ 执行记录 ============
def load_local_summary():
    """加载本地执行摘要"""
    if os.path.exists(SUMMARY_LOG):
        with open(SUMMARY_LOG, 'r') as f:
            return json.load(f)
    return {'last_time': '', 'records': []}

def save_local_summary(data):
    """保存本地执行摘要"""
    os.makedirs(os.path.dirname(SUMMARY_LOG), exist_ok=True)
    with open(SUMMARY_LOG, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def record_action(action, detail=''):
    """记录一个执行动作"""
    data = load_local_summary()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    record = {
        'time': now,
        'action': action,
        'detail': detail
    }
    data['records'].append(record)
    data['last_time'] = now
    
    # 只保留最近20条
    if len(data['records']) > 20:
        data['records'] = data['records'][-20:]
    
    save_local_summary(data)
    return record

# ============ 主循环 ============
def main():
    """主函数：将本地记录的摘要同步到飞书文档"""
    token = get_feishu_token()
    if not token:
        print('[错误] 获取token失败')
        return
    
    date_str = datetime.now().strftime('%Y-%m-%d')
    
    # 查找或创建当天文档
    doc_id, doc_name = find_today_doc(token, date_str)
    if not doc_id:
        doc_id, doc_name = create_today_doc(token, date_str)
        if doc_id:
            print(f'[OK] 创建新文档: {doc_name}')
        else:
            print('[错误] 创建文档失败')
            return
    
    # 读取本地记录
    data = load_local_summary()
    records = data.get('records', [])
    
    if not records:
        # 没有记录，写一个心跳
        now = datetime.now().strftime('%H:%M')
        my_name = NAME_MAP.get(WHO_AM_I, WHO_AM_I)
        content = f'\n[{now}] {my_name} 心跳检查 ✓'
        append_to_doc(token, doc_id, content)
        print(f'[OK] 心跳记录已写入')
    else:
        # 写入最近的记录
        my_name = NAME_MAP.get(WHO_AM_I, WHO_AM_I)
        now = datetime.now().strftime('%H:%M')
        
        for r in records[-3:]:  # 只写最近3条
            time_str = r.get('time', '').split(' ')[1] if ' ' in r.get('time', '') else r.get('time', '')
            content = f'\n[{time_str}] {my_name}: {r.get("action", "")}'
            if r.get('detail'):
                content += f' - {r.get("detail")}'
            append_to_doc(token, doc_id, content)
        
        # 清空本地记录
        data['records'] = []
        save_local_summary(data)
        print(f'[OK] 已写入 {len(records[-3:])} 条记录')

if __name__ == '__main__':
    main()