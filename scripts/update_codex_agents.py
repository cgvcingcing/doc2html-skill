#!/usr/bin/env python3
"""Update only the doc-to-html instructions owned by the installer."""

import argparse
import os
import pathlib
import re
import tempfile


START = "<!-- doc-to-html:start -->"
END = "<!-- doc-to-html:end -->"
BLOCK = """<!-- doc-to-html:start -->
# doc-to-html（文档转 HTML）
当用户要求把 Markdown、需求/方案文档或方案截图转换成 HTML 时，使用 doc-to-html skill；显式调用为 `$doc-to-html`。若技能正文未加载，读取与本 AGENTS.md 同目录的 `skills/doc-to-html/SKILL.md`，转换脚本在该技能目录的 `scripts/` 下。旧提示词保留在同目录的 `prompts/doc-to-html.md`。
<!-- doc-to-html:end -->
"""
LEGACY = """# doc-to-html（文档转 HTML）
当用户要求把 markdown、需求/方案文档、方案截图转换成 HTML/网页版时，读取并遵循 ~/.codex/prompts/doc-to-html.md；转换脚本与该提示词同级的 doc-to-html/scripts/ 目录下。
"""


def update_agents(path: pathlib.Path, remove: bool = False) -> bool:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    managed = list(re.finditer(re.escape(START) + r".*?" + re.escape(END) + r"\n?", text, re.S))
    if text.count(START) != len(managed) or text.count(END) != len(managed):
        raise ValueError("doc-to-html 托管标记不完整，原文件未修改")

    spans = [(match.start(), match.end()) for match in managed]
    spans.extend((match.start(), match.end()) for match in re.finditer(re.escape(LEGACY), text))
    spans.sort()
    if spans:
        updated = text
        for index in range(len(spans) - 1, -1, -1):
            start, end = spans[index]
            replacement = BLOCK if index == 0 and not remove else ""
            updated = updated[:start] + replacement + updated[end:]
    elif remove:
        return False
    else:
        separator = "" if not text or text.endswith("\n\n") else "\n" if text.endswith("\n") else "\n\n"
        updated = text + separator + BLOCK

    if updated == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as staged:
        staged.write(updated)
        pending = pathlib.Path(staged.name)
    try:
        pending.chmod(path.stat().st_mode & 0o777 if path.exists() else 0o644)
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="维护 doc-to-html 的 Codex 入口提示，保留其他用户规则")
    parser.add_argument("path", type=pathlib.Path)
    parser.add_argument("--remove", action="store_true", help="仅移除安装器管理的入口提示")
    args = parser.parse_args()
    changed = update_agents(args.path, args.remove)
    print("    已移除入口提示。" if args.remove and changed else
          "    已更新入口提示。" if changed else "    入口提示无需修改。")


if __name__ == "__main__":
    main()
