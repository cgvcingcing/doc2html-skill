#!/usr/bin/env bash
# doc2html-skill 安装器：按 PROTOCOL.md v1 把技能装配到 Claude Code / ZCode / Codex 三平台
# 用法：install.sh [--uninstall]
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
# 三平台安装根（全部 $HOME 相对，禁止机器特定绝对路径，见 PROTOCOL.md §2）
CLAUDE_SKILL="${HOME}/.claude/skills/doc-to-html"
ZCODE_SKILL="${HOME}/.zcode/skills/doc-to-html"
CODEX_DIR="${HOME}/.codex/prompts/doc-to-html"
CODEX_PROMPT="${HOME}/.codex/prompts/doc-to-html.md"
CODEX_AGENTS="${HOME}/.codex/AGENTS.md"

uninstall() {
  echo "==> 卸载三平台安装副本（源项目不动）"
  rm -rf "${CLAUDE_SKILL}" "${ZCODE_SKILL}" "${CODEX_DIR}" "${CODEX_PROMPT}"
  if [ -f "${CODEX_AGENTS}" ]; then
    python3 - "${CODEX_AGENTS}" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
t = p.read_text(encoding="utf-8")
marker_start = t.find("# doc-to-html（")
if marker_start >= 0:
    p.write_text(t[:marker_start].rstrip() + "\n", encoding="utf-8")
    print("    已从 AGENTS.md 移除指针块。")
else:
    print("    AGENTS.md 中无指针块，跳过。")
PY
  fi
  echo "完成卸载。"
  exit 0
}

[ "${1:-}" = "--uninstall" ] && uninstall

echo "==> 清理旧版安装副本（先清后装，保证无历史残留）"
rm -rf "${CLAUDE_SKILL}" "${ZCODE_SKILL}" "${CODEX_DIR}" "${CODEX_PROMPT}"

install_copy() { # $1=目标目录
  mkdir -p "$1/scripts"
  cp "${SRC}/scripts/md2html.py" "$1/scripts/md2html.py"
  cp "${SRC}/references/style-guide.md" "$1/style-guide.md"
  chmod +x "$1/scripts/md2html.py" 2>/dev/null || true
}

echo "==> Claude Code → ${CLAUDE_SKILL}"
install_copy "${CLAUDE_SKILL}"
cp "${SRC}/SKILL.md" "${CLAUDE_SKILL}/SKILL.md"

echo "==> ZCode → ${ZCODE_SKILL}"
install_copy "${ZCODE_SKILL}"
cp "${SRC}/SKILL.md" "${ZCODE_SKILL}/SKILL.md"

echo "==> Codex → ${CODEX_PROMPT} + ${CODEX_DIR}"
install_copy "${CODEX_DIR}"
cp "${SRC}/codex/doc-to-html.prompt.md" "${CODEX_PROMPT}"

echo "==> 在 ${CODEX_AGENTS} 写入入口提示（幂等，零绝对路径）"
if [ ! -f "${CODEX_AGENTS}" ] || ! grep -q "doc-to-html" "${CODEX_AGENTS}" 2>/dev/null; then
  cat >> "${CODEX_AGENTS}" <<'EOF'

# doc-to-html（文档转 HTML）
当用户要求把 markdown、需求/方案文档、方案截图转换成 HTML/网页版时，读取并遵循 ~/.codex/prompts/doc-to-html.md；转换脚本与该提示词同级的 doc-to-html/scripts/ 目录下。
EOF
  echo "    已写入。"
else
  echo "    已存在，跳过。"
fi

echo "==> 预热依赖（真实转换，装进各副本的 scripts/_vendor）"
for copy in "${CLAUDE_SKILL}" "${ZCODE_SKILL}" "${CODEX_DIR}"; do
  if python3 "${copy}/scripts/md2html.py" "${SRC}/samples/sample.md" -o /tmp/doc2html_warmup.html --title warmup >/dev/null 2>&1; then
    echo "    ${copy} 依赖就绪。"
  else
    echo "    ${copy} 预热失败（离线环境？首次使用时会再尝试）。"
  fi
done
rm -f /tmp/doc2html_warmup.html

echo
echo "完成（PROTOCOL v1.1）。使用方式："
echo "  - Claude Code：直接说「把 xx 方案转成 HTML」，或 /doc-to-html"
echo "  - ZCode：      直接说「把 xx 方案转成 HTML」（新会话生效）"
echo "  - Codex CLI：  会话内输入 /doc-to-html"
echo "  - 卸载：       bash $0 --uninstall"
