# skills

可移植的 [Agent Skills](https://agentskills.io)：产品决策、深度阅读、文档转换、Obsidian 笔记。

[![validate](https://github.com/xuanyuanli/skills/actions/workflows/validate.yml/badge.svg)](https://github.com/xuanyuanli/skills/actions/workflows/validate.yml)

一个技能一个目录，核心是 `SKILL.md`，可选 `scripts/` 与 `references/`。没有框架、没有依赖、不绑定平台——同一份文件可以直接被 Claude Code、Codex、GitHub Copilot、Cursor 以及任何支持 Agent Skills 开放格式的工具读取。

[English](README.md)

## 包含哪些技能

| 技能 | 做什么 | 触发示例 |
|---|---|---|
| [product-council](skills/product-council/SKILL.md) | 用俞军、张小龙、乔布斯、马化腾四套心智模型独立评审同一个产品决策，再收敛出共识、分歧与可执行结论 | 产品评审、这个功能该不该做、产品决策拆解 |
| [wan-weigang-reading](skills/wan-weigang-reading/SKILL.md) | 以万维钢的思维方式与写作风格精读书籍：一句话总纲、论证拆解、心智模型、反直觉、边界 | 精读、万维钢风格、强力研读、展开注释 |
| [pdf-to-markdown](skills/pdf-to-markdown/SKILL.md) | PDF/EPUB/DOCX 转干净 Markdown，含扫描件 OCR、测速选型、断点续跑、转换后清理 | 把 PDF 转成 md、扫描件 OCR、原书转 Markdown |
| [obsidian-reading-notes](skills/obsidian-reading-notes/SKILL.md) | 整理与合并 Obsidian 读书笔记：标题层级、分隔符、加粗、附件、合并候选，附检查脚本 | 整理读书笔记、合并笔记、检查笔记格式 |

## 相对原始版本的改动

| 技能 | 主要优化 |
|---|---|
| product-council | 去掉与具体项目绑定的路径（`vitepress-doc/docs/`、`query_db.py`、MCP 名称），改为按优先级探测事实来源；新增「何时不用」「反模式」「可逆性判断」「轻量模式」；每个角色补充「最容易偷懒的地方」，避免四人雷同；框架细节拆到 `references/frameworks.md`，完整示例放 `references/example.md` |
| wan-weigang-reading | 新增输入契约（原文/片段/二手总结/只有概念名）与字数规格；补充事实与引用边界、常见失败模式；保留「原文 / 解释 / 建议」三层标记；示例拆到 `references/example.md`；默认仍为手动调用 |
| pdf-to-markdown | 由 glob 触发的 rule 改为按描述触发的 skill；把所有本机路径改为 `OCR_HOME` + 环境变量；脚本重写为可断点续跑、原子写进度、自动校验页数（`convert.py`），并新增 `probe.py` 做分类与测速；保留 OCR 后整理的实战经验与验收标准 |
| obsidian-reading-notes | 由 `alwaysApply` rule 改为按需 skill；规范重组为「三条不变量 + 工作顺序 + 层级表」；新增 `lint_notes.py`，可检出 frontmatter、重复 H1、跳级标题、`&nbsp;`、全局附件目录，并支持安全修复与合并候选列表 |

两个 `.mdc` rule 的内容已完整并入对应 skill（`reading-notes.mdc` → `obsidian-reading-notes`，`pdf-to-markdown.mdc` → `pdf-to-markdown`）。

## 安装

只需要 Node.js 18+（仅安装器需要，技能本身只是文件）。

```bash
git clone https://github.com/xuanyuanli/skills.git
cd skills

node scripts/install.mjs --list                      # 看看有哪些
node scripts/install.mjs --tool all                  # 装到当前项目
node scripts/install.mjs --tool all --scope global   # 装到用户目录
```

`--tool all` 会安装 `claude`、`codex`、`copilot` 三套目录。这已经覆盖四个工具——Cursor 也会读 `.agents/skills/`，不必重复安装。

装到别的项目，或只装一个工具：

```bash
node scripts/install.mjs --tool cursor --dest ../my-app
node scripts/install.mjs --tool copilot --skill pdf-to-markdown
node scripts/install.mjs --tool claude --scope global --force
node scripts/install.mjs --tool codex --link           # 编辑技能时用软链接
```

预览、升级、卸载：

```bash
node scripts/install.mjs --tool all --dry-run
node scripts/install.mjs --tool all --force            # 覆盖已有副本
node scripts/install.mjs --tool all --uninstall        # 只删含合法 SKILL.md 的目录
```

不支持原生 skills 的工具，可以生成 `AGENTS.md` 索引：

```bash
node scripts/install.mjs --tool all --with-agents-md
node scripts/install.mjs --tool generic --out .windsurf/skills --dest ../my-app
```

## 各工具读取位置

| 工具 | 项目级 | 用户级 |
|---|---|---|
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| OpenAI Codex | `.agents/skills/` | `~/.agents/skills/` |
| GitHub Copilot（VS Code、CLI） | `.github/skills/` | `~/.copilot/skills/` |
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` |

Cursor 额外读取 `.agents/skills/` 与 `.claude/skills/`；VS Code 的 local agent 读取 `.github/skills/`、`.claude/skills/`、`.agents/skills/`。

调用方式：输入 `/技能名`（Claude Code、Cursor、Copilot 均支持），或让 agent 根据 `description` 自动选择。`wan-weigang-reading` 默认带 `disable-model-invocation: true`，只能手动调用；想让它自动触发，删掉这一行。

## 手动安装

复制整个技能目录，不要只复制 `SKILL.md`：

```bash
cp -r skills/product-council ~/.claude/skills/
```

目录名必须与 `name` 字段一致。`scripts/`、`references/` 都按相对路径引用，保持目录结构完整。

## 升级

```bash
git pull
node scripts/install.mjs --tool all --force
```

`--force` 会覆盖已安装副本；不加则跳过已存在的目录，避免覆盖你的本地修改。

## 仓库结构

```
skills/
├── skills/
│   ├── product-council/
│   │   ├── SKILL.md
│   │   └── references/{frameworks,example}.md
│   ├── wan-weigang-reading/
│   │   ├── SKILL.md
│   │   └── references/example.md
│   ├── pdf-to-markdown/
│   │   ├── SKILL.md
│   │   └── scripts/{_runtime,probe,convert}.py
│   └── obsidian-reading-notes/
│       ├── SKILL.md
│       └── scripts/lint_notes.py
├── scripts/
│   ├── install.mjs     # 跨工具安装器
│   └── validate.mjs    # 规范、frontmatter 与链接检查
└── .github/workflows/validate.yml
```

## 校验

```bash
node scripts/validate.mjs
```

检查每个 `SKILL.md`：frontmatter 合法、`name` 与目录一致、`description` 不超过 1024 字符、相对链接可达、LF 换行、无未知字段。CI 每次 push 都会跑同一命令。

## 说明

- 正文为中文，格式与英文技能完全兼容。
- 规则改成技能后是**按需加载**。原来 `alwaysApply: true` 的笔记规范如果必须始终生效，保留一条极短的规则指向该技能，或把要点写进项目的 `AGENTS.md` / `.github/copilot-instructions.md`。
- 技能是给 agent 的指令，不是可以盲跑的代码。`pdf-to-markdown` 会调用 Python OCR 包；`obsidian-reading-notes --fix` 会改写 Markdown，重要文件先备份。
- `--uninstall` 只删除包含匹配 `SKILL.md` 的目录，不会误删别的文件夹。
- MIT 协议。

## License

[MIT](LICENSE)
