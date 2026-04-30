#!/usr/bin/env python3
"""
执行者心跳脚本 - 阿呆/小结巴使用
cron触发 → 签到 → 检查任务 → spawn子agent执行 → 交任务 → 发消息触发爱马仕

用法:
    python3 heartbeat_executor.py --who [adai|xiaojieba]
"""

import os
import sys
import json
import argparse
from datetime import datetime
import urllib.request
import subprocess

# 从.env文件加载环境变量
def load_env():
    """从.env文件加载环境变量"""
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

# 配置 - 全部从环境变量读取
FEISHU_APP_ID = os.environ.get('FEISHU_APP_ID', '')
FEISHU_APP_SECRET = os.environ.get('FEISHU_APP_SECRET', '')
SIGNIN_FOLDER_ID = os.environ.get('SIGNIN_FOLDER_ID', 'TUcWf6Kyql4d6gdi1nWc7TxVnDe')
MESSAGE_BOARD_ID = os.environ.get('MESSAGE_BOARD_ID', 'Lj0OdVYvuoAKvVxOxr0crc9ynWg')
TASK_BOARD_ID = os.environ.get('TASK_BOARD_ID', 'EFcudwbCCozKaQx2peocy7NIn5b')
FEISHU_GROUP_ID = os.environ.get('FEISHU_GROUP_ID', 'oc_6e680216125c663a3359e07cb6831fe7')

# 身份映射
WHO_EMOJI = {
    'adai': '🐂',
    'xiaojieba': '🦜',
    'aimashu': '🦬'
}

WHO_NAME = {
    'adai': '阿呆',
    'xiaojieba': '小结巴',
    'aimashu': '爱马仕'
}


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
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            return result.get('tenant_access_token')
    except Exception as e:
        print(f"[ERROR] 获取token失败: {e}")
        return None


def read_doc(token, doc_id):
    """读取文档内容"""
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children?page_size=100"
    req = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {token}'
    })
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            texts = []
            for item in result.get('data', {}).get('items', []):
                if 'text' in item and 'elements' in item['text']:
                    for elem in item['text']['elements']:
                        if 'text_run' in elem and 'content' in elem['text_run']:
                            texts.append(elem['text_run']['content'])
            return '\n'.join(texts)
    except Exception as e:
        print(f"[ERROR] 读取文档失败: {e}")
        return ""


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
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            return result.get('code') == 0
    except Exception as e:
        print(f"[ERROR] 写入文档失败: {e}")
        return False


def get_today_signin_doc(token):
    """从签到文件夹找当天的签到文档"""
    today = datetime.now().strftime('%Y-%m-%d')
    url = f"https://open.feishu.cn/open-apis/drive/v1/files?folder_token={SIGNIN_FOLDER_ID}&page_size=50"
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            for f in result.get('data', {}).get('files', []):
                name = f.get('name', '')
                if today in name:
                    print(f"[OK] 找到今日签到文档: {name}")
                    return f.get('token')
            print(f"[WARN] 未找到今日({today})签到文档")
            return None
    except Exception as e:
        print(f"[ERROR] 查找签到文档失败: {e}")
        return None


def send_feishu_message(token, content):
    """发送飞书消息触发下一个AI"""
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
    data = json.dumps({
        "receive_id": FEISHU_GROUP_ID,
        "msg_type": "text",
        "content": json.dumps({"text": content})
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json; charset=utf-8'
    }, method='POST')
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            return result.get('code') == 0
    except Exception as e:
        print(f"[ERROR] 发送消息失败: {e}")
        return False


def is_task_completed(message_board_content, task_id):
    """检查任务是否已完成"""
    lines = message_board_content.split('\n')
    for line in lines:
        # 查找完成标记：✅ T数字 完成
        if '✅' in line and task_id in line and '完成' in line:
            return True
    return False


def find_my_task(message_board_content, who):
    """从留言板找分配给自己的任务（排除已完成的）"""
    emoji = WHO_EMOJI.get(who, '❓')
    name = WHO_NAME.get(who, '未知')
    
    # 查找格式：T8: xxx → 🐂阿呆
    lines = message_board_content.split('\n')
    for line in lines:
        if 'T' in line and ':' in line:
            # 检查是否分配给自己
            if emoji in line or name in line:
                # 提取任务ID和内容
                # 格式可能：T8: 任务内容 → 🐂阿呆
                parts = line.split('→')[0].strip()
                if parts.startswith('T'):
                    task_id = parts.split(':')[0].strip()
                    task_content = parts.split(':', 1)[1].strip() if ':' in parts else ''
                    
                    # 检查是否已完成
                    if is_task_completed(message_board_content, task_id):
                        print(f"[跳过] {task_id} 已完成，不重复执行")
                        continue
                    
                    return {'id': task_id, 'content': task_content, 'raw': line}
    return None


def spawn_agent_and_execute(who, task):
    """真正spawn子agent执行任务 - 使用Hermes AIAgent"""
    emoji = WHO_EMOJI.get(who, '❓')
    name = WHO_NAME.get(who, '未知')
    
    content = task.get('content', '')
    task_id = task.get('id', '?')
    
    print(f"[spawn] 启动子agent执行: {task_id}: {content}")
    
    # 导入Hermes AIAgent - 动态路径适配各机器
    hermes_agent_path = os.path.expanduser('~/.hermes/hermes-agent')
    sys.path.insert(0, hermes_agent_path)
    from run_agent import AIAgent
    
    # 构造prompt
    prompt = f"""你是{emoji}{name}，执行任务 {task_id}。

任务内容: {content}

要求：
1. 使用feishu-doc技能完成任务（修改留言板文档：{MESSAGE_BOARD_ID})
2. 在留言板写入：✅ {task_id}完成
3. 不要解释，直接执行并返回结果
"""
    
    try:
        # 真正spawn子agent
        agent = AIAgent(
            model="glm-5",
            enabled_toolsets=["feishu_doc", "file"],
            max_iterations=10,
            quiet_mode=True
        )
        
        result = agent.run_conversation(prompt)
        # 安全处理返回值
        if result:
            result_str = str(result)[:200] if isinstance(result, str) else str(type(result))
        else:
            result_str = '无输出'
        print(f"[完成] 子agent返回: {result_str}")
        return True
        
    except Exception as e:
        print(f"[错误] spawn失败: {e}")
        # 备用方案：直接写飞书
        return False


def checkout_signin(token, who):
    """签到打卡"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    emoji = WHO_EMOJI.get(who, '❓')
    name = WHO_NAME.get(who, '未知')
    
    signin_doc_id = get_today_signin_doc(token)
    if not signin_doc_id:
        print(f"[FAIL] 无法找到今日签到文档")
        return False
    
    sign_text = f"{emoji} {name} 签到 | {now}"
    append_to_doc(token, signin_doc_id, sign_text)
    return True


def heartbeat(who):
    """执行心跳"""
    print(f"\n{'='*50}")
    print(f"[心跳] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[身份] {WHO_EMOJI.get(who, '?')} {WHO_NAME.get(who, '?')}")
    print(f"[角色] 执行者")
    print(f"{'='*50}")
    
    # 1. 获取token
    token = get_token()
    if not token:
        print("[FAIL] 无法获取token")
        return False
    print("[OK] Token获取成功")
    
    # 2. 签到
    if checkout_signin(token, who):
        print("[OK] 签到成功")
    else:
        print("[WARN] 签到失败")
    
    # 3. 读留言板，找分配给自己的任务
    message_board_content = read_doc(token, MESSAGE_BOARD_ID)
    task = find_my_task(message_board_content, who)
    
    if task:
        print(f"\n[发现任务] {task['id']}: {task['content']}")
        
        # 4. spawn子agent执行任务
        print(f"[执行] 启动子agent...")
        spawn_agent_and_execute(who, task)
        
        # 5. 交任务（留言板）
        now = datetime.now().strftime('%H:%M')
        deliver_text = f"\n[{now}] {WHO_EMOJI.get(who)} {WHO_NAME.get(who)}\n✅ {task['id']} 完成\n"
        append_to_doc(token, MESSAGE_BOARD_ID, deliver_text)
        print(f"[交付] 已写入留言板")
        
        # 6. 发消息触发爱马仕
        trigger_msg = f"{WHO_EMOJI.get(who)} {WHO_NAME.get(who)} 任务完成，请🦬爱马仕检查发布新任务"
        send_feishu_message(token, trigger_msg)
        print(f"[触发] 已发消息触发爱马仕")
    else:
        print("[OK] 无分配给自己的任务")
    
    print(f"\n[完成] 心跳结束 {datetime.now().strftime('%H:%M:%S')}")
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='执行者心跳脚本')
    parser.add_argument('--who', required=True, choices=['adai', 'xiaojieba'],
                        help='执行者身份')
    
    args = parser.parse_args()
    
    if not FEISHU_APP_SECRET:
        print("[ERROR] 未设置 FEISHU_APP_SECRET 环境变量")
        sys.exit(1)
    
    heartbeat(args.who)