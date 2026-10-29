# skills

[中文](README.md) | **English**

Portable [Agent Skills](https://agentskills.io) for product decisions, deep reading, document conversion, Obsidian notes and git weekly reports.

One folder per skill: a `SKILL.md` plus optional `scripts/` and `references/`. No framework, no dependencies, no lock-in — works in Claude Code, Codex, GitHub Copilot and Cursor.

## Skills

| Skill | What it does |
|---|---|
| [product-council](skills/product-council/SKILL.md) | Reviews a product decision through four independent mental models, then converges on consensus, dissent and a decision |
| [wan-weigang-reading](skills/wan-weigang-reading/SKILL.md) | Deep reading in Wan Weigang's style: thesis, argument chains, mental models, boundaries |
| [pdf-to-markdown](skills/pdf-to-markdown/SKILL.md) | PDF/EPUB/DOCX to Markdown, with scanned-page OCR, speed probing and resumable runs |
| [obsidian-reading-notes](skills/obsidian-reading-notes/SKILL.md) | Obsidian reading-note conventions, merging and format checks |
| [weekly-report](skills/weekly-report/SKILL.md) | Value-ordered git weekly report: last Saturday to now, features first, bugs last |

## Install

Node.js 18+ is required for the installer only; the skills themselves are just files.

```bash
git clone https://github.com/xuanyuanli/skills.git
cd skills

node scripts/install.mjs --list                      # show skills
node scripts/install.mjs --tool all                  # install into this project
node scripts/install.mjs --tool all --scope global   # install into your home directory
```

`--tool all` installs the `claude`, `codex` and `copilot` layouts, which covers four tools (Cursor also reads `.agents/skills/`).

Single tool, another project, update and removal:

```bash
node scripts/install.mjs --tool cursor --dest ../my-app
node scripts/install.mjs --tool copilot --skill pdf-to-markdown
node scripts/install.mjs --tool all --force          # overwrite existing copies
node scripts/install.mjs --tool all --uninstall      # only dirs with a valid SKILL.md
```

For tools without native skill discovery, use `--with-agents-md` to generate an `AGENTS.md` index, or `--tool generic --out <dir>`.

## Where tools look

| Tool | Project | Personal |
|---|---|---|
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| OpenAI Codex | `.agents/skills/` | `~/.agents/skills/` |
| GitHub Copilot | `.github/skills/` | `~/.copilot/skills/` |
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` |

Invoke with `/skill-name`, or let the agent pick it from the `description`.

## Validate

```bash
node scripts/validate.mjs
```

Checks frontmatter, naming, description length, relative links and line endings. CI runs it on every push.

## Notes

- Bodies are in Chinese; the format is fully English-compatible.
- Skills load on demand. If a former always-on rule must stay active, keep a one-line rule pointing at the skill.
- `pdf-to-markdown` calls a Python OCR package; `obsidian-reading-notes --fix` rewrites Markdown — back up important files.
- MIT.

## Languages

Chinese is the default and lives in `README.md`. Add `README.<lang>.md` and register it in the language bar at the top.
