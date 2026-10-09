# doc2html-skill

把 Markdown、需求文档或方案截图转换为本地 HTML。Codex、Claude Code 和 ZCode 共用转换脚本；文档提取与截图转写由 agent 完成。

图片在正文中显示缩略图。点击图片或“查看大图”，可在整个浏览器窗口里查看、缩放和拖动；打开时自动适应屏幕，关闭或按 Esc 回到文档。

## 安装

需要 Python 3.10 及以上版本；首次安装 Python 依赖需要 pip 和网络。在本仓库根目录执行：

```bash
bash install.sh
```

安装后打开新的 agent 会话。Codex 原生入口为 `~/.codex/skills/doc-to-html/`，Claude Code 为 `~/.claude/skills/doc-to-html/`。Codex 旧提示词入口保留兼容；自定义 `CODEX_HOME` 时，Codex 安装目录跟随该设置。

## 快捷调用

在 Codex 会话中输入，也可以通过 `/skills` 选择 doc-to-html：

```text
$doc-to-html 把 docs/需求.md 转成 HTML，输出到 docs/需求.html
```

在 Claude Code 会话中输入：

```text
/doc-to-html 把 docs/需求.md 转成 HTML，输出到 docs/需求.html
```

三端也支持自然语言：“把 docs/需求.md 转成 HTML”。支持旧自定义 prompt 的 Codex CLI 可使用 `/prompts:doc-to-html`。

## 在 IDEA 项目里使用

把需求放在业务项目里，例如 `docs/需求.md`。在 IDEA 的 Terminal 中确认当前目录为业务项目根目录，运行 `codex` 或 `claude`，再使用上面的调用方式。项目关联的 agent 会话也可使用同样的相对路径。

默认输出和第一个输入在同一目录。单个 Markdown 可以直接运行转换脚本：

```bash
python3 ~/.codex/skills/doc-to-html/scripts/md2html.py docs/需求.md
```

输出为 `docs/需求.html`，原始 Markdown 保留。Word、PDF 和截图需要通过 agent 的提取流程转换；放入文件后需发起一次转换。

## 清理与卸载

清理中间产物时，HTML 文件受保护；目录中包含 HTML 或本次输出文件，会跳过整个目录并提示。可单独指定不含成品的提取目录或过程文件。

```bash
python3 ~/.codex/skills/doc-to-html/scripts/md2html.py --cleanup assembled.md extracts/
bash install.sh --uninstall
```

卸载只移除本项目的安装副本和 Codex 托管入口，保留源项目与其他用户规则。路径布局、CLI 参数和平台适配规则见 [PROTOCOL.md](PROTOCOL.md)。
