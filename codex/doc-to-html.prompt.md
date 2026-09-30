# doc-to-html：把 Markdown / 方案截图（含文字）/ 需求方案文档转换成本地单文件 HTML

本提示词与 Claude Code / ZCode 的 doc-to-html skill 等价（契约见该项目 PROTOCOL.md），共用同一转换脚本，保证各端产物一致。脚本产物自带可折叠侧栏目录与分节楼层配色。

## 脚本定位（契约）

转换脚本 `scripts/md2html.py` 与**本提示词同级**的 `doc-to-html/` 目录下，首选路径：

```
~/.codex/prompts/doc-to-html/scripts/md2html.py
```

若该路径不存在，按顺序探测（命中即停）：

1. `~/.zcode/skills/doc-to-html/scripts/md2html.py`
2. `~/.claude/skills/doc-to-html/scripts/md2html.py`

全部未命中 → 告知用户运行 skill 源项目的 `install.sh`。下文以 `<脚本>` 指代定位到的路径。

## 工作流程

1. **收集输入**：`.md` 文档；截图/方案图（png/jpg，内含文字）；需求/方案文档（docx/pdf）。输出目录默认与第一个输入文件相同。
2. **截图处理**：逐张查看图片，把其中的文字、表格、流程**忠实转写**为 markdown 片段（表格用 GFM 表格），存为 `extracts/<图片名>.md`；在组装稿里先 `![描述](图片路径)` 引用原图，紧随其后放转写内容并注明"（上图文字转写如下）"。不得臆造图中内容，模糊处标注"（图中此处模糊，请人工核对）"。
3. **docx/pdf 预处理**：优先 `pandoc -t gfm -o 提取.md 文件.docx`（pdf 用 `pdftotext -layout`）；无工具时用 python 库提取。提取后通读修复表格断裂与标题层级。
4. **组装 markdown**：合并为一个 `assembled.md`，不删改原文语义，只整理结构；文档头部元信息保持为 blockquote（脚本会自动折叠）。
5. **转换**：
   ```bash
   python3 <脚本> assembled.md -o 输出.html --title "文档标题" --subtitle "来源说明"
   ```
   常用参数：`--accent "#4f46e5"`、`--link-images`、`--assets-base DIR`、多 md 输入自动合并、`--cleanup PATH...` 转换成功后顺带删除中间产物。
6. **自检**：无头浏览器截图抽查首/中/尾三段，确认目录跳转、表格、图片、代码高亮正常。
7. **清理中间产物**（默认必做，任务收尾自动执行、无需用户提醒）：用 `python3 <脚本> --cleanup assembled.md extracts ...` 删除全部过程文件（多个路径空格分隔，目录整删；也可直接附在转换命令末尾），只保留最终 HTML 与用户原始输入；脚本只删显式列出的路径，输出 HTML 受保护绝不误删。用了 `--link-images` 时保留 HTML 引用到的图片。
8. **交付**：告知输出文件绝对路径，说明双击即可离线打开。

## 规则

- 内容忠实，只排版不改写；截图转写不得臆造。
- 单文件离线：图片默认 base64 内嵌。
- Mermaid 代码块保留为源码块（离线可用）；核心配图可手绘 HTML/CSS 替换（参考提示词同级目录的 `style-guide.md`）。
- 零绝对路径：本提示词与产出说明禁止写入机器特定绝对路径（相对定位或 `~` 路径）。
- 脚本报错时先读提示排查（文件不存在、表格管道符未转义等）。
