# 影刀流程改造清单（逐节点对照）

本文档对照**旧影刀流程**逐节点说明怎么改。目标：影刀只做"手脚"（抓取/点击/输入），所有判断（求简历、是否 OCR、回什么话）收口到后端 `POST /reply`。

## 改造原则

1. **删除所有 IF 业务判断**：仅在线简历、随机话术等逻辑后端已实现（`fast_path` 返回 `request_resume`）
2. **OCR 按需**：仅当 `/reply` 返回 `need_resume_ocr=true` 时才点「附件简历」+ OCR，之后带 `trigger=after_resume_ocr` 二次调用
3. **岗位外置**：循环外只设 `current_job_id` 一个变量，JD/公司信息由后端从 [../jobs.yaml](../jobs.yaml) 加载
4. **不用固定坐标 / 固定 Sleep**：坐标点击改元素点击，固定等待改「等待元素出现」
5. **每个候选人记一行日志**：`rpa_main.py` / `rpa_after_ocr.py` 已输出 `rpa_log`（单行 JSON），接「打印日志」节点即可

## 旧流程逐节点对照

### 循环外（进入页面）

| # | 旧节点 | 处理 | 说明 |
|---|--------|------|------|
| 1 | 点击元素「未读」 | 保留 | — |
| 2 | 等待 1~2 秒 | 替换 | 改「等待元素出现」候选人列表 |
| 3 | 点击元素「全部职位」 | 保留 | — |
| 4 | 点击元素「电商运营助理_苏州」 | 保留 | 同时在循环外新增变量：`api_url = http://127.0.0.1:8000/reply`、`current_job_id = ecommerce_ops_suzhou` |
| 5 | 等待 0~1 秒 | 替换 | 改「等待元素出现」 |
| 6 | 执行JS脚本 → `web_js_result` | 保留 | 参考实现见 [extract_candidates.js](extract_candidates.js)，返回 JSON 数组 |
| 7 | 打印日志 `web_js_result`（已禁用） | 保留 | 建议启用，打印候选人数量 |

### ForEach 循环内

| # | 旧节点 | 处理 | 说明 |
|---|--------|------|------|
| 8 | 获取元素对象 `row['itemXpath']` → 点击候选人 | 保留 | — |
| 9 | 执行JS脚本 → `all_chat_text` | 替换 | 改用 [extract_chat.js](extract_chat.js)，一次返回 `candidate_id` / `conversation` / `last_message_from` 等结构化 JSON → 变量 `chat_data` |
| 10 | IF `all_chat_text` 包含「备注：无附件简历，仅在线简历」 | **删除整个分支** | 后端 `fast_path` 检测到该提示会返回 `rpa_action=request_resume` |
| 11 | ├ 产生随机数 0~10 → `random_number` | 删除 | 话术由后端生成 |
| 12 | ├ IF `random_number >= 6` 键盘输入「你好，方便看下你的简历吗?」/ Else 键盘输入公司介绍 | 删除 | 同上，`request_resume` 的 `answer` 字段就是要发送的话术 |
| 13 | ├ 点击「求简历」→ 点击「确定」 | 移动 | 移到新流程 `rpa_action=request_resume` 分支内 |
| 14 | └ 继续下一次循环 | 删除 | — |
| 15 | 点击元素「附件简历」+ 等待 2~4 秒 | 移动 | 移到 `need_resume_ocr=true` 分支内；等待改「等待元素出现」简历弹层 |
| 16 | 通用文字识别 → `general_text` → `resume_person` | 移动 | 同上，仅按需执行 |
| 17 | 鼠标点击坐标 (1468,928) / (1394,930) 关弹层 | 替换 | 改「点击元素」关闭按钮，分辨率变化不会失效 |
| 18 | 设置变量 `job_requirement` = 硬编码 JD | **删除** | 改传 `job_id`，后端从 jobs.yaml 加载 |
| 19 | 设置变量 `company_info` = 硬编码公司介绍 | **删除** | 同上 |
| 20 | 插入代码段(Python) 调 `/reply` | 替换 | 改用 [rpa_main.py](rpa_main.py)（含异常降级 skip + 日志） |
| 21 | 从文本中提取内容 `answer` → `content` | 删除 | `rpa_main.py` 已直接输出 `content` 变量 |
| 22 | 键盘输入 `content {ENTER}` | 移动 | 移到 `rpa_action=reply_message` 分支内 |

## 新流程完整节点顺序（照此搭建）

```
循环外:
  1. 设置变量 api_url = http://127.0.0.1:8000/reply
  2. 设置变量 current_job_id = ecommerce_ops_suzhou
  3. 打开 Boss 聊天页 → 点击「未读」→ 点击「全部职位」→ 选职位
  4. 等待元素出现: 候选人列表
  5. 执行JS脚本 extract_candidates.js → web_js_result (json.loads 成列表)

ForEach web_js_result → row:
  6.  获取元素对象 row['itemXpath'] → 点击候选人
  7.  等待元素出现: 聊天消息区
  8.  执行JS脚本 extract_chat.js → chat_extract_json (json.loads → chat_data)
  9.  设置变量 resume_person = ""
  10. 插入代码段(Python): rpa_main.py
      → 输出 rpa_action / content / need_resume_ocr / rpa_log
  11. 打印日志: rpa_log
  12. IF need_resume_ocr 等于 true:
        a. 点击元素「附件简历」
        b. 等待元素出现: 简历弹层
        c. 通用文字识别 → general_text
        d. 设置变量 resume_person = general_text.text
        e. 点击元素: 弹层关闭按钮 (不要用坐标)
        f. 插入代码段(Python): rpa_after_ocr.py
           → 覆盖 rpa_action / content / rpa_log
        g. 打印日志: rpa_log
      End IF
  13. IF rpa_action 等于 "skip":
        继续下一次循环
  14. ELSE IF rpa_action 等于 "request_resume":
        IF content 不为空: 键盘输入 content {ENTER}
        点击元素「求简历」→ 点击元素「确定」
  15. ELSE IF rpa_action 等于 "reply_message":
        键盘输入 content {ENTER}
  16. ELSE IF rpa_action 等于 "send_company_address":
        执行「发送公司地址」预设动作
      End IF
循环结束
```

## 影刀变量一览

| 变量 | 来源 | 说明 |
|------|------|------|
| `api_url` | 循环外手动设置 | `/reply` 接口地址 |
| `current_job_id` | 循环外手动设置 | 对应 jobs.yaml 中的 `job_id` |
| `web_js_result` | extract_candidates.js | 候选人列表 JSON 数组 |
| `chat_data` | extract_chat.js | 当前候选人对话与元数据 |
| `resume_person` | OCR（按需） | 简历文本，默认空字符串 |
| `rpa_action` / `content` / `need_resume_ocr` / `rpa_log` | rpa_main.py / rpa_after_ocr.py | 动作指令、回复文本、是否需 OCR、单行日志 |

## API 响应字段

```json
{
  "answer": "回复文本",
  "need_resume_ocr": false,
  "reason": {
    "rpa_action": "skip | request_resume | reply_message | send_company_address",
    "basis": "决策原因",
    "next_stage": "后端维护的下一阶段，影刀可忽略"
  }
}
```

## 文件

| 文件 | 用途 |
|------|------|
| [extract_candidates.js](extract_candidates.js) | 循环外一次抓取候选人列表 |
| [extract_chat.js](extract_chat.js) | 循环内一次抓取对话与元数据 |
| [rpa_main.py](rpa_main.py) | 影刀「插入代码段(Python)」主调用 |
| [rpa_after_ocr.py](rpa_after_ocr.py) | OCR 完成后二次调用 |
| [../jobs.yaml](../jobs.yaml) | 岗位 JD/公司配置 |

## 日志格式

`rpa_log` 为单行 JSON，直接接「打印日志」节点：

```json
{"phase": "done", "candidate_id": "xxx", "rpa_action": "reply_message", "ocr_done": false, "basis": "...", "elapsed_ms": 850}
```

`phase` 取值：`done`（正常完成）/ `need_ocr`（待 OCR 二次调用）/ `after_ocr`（OCR 后完成）/ `error`（接口异常，已降级 skip）。
