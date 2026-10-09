# doc-to-html 平台适配协议（PROTOCOL v1.4）

本文件是 doc2html-skill 的**契约**：定义同一份技能如何映射到 Claude Code、Codex、ZCode 三个平台，以及各平台副本必须遵守的路径与接口规则。改动任何一侧（SKILL.md / prompt / 脚本 CLI）前先读本文件。

## 1. 平台映射

| 平台 | 指令文件（入口） | 脚本锚点（与入口的相对关系） |
| --- | --- | --- |
| Claude Code | `~/.claude/skills/doc-to-html/SKILL.md` | 同目录 `scripts/md2html.py` |
| ZCode | `~/.zcode/skills/doc-to-html/SKILL.md` | 同目录 `scripts/md2html.py` |
| Codex 原生 skill | `~/.codex/skills/doc-to-html/SKILL.md` | 同目录 `scripts/md2html.py` |
| Codex 兼容 prompt | `~/.codex/prompts/doc-to-html.md` | 同级目录 `doc-to-html/scripts/md2html.py` |

- Claude Code、ZCode 与 Codex 原生入口共用**同一份** `SKILL.md`（逐字相同），仅安装位置不同。
- Codex 的兼容 prompt 是等价改写（无 frontmatter、路径写法不同），语义必须与 SKILL.md 保持一致。原生 skill 使用 `$doc-to-html`，也可通过 `/skills` 选择；Claude Code 使用 `/doc-to-html`。兼容提示词在支持该功能的 CLI 中使用 `/prompts:doc-to-html`。
- 每个安装副本附带 `PROTOCOL.md`、`style-guide.md`（手工增强指引）与 `scripts/_vendor/`（Python 依赖，安装时预热生成）。设置了自定义 `CODEX_HOME` 时，Codex 安装根随之调整。

## 2. 路径书写硬规则

**任何安装到平台目录的文件（SKILL.md / prompt / 脚本 / AGENTS.md 指针），禁止写死带用户名或机器项目根目录的绝对路径**。允许的写法只有两种：

1. **相对本文件**：「与本 SKILL.md 同目录的 `scripts/md2html.py`」；
2. **`$HOME` 相对**：`~/.zcode/skills/doc-to-html/scripts/md2html.py` 这类以 `~` 开头的用户级路径。

原因：用户名、项目位置因机器而异；硬编码路径是泄漏源，也是换机失效的根源。

## 3. 运行时脚本发现顺序

agent 在执行时按以下顺序定位脚本，**命中即停**：

1. 正在读的 SKILL.md **同目录**的 `scripts/md2html.py`；Codex 兼容 prompt 则定位其同级 `doc-to-html/scripts/md2html.py`；
2. 依次探测：`~/.zcode/skills/doc-to-html/scripts/md2html.py` → `~/.claude/skills/doc-to-html/scripts/md2html.py` → `~/.codex/skills/doc-to-html/scripts/md2html.py` → `~/.codex/prompts/doc-to-html/scripts/md2html.py`；
3. 全部未命中 → 告知用户在项目根运行 `install.sh`，不要自行猜测其他路径。

## 4. CLI 稳定接口（v1）

`md2html.py` 的命令行参数是跨平台稳定契约，**只能向后兼容地新增**：

```
md2html.py INPUT.md [MORE.md ...] [-o OUTPUT.html] [--title T] [--subtitle S]
                   [--accent HEX] [--assets-base DIR] [--link-images]
                   [--cleanup PATH ...]
```

- 多输入按序合并（`---` 分隔）；`-o` 缺省时与首个输入同名 `.html`。
- 相对输入路径按 agent 或终端当前项目目录解析，适用于 IDEA 项目目录；默认在首个输入所在目录生成 HTML，原始输入保留。
- 图片预览由脚本统一提供：正文缩略图保持在内容列内，独立大图预览默认适应屏幕，支持缩放、拖动、原尺寸与关闭；打印只保留正文图片。带链接的图片保留原有跳转。大图查看不依赖外部脚本或网络，CLI 参数不变。
- `--cleanup` 删除指定的中间产物（文件或目录，空格分隔，目录检查后整删）；只删显式列出的路径，跳过 `.html` / `.htm` 文件（大小写不敏感）以及本次输出文件。目录中包含 HTML 或本次输出文件时，跳过整个目录并提示；单独执行清理时同样检查并保护目录中的 HTML，目录无法检查或为符号链接时也跳过。不带输入文件单独执行时仅做清理。
- 语义变更（参数删除、行为反转）必须升 `PROTOCOL` 版本号，并同步三个平台的指令文件与 `install.sh`。

## 5. 一致性维护规则

- `SKILL.md`（workflow 部分）与 `codex/doc-to-html.prompt.md` **语义同步**：改流程必须双改，再重跑 `install.sh`。
- 安装脚本采用**先清后装**：每次运行先删除旧安装副本（三端 skill 目录、Codex 兼容目录与 prompt 文件），再复制当前版本，保证安装目录里只有新版文件、无历史残留；skill 每次迭代后重跑 `install.sh` 即完成"清理旧版 + 部署新版"。
- Codex 全局 AGENTS.md 只更新带 `doc-to-html:start` / `doc-to-html:end` 标记的托管块；旧安装器生成的两行提示可迁移，其他用户内容保留。
- 依赖（markdown / pymdown-extensions）由脚本自举到各安装副本的 `scripts/_vendor`；`install.sh` 会用真实转换预热，保证离线首跑可用。
- 卸载：`install.sh --uninstall`（删除三端 skill、Codex 兼容入口与 AGENTS.md 中的托管块；**源项目** `doc2html-skill/` 和其他用户规则不受影响）。

## 6. 版本

- PROTOCOL v1（2026-09-29）：初版，确立三平台映射与零绝对路径规则。
- PROTOCOL v1.1（2026-09-30）：脚本内置可折叠侧栏目录与分节楼层配色（产物增强，CLI 不变）；CLI 向后兼容新增 `--cleanup`（清理中间产物）；工作流新增"清理中间产物"默认步骤；安装脚本改为先清理旧副本再部署（先清后装）。
- PROTOCOL v1.2（2026-10-08）：修复清理目录时可能删除最终 HTML 的问题；清理前检查目录中的 HTML 与本次输出文件，命中后跳过整目录，独立清理同样生效；目录无法检查或为符号链接时跳过。CLI 参数不变。
- PROTOCOL v1.3（2026-10-08）：增加 Codex 原生 skill，与 Claude Code / ZCode 共用 SKILL.md；修正显式调用方式，保留旧 prompt；安装副本携带协议文件；Codex 全局入口采用有边界的托管块，迁移和卸载保留其他规则；补充 IDEA 项目目录用法。
- PROTOCOL v1.4（2026-10-09）：脚本统一提供独立大图预览，替换正文框内的原尺寸滚动控件；默认适应屏幕，支持缩放、拖动、原尺寸与关闭，打印隐藏预览控件；修复图片属性顺序不同时未能内嵌的问题。CLI 参数不变。
