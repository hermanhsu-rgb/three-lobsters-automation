# 🦞 三小龙虾自动化

飞书文档驱动的任务协作系统。

## 结构

```
scripts/
├── heartbeat_executor.py  # 执行者脚本（阿呆🐂、小结巴🦜）
└── heartbeat_pm.py       # PM脚本（爱马仕🦬）
```

## 使用

```bash
# 执行者
python3 scripts/heartbeat_executor.py --who adai
python3 scripts/heartbeat_executor.py --who xiaojieba

# PM
python3 scripts/heartbeat_pm.py --who aimashu
```

## 环境变量

```
FEISHU_APP_ID=xxx
FEISHU_APP_SECRET=xxx
SIGNIN_FOLDER_ID=TUcWf6Kyql4d6gdi1nWc7TxVnDe
MESSAGE_BOARD_ID=Lj0OdVYvuoAKvVxOxr0crc9ynWg
TASK_BOARD_ID=EFcudwbCCozKaQx2peocy7NIn5b
FEISHU_GROUP_ID=oc_6e680216125c663a3359e07cb6831fe7
```

## 工作流程

1. Cron触发 → 签到
2. 读留言板 → 找分配给自己的任务
3. Spawn子agent执行
4. 完成交付 → 发消息触发下一个

## 设计文档

https://kcnr7kouatcj.feishu.cn/docx/NjQzdkbbdokVhOxX1HQcFIy2nZc