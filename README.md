# skills

Portable [Agent Skills](https://agentskills.io) for product decisions, deep reading, document conversion and Obsidian notes.

[![validate](https://github.com/xuanyuanli/skills/actions/workflows/validate.yml/badge.svg)](https://github.com/xuanyuanli/skills/actions/workflows/validate.yml)

One folder per skill, plain `SKILL.md` plus optional `scripts/` and `references/`. No framework, no dependencies, no lock-in — the same files work in Claude Code, Codex, GitHub Copilot, Cursor, and anything else that reads the open Agent Skills format.

[中文说明](README.zh-CN.md)

## Skills

| Skill | What it does | Triggers on |
|---|---|---|
| [product-council](skills/product-council/SKILL.md) | Reviews one product decision through four independent mental models (Yu Jun, Zhang Xiaolong, Steve Jobs, Pony Ma), then converges on consensus, dissent, and an actionable decision | 产品评审, 这个功能该不该做, 产品决策拆解 |
| [wan-weigang-reading](skills/wan-weigang-reading/SKILL.md) | Reads a book or concept in Wan Weigang's style: one-sentence thesis, argument chains, mental models, counter-intuitive points, boundaries | 精读, 万维钢风格, 强力研读, 展开注释 |
| [pdf-to-markdown](skills/pdf-to-markdown/SKILL.md) | Converts PDF/EPUB/DOCX to clean Markdown, with scanned-page OCR, speed probing, resumable full-book runs and post-OCR cleanup | 把 PDF 转成 md, 扫描件 OCR, 原书转 Markdown |
| [obsidian-reading-notes](skills/obsidian-reading-notes/SKILL.md) | Formats and merges Obsidian reading notes: heading levels, separators, bold, attachments, merge candidates — plus a linter | 整理读书笔记, 合并笔记, 检查笔记格式 |

The Chinese skills are optimized versions of a personal Cursor setup; `obsidian-reading-notes` began life as an always-on Cursor rule (`reading-notes.mdc`) and `pdf-to-markdown` as a glob-triggered rule, both converted to on-demand skills.

## Install

Requires Node.js 18+ (only for the installer; the skills themselves are just files).

```bash
git clone https://github.com/xuanyuanli/skills.git
cd skills

node scripts/install.mjs --list                 # what is available
node scripts/install.mjs --tool all             # into this project
node scripts/install.mjs --tool all --scope global   # into your home directory
```

`--tool all` installs `claude`, `codex` and `copilot` layouts. That is enough for four tools, because Cursor also discovers `.agents/skills/`.

Install into another project or a single tool:

```bash
node scripts/install.mjs --tool cursor --dest ../my-app
node scripts/install.mjs --tool copilot --skill pdf-to-markdown
node scripts/install.mjs --tool claude --scope global --force
node scripts/install.mjs --tool codex --link          # symlink while editing
```

Preview, update, remove:

```bash
node scripts/install.mjs --tool all --dry-run
node scripts/install.mjs --tool all --force          # overwrite existing copies
node scripts/install.mjs --tool all --uninstall      # only removes dirs with a valid SKILL.md
```

Tools without native skill discovery can get an `AGENTS.md` index instead:

```bash
node scripts/install.mjs --tool all --with-agents-md
node scripts/install.mjs --tool generic --out .windsurf/skills --dest ../my-app
```

## Where each tool looks

| Tool | Project | Personal |
|---|---|---|
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| OpenAI Codex | `.agents/skills/` | `~/.agents/skills/` |
| GitHub Copilot (VS Code, CLI) | `.github/skills/` | `~/.copilot/skills/` |
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` |

Cursor additionally reads `.agents/skills/` and `.claude/skills/`. VS Code's local agent reads `.github/skills/`, `.claude/skills/` and `.agents/skills/`.

Invoke a skill with `/skill-name` (Claude Code, Cursor, Copilot) or let the agent pick it from the `description`. `wan-weigang-reading` ships with `disable-model-invocation: true`, so it only runs when you invoke it explicitly — remove that line if you want automatic triggering.

## Manual install

Copy the skill folder, not just the file:

```bash
cp -r skills/product-council ~/.claude/skills/
```

The directory name must match the `name` field. Supporting files (`scripts/`, `references/`) are referenced relatively, so keep the folder intact.

## Updates

```bash
git pull
node scripts/install.mjs --tool all --force
```

`--force` replaces installed copies. Without it, existing directories are skipped so local edits are never silently overwritten.

## Repository layout

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
│   ├── install.mjs     # cross-tool installer
│   └── validate.mjs    # spec + link + frontmatter checks
└── .github/workflows/validate.yml
```

## Validate

```bash
node scripts/validate.mjs
```

Checks that every `SKILL.md` has valid frontmatter, a `name` matching its directory, a description within 1024 characters, working relative links, LF line endings, and no unknown frontmatter keys. CI runs the same command on every push.

## Notes

- Descriptions and bodies are in Chinese; the format is English-compatible.
- Skills load on demand. If a former `alwaysApply` rule must stay always-on, keep a one-line rule pointing at the skill, or copy its key points into `AGENTS.md` / `.github/copilot-instructions.md`.
- Skills are instructions, not code you run blindly. `pdf-to-markdown` calls a Python OCR package and `obsidian-reading-notes` can rewrite Markdown with `--fix`; review before using on important files.
- `--uninstall` refuses to delete anything that does not contain a matching `SKILL.md`.
- MIT licensed.

## License

[MIT](LICENSE)
