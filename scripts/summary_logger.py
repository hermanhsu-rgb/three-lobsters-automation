#!/usr/bin/env python3
"""
执行摘要记录器 - 三小龙虾通用
版本: V1.0 (2026-05-01)
每10分钟记录自己的执行摘要到当天的记事文档

使用方式:
1. 在其他脚本中导入: from summary_logger import record_action
2. 执行动作时调用: record_action('签到', '成功')
3. cron每10分钟运行本脚本，自动同步到飞书
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
PROJECT_FOLDER_TOKEN='P9Q1fSCyrlS0lqd8Y9Tcfbncnl9'

# 本地执行记录
SUMMARY_LOG = os.path.expanduser(f'~/.hermes/logs/summary_{WHO_AM_I}.json')

# 项目进展记录文档（固定版本）
PROJECT_PROGRESS_DOC_FIXED = 'RbRNdPRd7oWRfYxop2wcrdXMnOV'

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


def find_latest_progress_doc(token):
    """找最新的项目进展记录文档（爱马仕每天创建新版）"""
    url = f'https://open.feishu.cn/open-apis/drive/v1/files?folder_token={PROJECT_FOLDER_TOKEN}&page_size=50'
    headers = {'Authorization': f'Bearer {token}'}
    resp = requests.get(url, headers=headers, timeout=30)
    files = resp.json().get('data', {}).get('files', [])
    
    # 找所有项目进展记录文档
    progress_docs = []
    for f in files:
        name = f.get('name', '')
        # 匹配：项目进展记录 或 项目进展记录 (日期)
        if '项目进展记录' in name:
            progress_docs.append({
                'token': f.get('token'),
                'name': name,
                'modified_time': int(f.get('modified_time', 0))
            })
    
    if not progress_docs:
        return None, None
    
    # 按修改时间排序，返回最新的
    progress_docs.sort(key=lambda x: x['modified_time'], reverse=True)
    latest = progress_docs[0]
    print(f"[OK] 找到最新项目进展记录: {latest['name']}")
    return latest['token'], latest['name']


def find_today_doc(token, date_str):
    """查找当天的记事文档"""
    url = f'https://open.feishu.cn/open-apis/drive/v1/files?folder_token={PROJECT_FOLDER_TOKEN}&page_size=50'
    headers = {'Authorization': f'Bearer {token}'}
    resp = requests.get(url, headers=headers, timeout=30)
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
    # 先获取文档blocks
    blocks_url = f'https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks'
    headers = {'Authorization': f'Bearer {token}'}
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
        with open(SUMMARY_LOG, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'last_time': '', 'records': []}


def save_local_summary(data):
    """保存本地执行摘要"""
    os.makedirs(os.path.dirname(SUMMARY_LOG), exist_ok=True)
    with open(SUMMARY_LOG, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def record_action(action, detail='', who=None):
    """
    记录一个执行动作（供其他脚本调用）
    
    Args:
        action: 动作名称（如"签到"、"执行任务"）
        detail: 详细信息
        who: 指定身份（默认用环境变量WHO_AM_I）
    
    Returns:
        dict: 记录的内容
    """
    # 如果指定了who，临时切换
    global WHO_AM_I, SUMMARY_LOG
    original_who = WHO_AM_I
    if who:
        WHO_AM_I = who
        SUMMARY_LOG = os.path.expanduser(f'~/.hermes/logs/summary_{who}.json')
    
    data = load_local_summary()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    record = {
        'time': now,
        'action': action,
        'detail': detail,
        'synced': False  # 标记未同步
    }
    data['records'].append(record)
    data['last_time'] = now
    
    # 只保留最近100条（避免太大）
    if len(data['records']) > 100:
        data['records'] = data['records'][-100:]
    
    save_local_summary(data)
    
    # 恢复原来的身份
    if who:
        WHO_AM_I = original_who
        SUMMARY_LOG = os.path.expanduser(f'~/.hermes/logs/summary_{original_who}.json')
    
    return record

# ============ 主循环 ============
def main():
    """主函数：将本地未同步的记录同步到飞书项目进展记录"""
    token = get_feishu_token()
    if not token:
        print('[错误] 获取token失败')
        return
    
    # 找最新的项目进展记录文档（爱马仕每天创建新版）
    doc_id, doc_name = find_latest_progress_doc(token)
    if not doc_id:
        print('[错误] 找不到项目进展记录文档')
        return
    
    # 读取本地记录
    data = load_local_summary()
    records = data.get('records', [])
    
    # 只同步未同步的记录
    unsynced = [r for r in records if not r.get('synced', False)]
    
    if not unsynced:
        # 没有新记录，写一个心跳
        now = datetime.now().strftime('%H:%M')
        my_name = NAME_MAP.get(WHO_AM_I, WHO_AM_I)
        content = f'\n[{now}] {my_name} 心跳检查 ✓'
        append_to_doc(token, doc_id, content)
        print(f'[OK] 无新记录，心跳已写入')
    else:
        # 写入未同步的记录
        my_name = NAME_MAP.get(WHO_AM_I, WHO_AM_I)
        count = 0
        
        for r in unsynced:
            time_str = r.get('time', '').split(' ')[1] if ' ' in r.get('time', '') else r.get('time', '')
            content = f'\n[{time_str}] {my_name}: {r.get("action", "")}'
            if r.get('detail'):
                content += f' - {r.get("detail")}'
            
            if append_to_doc(token, doc_id, content):
                # 标记为已同步
                r['synced'] = True
                count += 1
        
        # 保存更新后的数据（已同步的记录保留在本地作为备份）
        save_local_summary(data)
        print(f'[OK] 已同步 {count}/{len(unsynced)} 条记录')

if __name__ == '__main__':
    main()