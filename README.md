# skills

**中文** | [English](README.en.md)

可移植的 [Agent Skills](https://agentskills.io)：产品决策、深度阅读、文档转换、Obsidian 笔记。

一个目录一个技能，核心是 `SKILL.md`，可选 `scripts/` 与 `references/`。无框架、无依赖、不绑定平台，Claude Code、Codex、GitHub Copilot、Cursor 通用。

## 技能

| 技能 | 作用 |
|---|---|
| [product-council](skills/product-council/SKILL.md) | 用四套心智模型独立评审产品决策，收敛出共识、分歧与可执行结论 |
| [wan-weigang-reading](skills/wan-weigang-reading/SKILL.md) | 万维钢式精读：一句话总纲、论证拆解、心智模型、边界 |
| [pdf-to-markdown](skills/pdf-to-markdown/SKILL.md) | PDF/EPUB/DOCX 转 Markdown，扫描件 OCR、测速、断点续跑 |
| [obsidian-reading-notes](skills/obsidian-reading-notes/SKILL.md) | Obsidian 读书笔记规范、合并与格式检查 |

## 安装

需要 Node.js 18+（仅安装器需要，技能本身只是文件）。

```bash
git clone https://github.com/xuanyuanli/skills.git
cd skills

node scripts/install.mjs --list                      # 查看技能
node scripts/install.mjs --tool all                  # 安装到当前项目
node scripts/install.mjs --tool all --scope global   # 安装到用户目录
```

`--tool all` 安装 `claude`、`codex`、`copilot` 三套目录，已覆盖四个工具（Cursor 也读 `.agents/skills/`）。

单工具、指定项目、升级与卸载：

```bash
node scripts/install.mjs --tool cursor --dest ../my-app
node scripts/install.mjs --tool copilot --skill pdf-to-markdown
node scripts/install.mjs --tool all --force          # 覆盖已有副本
node scripts/install.mjs --tool all --uninstall      # 只删含合法 SKILL.md 的目录
```

不支持原生 skills 的工具：用 `--with-agents-md` 生成 `AGENTS.md` 索引，或 `--tool generic --out <dir>` 指定目录。

## 工具目录

| 工具 | 项目级 | 用户级 |
|---|---|---|
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| OpenAI Codex | `.agents/skills/` | `~/.agents/skills/` |
| GitHub Copilot | `.github/skills/` | `~/.copilot/skills/` |
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` |

调用：输入 `/技能名`，或让 agent 根据 `description` 自动选择。

## 校验

```bash
node scripts/validate.mjs
```

检查 frontmatter、命名、描述长度、相对链接与换行；CI 每次 push 自动运行。

## 说明

- 技能正文为中文，格式与英文环境兼容。
- 规则转技能后按需加载；需要常驻时保留一条指向技能的短规则即可。
- `pdf-to-markdown` 会调用 Python OCR 包；`obsidian-reading-notes --fix` 会改写 Markdown，重要文件先备份。
- MIT 协议。

## 多语言

默认中文（`README.md`），英文见 [`README.en.md`](README.en.md)。新增语言：添加 `README.<lang>.md`，并在顶部语言栏登记。
