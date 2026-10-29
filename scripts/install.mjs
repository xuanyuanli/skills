#!/usr/bin/env node
/**
 * Install the skills in this repository into the native directory of any
 * mainstream agent, or into a directory you choose.
 *
 *   node scripts/install.mjs --list
 *   node scripts/install.mjs --tool all
 *   node scripts/install.mjs --tool claude --scope global
 *   node scripts/install.mjs --tool cursor --dest ../my-project
 *   node scripts/install.mjs --tool codex --skill product-council
 *   node scripts/install.mjs --tool generic --out .windsurf/skills
 *   node scripts/install.mjs --tool all --uninstall
 *
 * Native locations (verified against vendor docs, 2026-10):
 *   claude   .claude/skills      ~/.claude/skills
 *   codex    .agents/skills      ~/.agents/skills
 *   copilot  .github/skills      ~/.copilot/skills
 *   cursor   .cursor/skills      ~/.cursor/skills
 *
 * Cursor also discovers .agents/skills and .claude/skills, which is why
 * `--tool all` installs claude + codex + copilot and leaves Cursor covered.
 */

import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SKILLS_ROOT = path.join(ROOT, "skills");

const TOOLS = {
  claude: { dir: ".claude/skills", label: "Claude Code" },
  codex: { dir: ".agents/skills", label: "Codex CLI" },
  copilot: { dir: ".github/skills", label: "GitHub Copilot / VS Code" },
  cursor: { dir: ".cursor/skills", label: "Cursor" },
  generic: { dir: null, label: "Custom (requires --out)" },
};

const ALL_TOOLS = ["claude", "codex", "copilot"];

function usage() {
  return `Usage: node scripts/install.mjs [options]

Options:
  --list                Show available skills and exit
  --tool <names>        Comma-separated: ${Object.keys(TOOLS).join(", ")}, or "all"
                        (default: all = claude, codex, copilot; Cursor reads .agents/skills)
  --skill <names>       Comma-separated skill names (default: every skill)
  --scope <project|global>
                        project = current directory (default), global = home directory
  --dest <dir>          Project root to install into instead of the current directory
  --out <relative-dir>  Override the tool's directory, e.g. --out .windsurf/skills
  --link                Symlink instead of copy (handy while editing skills)
  --force               Replace existing skill directories
  --uninstall           Remove the selected skills from the selected tools
  --with-agents-md      Write an AGENTS.md index block for tools without native skills
  --dry-run             Print what would happen, change nothing
  --json                Machine-readable summary
  -h, --help            Show this help

Examples:
  node scripts/install.mjs --list
  node scripts/install.mjs --tool all
  node scripts/install.mjs --tool codex --scope global
  node scripts/install.mjs --tool generic --out .windsurf/skills --dest ../app
  node scripts/install.mjs --tool all --uninstall
`;
}

function parseArgs(argv) {
  const opts = {
    tool: "all",
    skill: null,
    scope: "project",
    dest: null,
    out: null,
    link: false,
    force: false,
    uninstall: false,
    agentsMd: false,
    dryRun: false,
    json: false,
    list: false,
    help: false,
  };
  const takesValue = new Set(["tool", "skill", "scope", "dest", "out"]);
  const aliases = {
    "with-agents-md": "agentsMd",
    "dry-run": "dryRun",
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (!arg.startsWith("-")) throw new Error(`unexpected argument: ${arg}`);

    let key = arg.replace(/^--?/, "");
    let value;
    if (key.includes("=")) {
      [key, value] = [key.slice(0, key.indexOf("=")), key.slice(key.indexOf("=") + 1)];
    }
    if (key === "h" || key === "help") {
      opts.help = true;
      continue;
    }
    if (key === "list" || key === "link" || key === "force" || key === "uninstall" || key === "json" || key in aliases) {
      opts[aliases[key] ?? key] = true;
      continue;
    }
    if (!takesValue.has(key)) throw new Error(`unknown option: ${arg}`);
    if (value === undefined) {
      value = argv[++i];
      if (value === undefined) throw new Error(`missing value for --${key}`);
    }
    opts[key] = value;
  }
  return opts;
}

function parseFrontmatter(text) {
  const normalized = text.replace(/\r\n/g, "\n");
  if (!normalized.startsWith("---\n")) return {};
  const end = normalized.indexOf("\n---", 3);
  if (end === -1) return {};
  const block = normalized.slice(4, end);
  const meta = {};
  for (const line of block.split("\n")) {
    const match = /^([A-Za-z0-9_-]+):\s*(.*)$/.exec(line);
    if (!match) continue;
    let value = match[2].trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    meta[match[1]] = value;
  }
  return meta;
}

async function discoverSkills() {
  const entries = await fs.readdir(SKILLS_ROOT, { withFileTypes: true });
  const skills = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const dir = path.join(SKILLS_ROOT, entry.name);
    const skillFile = path.join(dir, "SKILL.md");
    let text;
    try {
      text = await fs.readFile(skillFile, "utf8");
    } catch {
      continue;
    }
    const meta = parseFrontmatter(text);
    skills.push({
      dir,
      name: meta.name || entry.name,
      description: meta.description || "",
    });
  }
  return skills.sort((a, b) => a.name.localeCompare(b.name));
}

async function exists(target) {
  try {
    await fs.lstat(target);
    return true;
  } catch {
    return false;
  }
}

async function installOne(skill, targetDir, opts) {
  const destination = path.join(targetDir, skill.name);
  const present = await exists(destination);

  if (opts.uninstall) {
    if (!present) return { status: "absent", destination };
    const marker = path.join(destination, "SKILL.md");
    if (!(await exists(marker))) {
      return { status: "refused", destination, reason: "no SKILL.md; not removing" };
    }
    const meta = parseFrontmatter(await fs.readFile(marker, "utf8"));
    if ((meta.name || path.basename(destination)) !== skill.name) {
      return { status: "refused", destination, reason: "name mismatch; not removing" };
    }
    if (!opts.dryRun) await fs.rm(destination, { recursive: true, force: true });
    return { status: "removed", destination };
  }

  if (present && !opts.force) {
    return { status: "skipped", destination, reason: "exists (use --force)" };
  }

  if (!opts.dryRun) {
    await fs.mkdir(targetDir, { recursive: true });
    if (present) await fs.rm(destination, { recursive: true, force: true });
    if (opts.link) {
      const type = process.platform === "win32" ? "junction" : "dir";
      await fs.symlink(skill.dir, destination, type);
    } else {
      await fs.cp(skill.dir, destination, { recursive: true });
    }
  }
  return { status: opts.link ? "linked" : "copied", destination };
}

async function writeAgentsIndex(baseDir, installed, opts) {
  const file = path.join(baseDir, "AGENTS.md");  const begin = "<!-- skills:begin (generated by skills installer) -->";
  const end = "<!-- skills:end -->";
  const lines = [
    begin,
    "## Skills",
    "",
    "Load the matching skill when a request falls into its scope. Each entry points at the full `SKILL.md`.",
    "",
    ...installed.map((item) => {
      const rel = path.relative(baseDir, path.join(item.destination, "SKILL.md")).split(path.sep).join("/");
      const description = item.description.length > 160 ? `${item.description.slice(0, 157)}...` : item.description;
      return `- **[${item.skill}](${rel})** — ${description}`;
    }),
    end,
  ];
  const block = lines.join("\n");

  let current = "";
  try {
    current = await fs.readFile(file, "utf8");
  } catch {
    current = "";
  }

  const pattern = /<!-- skills:begin[^>]*-->[\s\S]*?<!-- skills:end -->/;
  const next = pattern.test(current)
    ? current.replace(pattern, block)
    : `${current}${current && !current.endsWith("\n") ? "\n" : ""}${current ? "\n" : ""}${block}\n`;

  if (!opts.dryRun) {
    await fs.writeFile(file, next, "utf8");
  }
  return file;
}

async function main() {
  let opts;
  try {
    opts = parseArgs(process.argv.slice(2));
  } catch (error) {
    console.error(`error: ${error.message}\n`);
    console.error(usage());
    return 2;
  }

  if (opts.help) {
    console.log(usage());
    return 0;
  }

  const skills = await discoverSkills();
  if (skills.length === 0) {
    console.error("error: no skills found under skills/");
    return 2;
  }

  if (opts.list) {
    if (opts.json) {
      console.log(JSON.stringify(skills.map(({ name, description }) => ({ name, description })), null, 2));
      return 0;
    }
    for (const skill of skills) {
      console.log(`${skill.name}\n  ${skill.description}\n  ${path.relative(process.cwd(), skill.dir)}`);
    }
    return 0;
  }

  if (!["project", "global"].includes(opts.scope)) {
    console.error("error: --scope must be project or global");
    return 2;
  }
  if (opts.scope === "global" && opts.dest) {
    console.error("error: --dest cannot be combined with --scope global");
    return 2;
  }
  if (opts.link && opts.uninstall) {
    console.error("error: --link and --uninstall are mutually exclusive");
    return 2;
  }

  const toolNames = opts.tool === "all" ? ALL_TOOLS : opts.tool.split(",").map((s) => s.trim());
  for (const tool of toolNames) {
    if (!(tool in TOOLS)) {
      console.error(`error: unknown tool "${tool}" (expected ${Object.keys(TOOLS).join(", ")})`);
      return 2;
    }
  }
  if (opts.out && toolNames.length !== 1) {
    console.error("error: --out requires exactly one --tool");
    return 2;
  }

  const baseDir = opts.scope === "global" ? os.homedir() : path.resolve(opts.dest || process.cwd());
  const selected = opts.skill
    ? opts.skill.split(",").map((s) => s.trim())
    : skills.map((s) => s.name);
  const unknown = selected.filter((name) => !skills.some((skill) => skill.name === name));
  if (unknown.length) {
    console.error(`error: unknown skill(s): ${unknown.join(", ")}`);
    return 2;
  }
  const chosen = skills.filter((skill) => selected.includes(skill.name));

  const results = [];
  for (const tool of toolNames) {
    const relative = opts.out || TOOLS[tool].dir;
    if (!relative) {
      console.error('error: --tool generic needs --out, e.g. --out .windsurf/skills');
      return 2;
    }
    if (path.isAbsolute(relative)) {
      console.error("error: --out must be relative to the destination root");
      return 2;
    }
    const targetDir = path.join(baseDir, relative);
    for (const skill of chosen) {
      const result = await installOne(skill, targetDir, opts);
      results.push({ ...result, tool, skill: skill.name, description: skill.description });
    }
  }

  const counts = results.reduce((acc, item) => {
    acc[item.status] = (acc[item.status] || 0) + 1;
    return acc;
  }, {});

  let agentsFile = null;
  if (opts.agentsMd && !opts.uninstall) {
    const installed = results.filter((item) =>
      ["copied", "linked", "skipped"].includes(item.status)
    );
    if (installed.length) {
      const unique = installed.filter(
        (item, index, list) => list.findIndex((other) => other.skill === item.skill) === index
      );
      agentsFile = await writeAgentsIndex(baseDir, unique, opts);
    }
  }

  if (opts.json) {
    console.log(
      JSON.stringify(
        {
          baseDir,
          dryRun: opts.dryRun,
          counts,
          results: results.map(({ status, tool, skill, destination, reason }) => ({
            status,
            tool,
            skill,
            destination,
            ...(reason ? { reason } : {}),
          })),
          agentsFile,
        },
        null,
        2
      )
    );
  } else {
    if (opts.dryRun) console.log("(dry run — nothing was written)\n");
    for (const item of results) {
      const rel = path.relative(baseDir, item.destination) || item.destination;
      const extra = item.reason ? ` — ${item.reason}` : "";
      console.log(`[${item.status.padEnd(7)}] ${item.tool.padEnd(7)} ${rel}${extra}`);
    }
    console.log("");
    console.log(
      Object.entries(counts)
        .map(([status, count]) => `${count} ${status}`)
        .join(", ")
    );
    if (agentsFile) console.log(`AGENTS.md index: ${path.relative(baseDir, agentsFile)}`);
  }

  return results.some((item) => item.status === "refused") ? 1 : 0;
}

main()
  .then((code) => {
    process.exitCode = code;
  })
  .catch((error) => {
    console.error(`error: ${error.message}`);
    process.exitCode = 1;
  });
