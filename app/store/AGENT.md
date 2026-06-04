# app/store/ — 数据存储层

会话状态持久化。**换数据库（SQLite → MySQL/Postgres）只动这一目录，接口不变。**

## 文件

### db.py —— SQLite 会话状态
单表 `sessions`，按 `candidate_id` 跟踪招聘阶段与简历快照。
对话历史本身**不存**（由 RPA 每轮抓取传入），这里只存跨轮需要记住的状态。

表结构：
```
sessions(
  candidate_id TEXT PRIMARY KEY,  -- 候选人唯一标识
  stage        TEXT,              -- 招聘阶段 (默认 "初次接触")
  resume       TEXT,              -- 最近一份简历快照
  updated_at   TEXT               -- 更新时间
)
```

函数：
- `init_db()` —— 建表（不存在才建）。由 [app/main.py](../main.py) 启动时调用。
- `get_session(candidate_id)` —— 查一条，无则返回 `None`。
- `get_or_default(candidate_id)` —— 查一条，无则返回默认值字典（**不落库**）。pipeline 读状态用这个。
- `upsert_session(candidate_id, stage, resume)` —— 写入或更新（`ON CONFLICT` 做 upsert）。pipeline 收尾用这个。
- `reset_session(candidate_id)` —— 删除一条，返回是否删到。`/reset` 调试接口用。
- `_conn()` —— 内部 contextmanager，开连接 + 自动 commit/close，`row_factory=Row` 让结果可按列名取。

特点：Python 标准库 `sqlite3`，**零安装零部署**，文件路径由 `settings.db_path` 决定。

## 改这里的时机
- 加要持久化的状态字段（如"上次已回复的消息指纹"用于去重，见 [PLAN.md](../../PLAN.md) P2 第 8 项）
- 换数据库引擎：保持以上函数签名不变，替换内部实现即可，pipeline 无感知
