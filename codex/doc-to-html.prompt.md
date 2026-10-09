# doc-to-html：把 Markdown / 方案截图（含文字）/ 需求方案文档转换成本地单文件 HTML

本提示词与 Claude Code / ZCode 的 doc-to-html skill 等价（契约见该项目 PROTOCOL.md），共用同一转换脚本，保证各端产物一致。脚本产物自带可折叠侧栏目录与分节楼层配色。

Codex 首选原生 skill：`$doc-to-html 把 docs/需求.md 转成 HTML`，或在 `/skills` 中选择 doc-to-html。此文件保留为兼容提示词；支持自定义 prompt 的 CLI 使用 `/prompts:doc-to-html`。相对输入路径按当前项目目录解析，默认输出到第一个输入所在目录，例如 `docs/需求.html`。

## 脚本定位（契约）

转换脚本 `scripts/md2html.py` 与**本提示词同级**的 `doc-to-html/` 目录下，首选路径：

```
~/.codex/prompts/doc-to-html/scripts/md2html.py
```

若该路径不存在，按顺序探测（命中即停）：

1. `~/.zcode/skills/doc-to-html/scripts/md2html.py`
2. `~/.claude/skills/doc-to-html/scripts/md2html.py`
3. `~/.codex/skills/doc-to-html/scripts/md2html.py`

全部未命中 → 告知用户运行 skill 源项目的 `install.sh`。下文以 `<脚本>` 指代定位到的路径。

## 工作流程

1. **收集输入**：`.md` 文档；截图/方案图（png/jpg，内含文字）；需求/方案文档（docx/pdf）。相对输入路径按用户当前项目目录解析，输出目录默认与第一个输入文件相同。放入文件后需发起一次转换。
2. **截图处理**：逐张查看图片，把其中的文字、表格、流程**忠实转写**为 markdown 片段（表格用 GFM 表格），存为 `extracts/<图片名>.md`；在组装稿里先 `![描述](图片路径)` 引用原图，紧随其后放转写内容并注明"（上图文字转写如下）"。不得臆造图中内容，模糊处标注"（图中此处模糊，请人工核对）"。大图预览由脚本统一提供：正文显示缩略图，点击图片或“查看大图”进入独立预览，默认适应屏幕，可缩放、拖动、查看原尺寸和按 Esc 关闭；无需在正文图片框内增加原尺寸开关。
3. **docx/pdf 预处理**：优先 `pandoc -t gfm -o 提取.md 文件.docx`（pdf 用 `pdftotext -layout`）；无工具时用 python 库提取。提取后通读修复表格断裂与标题层级。
4. **组装 markdown**：合并为一个 `assembled.md`，不删改原文语义，只整理结构；文档头部元信息保持为 blockquote（脚本会自动折叠）。图片相对路径以组装稿目录为基准，必要时用 `--assets-base`；多文档之间保留 `---`，标题层级冲突时以内层文档为 h3。
5. **转换**：
   ```bash
   python3 <脚本> assembled.md -o 输出.html --title "文档标题" --subtitle "来源说明"
   ```
   常用参数：`--accent "#4f46e5"`、`--link-images`、`--assets-base DIR`、多 md 输入自动合并、`--cleanup PATH...` 转换成功后顺带删除中间产物。
6. **自检**：无头浏览器截图抽查首/中/尾三段，确认目录跳转、表格、图片、代码高亮正常；有大图时检查独立预览的适应屏幕、缩放、拖动和关闭。
7. **清理中间产物**（默认必做，任务收尾自动执行、无需用户提醒）：用 `python3 <脚本> --cleanup assembled.md extracts ...` 删除过程文件（多个路径空格分隔，目录检查后整删；也可直接附在转换命令末尾），只保留最终 HTML 与用户原始输入；脚本只删显式列出的路径，保护 `.html` / `.htm` 文件（含大写扩展名）。目录中只要有 HTML，或包含本次输出文件，就跳过整个目录并提示；单独执行清理时同样保护目录中的 HTML，目录无法检查或为符号链接时也跳过。用了 `--link-images` 时保留 HTML 引用到的图片。
8. **交付**：告知输出文件绝对路径，说明双击即可离线打开。

## 规则

- 内容忠实，只排版不改写；截图转写不得臆造。
- 单文件离线：图片默认 base64 内嵌。
- Mermaid 代码块保留为源码块（离线可用）；核心配图可手绘 HTML/CSS 替换（参考与提示词同级的 `doc-to-html/style-guide.md`）。
- 零绝对路径：安装指令与脚本不得写死机器特定绝对路径（相对定位或 `~` 路径）；交付时可给出运行中实际生成的文件路径。
- 脚本报错时先读提示排查（文件不存在、表格管道符未转义等）。
