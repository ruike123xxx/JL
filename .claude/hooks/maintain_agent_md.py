#!/usr/bin/env python
"""PostToolUse hook: 提醒维护 AGENT.md 文档。

当 Edit/Write/MultiEdit 修改了 app/ 下的 .py 文件时, 向模型注入一条
additionalContext, 提醒它去更新该文件所在目录的 AGENT.md, 保持文档与代码同步。

读取 stdin 的 hook JSON, 不依赖 jq。无关文件则静默退出。
"""
import json
import os
import sys


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return  # 拿不到输入就静默放过, 不打断流程

    tool_input = data.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path") or ""
    if not file_path:
        return

    norm = file_path.replace("\\", "/")

    # 只关心 app/ 下的 .py 文件
    if "/app/" not in norm and not norm.startswith("app/"):
        return
    if not norm.endswith(".py"):
        return

    # 该文件所在目录的 AGENT.md
    agent_md = os.path.join(os.path.dirname(file_path), "AGENT.md")
    agent_md_disp = agent_md.replace("\\", "/")

    reminder = (
        f"你刚修改了 {norm}。请检查该文件所在目录的 AGENT.md "
        f"({agent_md_disp}) 是否还准确描述了这个文件的功能/职责/关键函数；"
        "若代码改动影响了文档内容(如新增/删除函数、改变职责、改了 RPA 动作枚举等), "
        "请同步更新 AGENT.md。若改动不影响文档(如纯内部重构), 可忽略。"
    )

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": reminder,
        }
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
