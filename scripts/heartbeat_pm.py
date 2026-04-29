#!/usr/bin/env python3
"""
PM心跳脚本 - 爱马仕使用
cron触发 → 签到 → 检查交任务 → spawn子agent思考+发布新任务

用法:
    python3 heartbeat_pm.py --who aimashu
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
PROJECT_DOC_ID = os.environ.get('PROJECT_DOC_ID', 'UYDtd65mto9ap0xRtquczN8tnVe')  # 任务分配表
FEISHU_GROUP_ID = os.environ.get('FEISHU_GROUP_ID', 'oc_6e680216125c663a3359e07cb6831fe7')

# 身份映射
WHO_EMOJI = {'adai': '🐂', 'xiaojieba': '🦜', 'aimashu': '🦬'}
WHO_NAME = {'adai': '阿呆', 'xiaojieba': '小结巴', 'aimashu': '爱马仕'}


def get_token():
    """获取飞书token"""
    url = 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal'
    data = json.dumps({
        'app_id': FEISHU_APP_ID,
        'app_secret': FEISHU_APP_SECRET
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, headers={
        'Content-Type': 'application/json; charset=utf-8'
    })
    
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        if result.get('code') == 0:
            return result.get('tenant_access_token')
        else:
            print(f"[ERROR] 获取token失败: {result}")
            return None


def read_doc(token, doc_id):
    """读取文档内容"""
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children?page_size=100"
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
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
        with urllib.request.urlopen(req, timeout=10) as resp:
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
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            for f in result.get('data', {}).get('files', []):
                name = f.get('name', '')
                if today in name:
                    return f.get('token')
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
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            return result.get('code') == 0
    except Exception as e:
        print(f"[ERROR] 发送消息失败: {e}")
        return False


def check_task_completion(message_board_content):
    """检查有没有人交任务"""
    completions = []
    lines = message_board_content.split('\n')
    
    for i, line in enumerate(lines):
        # 查找完成标记：✅ T数字 完成
        if '✅' in line and '完成' in line:
            # 提取任务ID和完成者
            for emoji in ['🐂', '🦜', '🦬']:
                if emoji in line:
                    parts = line.split('✅')
                    if len(parts) > 1:
                        task_info = parts[1].strip()
                        completions.append({
                            'who': emoji,
                            'task': task_info,
                            'line': line
                        })
                    break
    
    return completions


def spawn_pm_thinking_agent(token, completions):
    """真正spawn PM思考子agent"""
    # 读取项目整体进度
    project_content = read_doc(token, PROJECT_DOC_ID)
    
    # 导入Hermes AIAgent
    sys.path.insert(0, '/root/.hermes/hermes-agent')
    from run_agent import AIAgent
    
    # 构造思考prompt
    prompt = f"""你是🦬爱马仕，PM角色。

最近完成的任务：{json.dumps(completions, ensure_ascii=False)}

项目任务分配表：
{project_content}

请思考并发布下一个任务。要求：
1. 确认完成情况
2. 决定下一步做什么
3. 使用feishu_doc技能在留言板({MESSAGE_BOARD_ID})发布新任务

发布格式：
[时间] 🦬爱马仕 发布任务
T数字: 任务内容 → 🐂阿呆/🦜小结巴

直接执行，返回发布结果。
"""
    
    print(f"[spawn] 启动PM子agent思考...")
    
    try:
        agent = AIAgent(
            model="anthropic/claude-sonnet-4",
            enabled_toolsets=["feishu_doc", "file"],
            max_iterations=10,
            quiet_mode=True
        )
        
        result = agent.run_conversation(prompt)
        print(f"[完成] PM子agent返回: {result[:200] if result else '无输出'}")
        return True
        
    except Exception as e:
        print(f"[错误] PM spawn失败: {e}")
        return False


def checkout_signin(token, who):
    """签到打卡"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    emoji = WHO_EMOJI.get(who, '❓')
    name = WHO_NAME.get(who, '未知')
    
    signin_doc_id = get_today_signin_doc(token)
    if not signin_doc_id:
        return False
    
    sign_text = f"{emoji} {name} 签到 | {now}"
    append_to_doc(token, signin_doc_id, sign_text)
    return True


def heartbeat_pm(who):
    """执行PM心跳"""
    print(f"\n{'='*50}")
    print(f"[心跳] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[身份] {WHO_EMOJI.get(who, '?')} {WHO_NAME.get(who, '?')}")
    print(f"[角色] PM（项目管理）")
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
    
    # 3. 读留言板，检查有没有人交任务
    message_board_content = read_doc(token, MESSAGE_BOARD_ID)
    completions = check_task_completion(message_board_content)
    
    if completions:
        print(f"\n[发现交付] {len(completions)} 个任务完成")
        for c in completions:
            print(f"  - {c['who']} {c['task']}")
        
        # 4. spawn PM思考子agent
        print(f"\n[思考] 启动PM子agent...")
        thinking_file = spawn_pm_thinking_agent(token, completions)
        
        # 5. 读取思考结果（如果子agent已完成）
        result_file = os.path.expanduser("~/.hermes/shared/pm_result.json")
        if os.path.exists(result_file):
            with open(result_file) as f:
                result = json.load(f)
            
            # 6. 发布新任务到留言板
            next_task = result.get('next_task')
            if next_task:
                now = datetime.now().strftime('%H:%M')
                task_text = f"\n[{now}] 🦬爱马仕 发布任务\n{next_task['id']}: {next_task['content']} → {next_task['assignee']}\n"
                append_to_doc(token, MESSAGE_BOARD_ID, task_text)
                print(f"[发布] {next_task['id']} 已分配给 {next_task['assignee']}")
                
                # 7. 发消息触发执行者
                trigger_msg = f"🦬爱马仕 发布新任务：{next_task['id']}，请 {next_task['assignee']} 领取执行"
                send_feishu_message(token, trigger_msg)
                print(f"[触发] 已发消息触发执行者")
            
            # 清理结果文件
            os.remove(result_file)
    else:
        print("[OK] 无新完成的任务")
    
    print(f"\n[完成] PM心跳结束 {datetime.now().strftime('%H:%M:%S')}")
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PM心跳脚本')
    parser.add_argument('--who', required=True, choices=['aimashu'],
                        help='PM身份')
    
    args = parser.parse_args()
    
    if not FEISHU_APP_SECRET:
        print("[ERROR] 未设置 FEISHU_APP_SECRET 环境变量")
        sys.exit(1)
    
    heartbeat_pm(args.who)
