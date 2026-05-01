#!/usr/bin/env python3
"""
项目进展摘要记录器
每30分钟汇总群消息，写入项目进展记录
"""

import os
import json
import requests
from datetime import datetime

# ============ 配置 ============
WHO_AM_I = os.environ.get('WHO_AM_I', 'adai')

FEISHU_APP_ID = os.environ.get('FEISHU_APP_ID')
FEISHU_APP_SECRET = os.environ.get('FEISHU_APP_SECRET')

PROJECT_FOLDER_TOKEN = 'P9Q1fSCyrlS0lqd8Y9Tcfbncnl9'
CHAT_ID = os.environ.get('FEISHU_CHAT_ID', 'oc_6e680216125c663a3359e07cb6831fe7')  # 默认助力群

# 已处理消息记录
PROCESSED_LOG = os.path.expanduser(f'~/.hermes/logs/processed_messages.json')

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


def get_group_messages(token, limit=50):
    """获取群消息"""
    url = f'https://open.feishu.cn/open-apis/im/v1/messages?page_size={limit}&container_id_type=chat&container_id={CHAT_ID}'
    headers = {'Authorization': f'Bearer {token}'}
    resp = requests.get(url, headers=headers, timeout=30)
    result = resp.json()
    
    if result.get('code') != 0:
        return []
    
    messages = []
    items = result.get('data', {}).get('items', [])
    
    for msg in items:
        create_time = int(msg.get('create_time', 0)) / 1000
        msg_id = msg.get('message_id', '')
        sender_id = msg.get('sender', {}).get('id', '')
        msg_type = msg.get('msg_type', '')
        body = msg.get('body', {}).get('content', '')
        
        # 解析消息内容
        try:
            content_obj = json.loads(body)
            text = content_obj.get('text', body)
        except:
            text = body
        
        messages.append({
            'msg_id': msg_id,
            'time': create_time,
            'sender': sender_id,
            'type': msg_type,
            'text': text[:200]  # 截断
        })
    
    return messages


def find_latest_progress_doc(token):
    """找最新的项目进展记录文档"""
    url = f'https://open.feishu.cn/open-apis/drive/v1/files?folder_token={PROJECT_FOLDER_TOKEN}&page_size=50'
    headers = {'Authorization': f'Bearer {token}'}
    resp = requests.get(url, headers=headers, timeout=30)
    files = resp.json().get('data', {}).get('files', [])
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    for f in files:
        name = f.get('name', '')
        if '项目进展记录' in name and today in name:
            return f.get('token'), name
    
    # 没找到今天的，找最新的
    progress_docs = []
    for f in files:
        name = f.get('name', '')
        if '项目进展记录' in name:
            progress_docs.append({
                'token': f.get('token'),
                'name': name,
                'modified_time': int(f.get('modified_time', 0))
            })
    
    if progress_docs:
        progress_docs.sort(key=lambda x: x['modified_time'], reverse=True)
        return progress_docs[0]['token'], progress_docs[0]['name']
    
    return None, None


def append_to_doc(token, doc_id, content):
    """追加内容到文档"""
    url = f'https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json; charset=utf-8'
    }
    resp = requests.post(url, headers=headers, json={
        'children': [
            {
                'block_type': 2,
                'text': {
                    'elements': [{'text_run': {'content': content}}]
                }
            }
        ]
    }, timeout=30)
    return resp.status_code == 200


def load_processed_messages():
    """加载已处理的消息ID"""
    if os.path.exists(PROCESSED_LOG):
        try:
            with open(PROCESSED_LOG, 'r') as f:
                return set(json.load(f))
        except:
            return set()
    return set()


def save_processed_messages(msg_ids):
    """保存已处理的消息ID"""
    os.makedirs(os.path.dirname(PROCESSED_LOG), exist_ok=True)
    with open(PROCESSED_LOG, 'w') as f:
        json.dump(list(msg_ids), f)


def generate_summary(messages):
    """生成项目进展摘要（提取关键主题）"""
    if not messages:
        return None
    
    # 提取有意义的消息内容
    key_topics = []
    for m in messages:
        text = m['text'].strip()
        # 过滤空消息、太短消息、机器人富文本、简单问候
        if len(text) < 10 or text.startswith('{'):
            continue
        if text.lower() in ['hi', 'ok', '好', '嗯', '收到', '好的']:
            continue
        
        # 提取关键词（任务、问题、完成等）
        keywords = ['任务', '完成', '问题', '配置', '测试', '安装', '修复', '改', '写', 'push', 'git', '脚本']
        for kw in keywords:
            if kw in text.lower():
                key_topics.append(text[:50])
                break
    
    if not key_topics:
        return None
    
    # 生成摘要
    now = datetime.now().strftime('%H:%M')
    emoji = {'adai': '🐂', 'xiaojieba': '🦞', 'aimashu': '🦬'}.get(WHO_AM_I, '')
    my_name = NAME_MAP.get(WHO_AM_I, WHO_AM_I)
    
    # 只取前3个关键主题
    topics = key_topics[:3]
    summary = f"{emoji} {my_name} | {now} | " + " | ".join(topics)
    
    return summary


def main():
    """主函数"""
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        print('[错误] 未配置飞书凭证')
        return
    
    token = get_feishu_token()
    if not token:
        print('[错误] 获取token失败')
        return
    
    # 获取群消息
    messages = get_group_messages(token, limit=50)
    if not messages:
        print('[OK] 无新消息')
        return
    
    # 过滤已处理的
    processed = load_processed_messages()
    new_messages = [m for m in messages if m['msg_id'] not in processed]
    
    if not new_messages:
        print('[OK] 无新消息需要处理')
        return
    
    # 处理所有未处理的新消息（不限时间）
    recent_messages = new_messages
    
    if not recent_messages:
        print(f'[OK] 无新消息需要处理')
        return
    
    # 生成摘要
    summary = generate_summary(recent_messages)
    if not summary:
        print('[OK] 无法生成摘要')
        return
    
    # 找项目进展记录文档
    doc_id, doc_name = find_latest_progress_doc(token)
    if not doc_id:
        print('[错误] 找不到项目进展记录文档')
        return
    
    print(f'文档: {doc_name}')
    
    # 写入摘要
    if append_to_doc(token, doc_id, summary):
        print(f'[OK] 已写入: {summary}')
        # 标记为已处理
        processed_msg_ids = set(m['msg_id'] for m in recent_messages)
        save_processed_messages(processed | processed_msg_ids)
    else:
        print('[错误] 写入失败')


if __name__ == '__main__':
    main()
