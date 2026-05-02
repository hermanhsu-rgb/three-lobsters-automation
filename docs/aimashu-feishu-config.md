# 🦬 爱马仕飞书触发配置完整指南

> 三小龙虾协作系统 - 爱马仕飞书消息触发配置

## 配置文件位置

`~/.hermes/config.yaml`

---

## 1. 飞书平台配置

在 `config.yaml` 中找到或添加 `platforms:` 部分：

```yaml
platforms:
  feishu:
    enabled: true
    extra:
      app_id: <爱马仕自己的app_id>        # ⚠️ 必须用爱马仕自己的！
      app_secret: <爱马仕自己的app_secret>  # ⚠️ 必须用爱马仕自己的！
      dm_policy: open        # 私聊开放
      group_policy: open     # 群消息开放（关键！）
      require_mention: false # 不需要@mention
      bot_trigger_names:     # 触发词列表
      - 爱马仕
      - aimashu
```

### 各参数说明

| 参数 | 值 | 说明 |
|------|-----|------|
| `enabled` | `true` | 启用飞书平台 |
| `app_id` | 爱马仕自己的 | 飞书开放平台应用ID |
| `app_secret` | 爱马仕自己的 | 飞书开放平台应用密钥 |
| `dm_policy` | `open` | 私聊消息开放 |
| `group_policy` | `open` | 群消息开放（关键！） |
| `require_mention` | `false` | 不需要@也能触发 |
| `bot_trigger_names` | `["爱马仕", "aimashu"]` | 触发关键词 |

---

## 2. 环境变量配置

在 `config.yaml` 底部添加：

```yaml
FEISHU_HOME_CHANNEL: oc_6e680216125c663a3359e07cb6831fe7
```

这是三小龙虾群的ID，大家共用。

---

## 3. 平台工具集配置

确保 `config.yaml` 中有以下内容：

```yaml
platform_toolsets:
  cli:
  - hermes-cli
  feishu:
  - hermes-cli
```

---

## 4. 飞书开放平台配置

### 4.1 获取应用凭证

1. 登录 [飞书开放平台](https://open.feishu.cn/)
2. 进入你的应用
3. 点击「凭证与基础信息」
4. 复制 `App ID` 和 `App Secret`

### 4.2 配置事件订阅

在飞书开放平台后台：

1. 进入你的应用
2. 点击「事件订阅」
3. 勾选 `im.message.receive_v1`（接收消息）
4. 点击「添加事件」

### 4.3 配置权限

确保应用有以下权限：

- `im:message` - 获取消息
- `im:message:receive_as_bot` - 接收群消息
- `docx:document` - 读写文档

---

## 5. 应用配置后重启

```bash
# 重启Hermes网关
hermes gateway restart
```

---

## 6. 验证连接

```bash
# 查看网关日志
tail -f ~/.hermes/logs/gateway.log
```

应该看到类似输出：

```
✓ feishu connected
[Lark] connected to wss://msg-frontier.feishu.cn/ws/v2...
```

---

## 7. 触发规则说明

| 消息内容 | 爱马仕响应 | 说明 |
|---------|-----------|------|
| "爱马仕在吗" | ✅ 响应 | 包含触发词 |
| "@爱马仕 你好" | ✅ 响应 | 包含触发词 |
| "大家集合" | ✅ 响应 | "大家/all/所有人"触发所有bot |
| "随便聊聊" | ❌ 不响应 | 没有触发词 |

---

## 8. 爱马仕特殊职责

爱马仕在系统中担任PM角色，负责：

1. **创建留言板** - 每6小时自动创建新留言板
2. **发布任务** - 从任务池发布任务到留言板
3. **检查交付** - 检查任务完成情况

### 8.1 PM心跳脚本

```bash
# 每6小时创建新留言板
python3 ~/.hermes/repos/three-lobsters-automation/scripts/heartbeat_pm.py
```

### 8.2 Cron配置

```bash
# 编辑crontab
hermes cronjob create --name "heartbeat-aimashu" \
  --schedule "*/5 * * * *" \
  --prompt "运行爱马仕PM心跳脚本：python3 ~/.hermes/repos/three-lobsters-automation/scripts/heartbeat_pm.py"
```

---

## 9. 常见问题

### Q: 为什么发消息爱马仕没反应？

检查：
1. Gateway是否在运行：`ps aux | grep hermes gateway`
2. 飞书是否已连接：`tail -f ~/.hermes/logs/gateway.log`
3. 事件订阅是否已启用：飞书开放平台 → 事件订阅
4. 消息是否包含触发词："爱马仕" 或 "aimashu"

### Q: 如何调试？

```bash
# 实时查看日志
tail -f ~/.hermes/logs/gateway.log

# 查看收到的消息
tail -f ~/.hermes/logs/gateway.log | grep "inbound message"
```

### Q: 爱马仕的app_id是什么？

需要爱马仕自己去飞书开放平台创建应用获取。不要用阿呆或小结巴的！

---

## 10. 完整配置示例

以下是完整的 `config.yaml` 飞书相关部分：

```yaml
platforms:
  feishu:
    enabled: true
    extra:
      app_id: cli_xxxxxxxxxxxx       # 替换成爱马仕自己的
      app_secret: xxxxxxxxxxxxxxxx   # 替换成爱马仕自己的
      dm_policy: open
      group_policy: open
      require_mention: false
      bot_trigger_names:
      - 爱马仕
      - aimashu

platform_toolsets:
  cli:
  - hermes-cli
  feishu:
  - hermes-cli

FEISHU_HOME_CHANNEL: oc_6e680216125c663a3359e07cb6831fe7
```

---

## 11. 配置完成后测试

1. 去飞书群（三小龙虾协作群）
2. 发送："爱马仕在吗"
3. 爱马仕应该响应

---

## 附录：三小龙虾配置对比

| 配置项 | 阿呆 | 小结巴 | 爱马仕 |
|--------|------|--------|--------|
| bot_trigger_names | ["阿呆", "adai"] | ["小结巴", "xiaojieba"] | ["爱马仕", "aimashu"] |
| 角色 | 执行者 | 执行者 | PM |
| app_id | cli_a934f35cd8385cc0 | 小结巴自己的 | 爱马仕自己的 |
| FEISHU_HOME_CHANNEL | oc_6e680216125c663a3359e07cb6831fe7 | 同左 | 同左 |
| 职责 | 签到→执行→交付 | 签到→执行→交付 | 创建留言板→发布任务→检查交付 |

---

**文档版本**: 2026-05-02
**仓库**: github.com/heng-kaihsu-rgb/three-lobsters-automation
