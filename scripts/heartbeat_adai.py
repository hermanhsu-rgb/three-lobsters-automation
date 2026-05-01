#!/usr/bin/env python3
"""
🐂 阿呆 专用执行者心跳脚本
cron触发 → 签到 → 检查任务 → spawn子agent执行 → 交任务 → 发消息触发爱马仕

用法:
    python3 heartbeat_adai.py
"""

import os
import sys
import json
from datetime import datetime
import urllib.request
import subprocess

# 导入执行记录模块
try:
    from summary_logger import record_action
except ImportError:
    # 如果导入失败，定义空函数
    def record_action(action, detail='', who=None):
        pass

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
PROJECT_PROGRESS_DOC = os.environ.get('PROJECT_PROGRESS_DOC', 'RbRNdPRd7oWRfYxop2wcrdXMnOV')  # 项目进展记录

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
    """读取文档最近内容（读到末尾，取最后30行）"""
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children?page_size=100"
    req = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {token}'
    })
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            
            # 读取所有页，直到末尾
            all_items = result.get('data', {}).get('items', [])
            page_token = result.get('data', {}).get('page_token')
            
            # 继续读取到末尾（最多20页，避免太慢）
            page_count = 1
            while page_token and page_count < 20:
                url2 = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children?page_size=100&page_token={page_token}"
                req2 = urllib.request.Request(url2, headers={'Authorization': f'Bearer {token}'})
                with urllib.request.urlopen(req2, timeout=30) as resp2:
                    result2 = json.loads(resp2.read().decode('utf-8'))
                    items2 = result2.get('data', {}).get('items', [])
                    all_items.extend(items2)
                    page_count += 1
                    if not result2.get('data', {}).get('has_more'):
                        break
                    page_token = result2.get('data', {}).get('page_token')
            
            # 只取最后30个block（任务和最近签到都在末尾）
            items = all_items[-30:]
            
            texts = []
            for item in items:
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


def get_time_period():
    """获取当前时间段名称、范围和开始时间"""
    hour = datetime.now().hour
    if 0 <= hour < 6:
        return "凌晨", "00-06", "00"
    elif 6 <= hour < 12:
        return "上午", "06-12", "06"
    elif 12 <= hour < 18:
        return "下午", "12-18", "12"
    else:
        return "晚上", "18-24", "18"


def get_current_signin_doc(token):
    """从签到文件夹找当前时间段的签到文档（每6小时一个）"""
    today = datetime.now().strftime('%Y-%m-%d')
    period_name, period_range, _ = get_time_period()
    
    url = f"https://open.feishu.cn/open-apis/drive/v1/files?folder_token={SIGNIN_FOLDER_ID}&page_size=50"
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            for f in result.get('data', {}).get('files', []):
                name = f.get('name', '')
                # 匹配：日期 + 时间段（如"凌晨"或"00-06"）
                # 宽松匹配：包含今天日期 + (时间段 OR 无时间段后缀)
                if today in name and (period_name in name or period_range in name or name.endswith(today) or name.endswith(today+')')):
                    # 排除留言板（只找签到板）
                    if '留言板' not in name or '签到' in name:
                        print(f"[OK] 找到当前时段签到文档: {name}")
                        return f.get('token')
            print(f"[WARN] 未找到当前时段({today} {period_name})签到文档")
            return None
    except Exception as e:
        print(f"[ERROR] 查找签到文档失败: {e}")
        return None


def get_current_message_board(token):
    """从签到文件夹找当前时段的留言板（标准格式：YYYY-MM-DD-HH）"""
    today = datetime.now().strftime('%Y-%m-%d')
    hour = datetime.now().hour
    if hour >= 18:
        period_start = "18"
    elif hour >= 12:
        period_start = "12"
    elif hour >= 6:
        period_start = "06"
    else:
        period_start = "00"
    
    url = f"https://open.feishu.cn/open-apis/drive/v1/files?folder_token={SIGNIN_FOLDER_ID}&page_size=50"
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            for f in result.get('data', {}).get('files', []):
                name = f.get('name', '')
                # 严格匹配：签到留言板 + 日期 + 时段后缀（如-18）
                if '签到留言板' in name and today in name and f'-{period_start}' in name:
                    print(f"[OK] 找到当前时段留言板: {name}")
                    return f.get('token')
            
            print(f"[WARN] 未找到当前时段留言板")
            return None
    except Exception as e:
        print(f"[ERROR] 查找留言板失败: {e}")
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


def load_completed_tasks(who):
    """加载已完成的任务ID列表"""
    completed_file = os.path.expanduser(f'~/.hermes/logs/completed_tasks_{who}.json')
    if os.path.exists(completed_file):
        try:
            with open(completed_file) as f:
                return set(json.load(f))
        except:
            return set()
    return set()


def save_completed_tasks(who, completed_set):
    """保存已完成的任务ID列表"""
    completed_file = os.path.expanduser(f'~/.hermes/logs/completed_tasks_{who}.json')
    os.makedirs(os.path.dirname(completed_file), exist_ok=True)
    with open(completed_file, 'w') as f:
        json.dump(list(completed_set), f)


def find_my_task(message_board_content, who):
    """从留言板找分配给自己的任务（排除已完成的）"""
    import re
    name = WHO_NAME.get(who, '未知')
    emoji = WHO_EMOJI.get(who, '')
    
    # 加载已完成任务
    completed = load_completed_tasks(who)
    
    # 支持多种格式：
    # 1. T1: 任务内容 → 🐂阿呆
    # 2. DSD-001: 任务内容 → 🐂阿呆
    # 3. T1: 任务内容 @阿呆
    # 4. 多行：T1: 任务内容\n执行人：阿呆
    lines = message_board_content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        # 匹配任务ID：T数字、DSD-数字、DSD-字母数字组合
        match = re.match(r'((?:T\d+|DSD-[\w]+|TASK-[\w]+)):', line)
        if match:
            task_id = match.group(1)
            # 跳过已完成的任务
            if task_id in completed:
                i += 1
                continue
            
            # 检查当前行和接下来3行是否有自己的名字或emoji
            check_lines = [line] + lines[i+1:i+4]
            check_text = '\n'.join(check_lines)
            
            # 匹配：名字、emoji+名字、→ emoji名字
            if name in check_text or (emoji and emoji in check_text):
                # 提取任务内容（冒号后到行尾，去掉分配标记）
                pos = line.find(':')
                task_content = line[pos+1:].strip()
                # 去掉分配标记（→ xxx）
                if '→' in task_content:
                    task_content = task_content.split('→')[0].strip()
                return {'id': task_id, 'content': task_content, 'raw': check_text}
        i += 1
    return None


def spawn_agent_and_execute(who, task, message_board_id):
    """Spawn子agent真正执行任务 - 增强稳定性版本"""
    task_id = task['id']
    content = task['content']
    emoji = WHO_EMOJI.get(who, '🤖')
    name = WHO_NAME.get(who, who)
    
    # 导入Hermes AIAgent - 使用更稳定的导入方式
    hermes_agent_path = os.path.expanduser('~/.hermes/hermes-agent')
    
    # 检查路径是否存在
    if not os.path.exists(hermes_agent_path):
        print(f"[错误] Hermes Agent路径不存在: {hermes_agent_path}")
        return False
    
    # 避免重复插入路径
    if hermes_agent_path not in sys.path:
        sys.path.insert(0, hermes_agent_path)
        print(f"[导入] 添加路径到sys.path: {hermes_agent_path}")
    
    # 尝试导入AIAgent
    try:
        from run_agent import AIAgent
        print("[成功] AIAgent模块导入成功")
    except ImportError as e:
        print(f"[错误] 无法导入AIAgent: {e}")
        print(f"[提示] 检查依赖: pip list | grep openai")
        return False
    except Exception as e:
        print(f"[错误] 导入AIAgent时发生未知错误: {e}")
        return False
    
    # 构造具体执行prompt - 根据任务类型区分
    prompt = f"""你是{emoji}{name}，执行者角色。

## 当前任务
ID: {task_id}
内容: {content}

## 执行步骤（必须全部执行）
1. **理解任务**：分析任务要求，确定执行方法
2. **执行任务**：
   - 如果是计算题：计算并得出答案
   - 如果是文档操作：用feishu-doc技能读取/修改飞书文档
   - 如果是代码任务：用terminal和file工具编写/修改代码
   - 如果是研究任务：用web_search搜索信息
3. **记录结果**：将执行结果写入留言板(doc_id: {message_board_id})

## 输出格式（必须写在留言板）
[{datetime.now().strftime('%H:%M')}] {emoji}{name}
任务: {task_id} - {content}
执行过程: [简要描述你做了什么]
结果: [具体结果，如计算答案、修改内容、研究发现等]
✅ {task_id} 完成

## 重要
- 不要只写"完成"，必须写出具体执行内容和结果
- 如果任务涉及飞书文档，用feishu-doc技能
- 如果任务涉及代码，用terminal或file工具
- 立即执行，完成后返回结果摘要
"""
    
    # 重试机制：最多尝试3次
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[尝试] Spawn子agent (第{attempt}/{max_retries}次)...")
            
            # 真正spawn子agent
            agent = AIAgent(
                model="glm-5",
                enabled_toolsets=["feishu_doc", "file", "terminal", "web"],
                max_iterations=15,
                quiet_mode=True
            )
            print("[创建] AIAgent实例创建成功")
            
            # 执行任务
            print("[执行] 子agent开始执行任务...")
            result = agent.run_conversation(prompt)
            
            # 安全处理返回值
            if result:
                if isinstance(result, dict):
                    result_str = f"dict with keys: {list(result.keys())}"
                elif isinstance(result, str):
                    result_str = f"str ({len(result)} chars): {result[:200]}"
                else:
                    result_str = f"{type(result).__name__}: {str(result)[:200]}"
            else:
                result_str = '无输出'
            
            print(f"[完成] 子agent返回: {result_str}")
            return True
            
        except KeyboardInterrupt:
            print("[中断] 用户中断执行")
            return False
        except Exception as e:
            print(f"[错误] Spawn失败 (尝试 {attempt}/{max_retries}): {type(e).__name__}: {e}")
            
            # 如果是最后一次尝试，打印详细错误
            if attempt == max_retries:
                import traceback
                print("[详细错误] " + traceback.format_exc())
                print("[失败] 所有重试均失败，请检查：")
                print("  1. Hermes Agent是否正确安装")
                print("  2. 依赖包是否完整 (pip install -r requirements.txt)")
                print("  3. 环境变量是否配置正确")
                return False
            else:
                # 等待后重试
                import time
                wait_time = 2 * attempt
                print(f"[等待] {wait_time}秒后重试...")
                time.sleep(wait_time)
    
    return False


def checkout_signin(token, who):
    """签到打卡 - 统一写在留言板"""
    now = datetime.now().strftime('%H:%M')
    emoji = WHO_EMOJI.get(who, '❓')
    name = WHO_NAME.get(who, '未知')
    
    # 签到写在留言板，不找单独的签到文档
    message_board_id = get_current_message_board(token)
    if not message_board_id:
        print(f"[FAIL] 无法找到当前时段留言板")
        return False
    
    sign_text = f"{emoji} {name} 签到 | {now}"
    append_to_doc(token, message_board_id, sign_text)
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
        record_action('签到', '成功', who='adai')
    else:
        print("[WARN] 签到失败")
    
    # 3. 读留言板，找分配给自己的任务
    message_board_id = get_current_message_board(token)
    message_board_content = read_doc(token, message_board_id)
    task = find_my_task(message_board_content, who)
    
    if task:
        print(f"\n[发现任务] {task['id']}: {task['content']}")
        
        # 4. spawn子agent执行任务
        print(f"[执行] 启动子agent...")
        spawn_agent_and_execute(who, task, message_board_id)
        
        # 记录任务已完成
        completed = load_completed_tasks(who)
        completed.add(task['id'])
        save_completed_tasks(who, completed)
        print(f"[记录] 任务 {task['id']} 已标记完成")
        record_action('完成任务', f"{task['id']}: {task.get('content', '')}", who='adai')
        
        # 5. 交任务（留言板）
        now = datetime.now().strftime('%H:%M')
        deliver_text = f"\n[{now}] {WHO_EMOJI.get(who)} {WHO_NAME.get(who)}\n✅ {task['id']} 完成\n"
        append_to_doc(token, message_board_id, deliver_text)
        print(f"[交付] 已写入留言板")
        
        # 6. 发消息触发爱马仕
        trigger_msg = f"{WHO_EMOJI.get(who)} {WHO_NAME.get(who)} 任务完成，请🦬爱马仕检查发布新任务"
        send_feishu_message(token, trigger_msg)
        print(f"[触发] 已发消息触发爱马仕")
    else:
        print("[OK] 无分配给自己的任务")
    
    # 7. 记录项目进展
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    progress_text = f"\n🐂 阿呆 心跳 | {now}"
    if task:
        progress_text += f" | 执行: {task['id']}"
    append_to_doc(token, PROJECT_PROGRESS_DOC, progress_text)
    print(f"[进展] 已写入项目进展记录")
    
    print(f"\n[完成] 心跳结束 {datetime.now().strftime('%H:%M:%S')}")
    return True


if __name__ == '__main__':
    if not FEISHU_APP_SECRET:
        print("[ERROR] 未设置 FEISHU_APP_SECRET 环境变量")
        sys.exit(1)
    
    heartbeat("adai")