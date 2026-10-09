# doc2html-skill

把 **Markdown、方案截图（内含文字）、需求/方案文档（docx/pdf）** 转换成一个**美观、可离线双击打开的单文件 HTML**：自动侧栏目录（滚动高亮、h2 分组折叠、整栏收起）、分节楼层配色（各 h2 章节循环 8 色标注）、表格与代码美化、图片 base64 内嵌、打印友好；转换后清理中间产物，只保留最终 HTML。

大图由转换脚本统一提供独立预览，默认适应屏幕，支持缩放、拖动、原尺寸和关闭。无需在正文图片框内手工加入原尺寸滚动开关。

核心转换是确定性脚本 `scripts/md2html.py`，因此 **Claude Code、Codex、ZCode 三端行为完全一致**——agent 只负责收集输入、读图转写、组织 markdown，排版一律交给脚本。三平台如何装配与寻路由 [PROTOCOL.md](PROTOCOL.md) 契约约束。

## 项目结构

```
doc2html-skill/
├── SKILL.md                        # 技能定义（三端原生 skill 共用，逐字相同）
├── PROTOCOL.md                     # 三平台适配契约：目录映射、路径规则、发现顺序、CLI 稳定接口
├── AGENTS.md                       # 本文件：任意 agent 进入本仓库时的说明
├── install.sh                      # 一键安装三平台；--uninstall 卸载
├── scripts/
│   ├── md2html.py                  # 核心转换器（依赖自举到 scripts/_vendor）
│   ├── update_codex_agents.py      # 维护 Codex 托管入口，保留其他用户规则
│   └── _vendor/                    # 首次运行自动生成的 Python 依赖
├── codex/
│   └── doc-to-html.prompt.md       # Codex prompt 源（安装时复制到 ~/.codex/prompts/）
├── references/
│   └── style-guide.md              # 产物样式规范与手绘图表指引
└── samples/
    ├── sample.md / demo.png / sample.html
```

## 安装与卸载

```bash
bash install.sh             # 在项目根目录执行，三平台全装
bash install.sh --uninstall # 卸载（源项目保留）
```

安装副本位置（契约，见 PROTOCOL.md §1）：

| 平台 | 指令文件 | 脚本 |
| --- | --- | --- |
| Claude Code | `~/.claude/skills/doc-to-html/SKILL.md` | 同目录 `scripts/` |
| ZCode | `~/.zcode/skills/doc-to-html/SKILL.md` | 同目录 `scripts/` |
| Codex 原生 skill | `~/.codex/skills/doc-to-html/SKILL.md` | 同目录 `scripts/` |
| Codex 兼容 prompt | `~/.codex/prompts/doc-to-html.md` | 同级 `doc-to-html/scripts/` |

显式调用：Codex 使用 `$doc-to-html`（或 `/skills` 中选择），Claude Code 使用 `/doc-to-html`；支持自定义 prompt 的 Codex CLI 可继续使用 `/prompts:doc-to-html`。在 IDEA 中从业务项目目录启动 agent，指定 `docs/需求.md`，默认生成 `docs/需求.html`。完整示例见 [README.md](README.md)。

## 硬规则：零机器绝对路径

**任何安装到平台目录的文件，禁止写入机器特定绝对路径**（PROTOCOL.md §2）。路径只允许两种写法：相对本文件定位，或 `~` 开头的用户级路径。agent 运行时按 PROTOCOL.md §3 的发现顺序定位脚本。修改 skill 内容时请遵守该规则并同步三端，再重跑 `install.sh`。

## 直接用命令行（不经过任何 agent）

```bash
python3 scripts/md2html.py 方案.md -o 方案.html --title "标题" --subtitle "2026-09 版本"
python3 scripts/md2html.py a.md b.md -o 合并.html          # 多文件按序合并
python3 scripts/md2html.py 方案.md --accent "#0e7a4e"       # 换主题色
python3 scripts/md2html.py --cleanup assembled.md extracts/ # 清理中间产物，交付只留最终 HTML
```

CLI 参数是稳定契约（PROTOCOL.md §4），只能向后兼容地新增。

## 输入类型处理约定

| 输入 | 处理方式 |
| --- | --- |
| Markdown | 直接转换；文档头部长元信息 blockquote 自动折叠 |
| 方案截图（含文字） | agent 用视觉转写文字/表格为 markdown 片段，原图 base64 内嵌 + 转写并列呈现 |
| docx | `pandoc -t gfm` 提取为 md（无 pandoc 时由 agent 用库提取）后转换 |
| pdf | `pdftotext -layout` 提取、人工整理后转换 |

## 维护说明

- 修改排版风格：编辑 `scripts/md2html.py` 内嵌的 `CSS` 模板（占位符 `__ACCENT__` 为主题色）。
- 修改 skill 内容：同步改 `SKILL.md` 与 `codex/doc-to-html.prompt.md`（语义一致），然后重跑 `install.sh`（先清理旧安装副本再部署新版，无残留）。
- 协议变更：更新 `PROTOCOL.md` 版本号，并检查 `install.sh` 与两份指令文件的一致性。
