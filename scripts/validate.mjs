#!/usr/bin/env node
/**
 * Validate every SKILL.md against the Agent Skills specification and this
 * repository's conventions. Runs in CI and can be used as a pre-commit check.
 *
 *   node scripts/validate.mjs
 *   node scripts/validate.mjs --json
 */

import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SKILLS_ROOT = path.join(ROOT, "skills");

const NAME_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const KNOWN_KEYS = new Set([
  "name",
  "description",
  "license",
  "metadata",
  "allowed-tools",
  "compatibility",
  // widely supported tool-specific keys
  "disable-model-invocation",
  "user-invocable",
  "argument-hint",
  "context",
  "agent",
  "model",
  "paths",
  "version",
]);
const MAX_DESCRIPTION = 1024;
const MAX_NAME = 64;
const MAX_BODY_LINES = 500;

function parseFrontmatter(text) {
  const normalized = text.replace(/\r\n/g, "\n");
  const match = /^---\n([\s\S]*?)\n---(?:\n|$)/.exec(normalized);
  if (!match) return null;
  const meta = {};
  for (const line of match[1].split("\n")) {
    const entry = /^([A-Za-z0-9_-]+):\s*(.*)$/.exec(line);
    if (!entry) continue;
    let value = entry[2].trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    meta[entry[1]] = value;
  }
  return { meta, body: normalized.slice(match[0].length), raw: match[1] };
}

function stripCode(text) {
  return text.replace(/```[\s\S]*?```/g, "").replace(/`[^`\n]*`/g, "");
}

function extractLinks(body) {
  const links = [];
  const pattern = /\]\(([^)\s]+)(?:\s+["'][^"']*["'])?\)/g;
  let match;
  while ((match = pattern.exec(body)) !== null) links.push(match[1]);
  return links;
}

async function fileExists(target) {
  try {
    await fs.access(target);
    return true;
  } catch {
    return false;
  }
}

function issue(level, code, message, line) {
  return { level, code, message, ...(line ? { line } : {}) };
}

async function validateSkill(entry) {
  const dir = path.join(SKILLS_ROOT, entry.name);
  const file = path.join(dir, "SKILL.md");
  const problems = [];

  let text;
  try {
    text = await fs.readFile(file, "utf8");
  } catch {
    return {
      name: entry.name,
      ok: false,
      problems: [issue("error", "missing-skill", "SKILL.md is missing")],
    };
  }

  if (text.startsWith("\uFEFF")) {
    problems.push(issue("error", "bom", "file starts with a UTF-8 BOM"));
  }
  if (text.includes("\r\n")) {
    problems.push(issue("error", "crlf", "CRLF line endings; repository uses LF"));
  }

  const parsed = parseFrontmatter(text);
  if (!parsed) {
    return {
      name: entry.name,
      ok: false,
      problems: [...problems, issue("error", "no-frontmatter", "missing YAML frontmatter")],
    };
  }

  const { meta, body } = parsed;

  for (const key of Object.keys(meta)) {
    if (!KNOWN_KEYS.has(key)) {
      problems.push(issue("warning", "unknown-key", `unknown frontmatter key: ${key}`));
    }
  }

  if (!meta.name) {
    problems.push(issue("error", "no-name", "frontmatter is missing `name`"));
  } else {
    if (meta.name !== entry.name) {
      problems.push(
        issue("error", "name-mismatch", `name "${meta.name}" must match directory "${entry.name}"`)
      );
    }
    if (!NAME_RE.test(meta.name)) {
      problems.push(issue("error", "name-format", "name must be lowercase letters, digits and hyphens"));
    }
    if (meta.name.length > MAX_NAME) {
      problems.push(issue("error", "name-length", `name exceeds ${MAX_NAME} characters`));
    }
  }

  if (!meta.description) {
    problems.push(issue("error", "no-description", "frontmatter is missing `description`"));
  } else {
    if (meta.description.length > MAX_DESCRIPTION) {
      problems.push(
        issue("error", "description-length", `description is ${meta.description.length} chars (max ${MAX_DESCRIPTION})`)
      );
    }
    if (meta.description.includes("\n")) {
      problems.push(issue("error", "description-multiline", "description must be a single line"));
    }
    if (!/使用|use when|Use when|use this|when the user/i.test(meta.description)) {
      problems.push(
        issue("warning", "description-trigger", "description does not say when to use the skill")
      );
    }
  }

  if (!meta.license) {
    problems.push(issue("warning", "no-license", "no `license` field"));
  }

  const bodyLines = body.split("\n").length;
  if (bodyLines > MAX_BODY_LINES) {
    problems.push(
      issue("warning", "body-length", `body is ${bodyLines} lines (recommended max ${MAX_BODY_LINES})`)
    );
  }
  if (text.includes("\t")) {
    problems.push(issue("warning", "tab", "file contains tab characters"));
  }

  const linkBody = stripCode(body);
  for (const link of extractLinks(linkBody)) {
    if (/^(https?:|mailto:|#|<)/.test(link) || link.startsWith("/")) continue;
    const clean = link.split("#")[0];
    if (!clean) continue;
    const target = path.resolve(dir, clean);
    if (!(await fileExists(target))) {
      problems.push(issue("error", "broken-link", `link target not found: ${link}`));
    }
  }

  if (/^#{1,6}\s/m.test(body) && !/^##\s/m.test(body)) {
    problems.push(issue("warning", "single-level", "body has only one heading level; check structure"));
  }

  const hasScripts = await fileExists(path.join(dir, "scripts"));
  if (hasScripts && !/scripts\//.test(body)) {
    problems.push(issue("warning", "unreferenced-scripts", "scripts/ exists but SKILL.md never references it"));
  }

  const errors = problems.filter((p) => p.level === "error").length;
  return {
    name: entry.name,
    ok: errors === 0,
    lines: bodyLines,
    descriptionLength: (meta.description || "").length,
    meta,
    problems,
  };
}

async function main() {
  const json = process.argv.includes("--json");

  let entries;
  try {
    entries = (await fs.readdir(SKILLS_ROOT, { withFileTypes: true })).filter((e) => e.isDirectory());
  } catch {
    console.error(`error: ${SKILLS_ROOT} does not exist`);
    return 2;
  }
  entries.sort((a, b) => a.name.localeCompare(b.name));

  const results = [];
  for (const entry of entries) {
    results.push(await validateSkill(entry));
  }

  const errorCount = results.reduce(
    (sum, result) => sum + result.problems.filter((p) => p.level === "error").length,
    0
  );
  const warningCount = results.reduce(
    (sum, result) => sum + result.problems.filter((p) => p.level === "warning").length,
    0
  );

  if (json) {
    console.log(JSON.stringify({ skills: results, errors: errorCount, warnings: warningCount }, null, 2));
    return errorCount ? 1 : 0;
  }

  for (const result of results) {
    const status = result.ok ? "ok" : "FAIL";
    const detail = result.lines ? `${result.lines} body lines, ${result.descriptionLength} char description` : "";
    console.log(`${status.padEnd(4)}  ${result.name}${detail ? `  (${detail})` : ""}`);
    for (const problem of result.problems) {
      console.log(`      ${problem.level}: ${problem.message}`);
    }
  }

  console.log("");
  console.log(`${results.length} skill(s): ${errorCount} error(s), ${warningCount} warning(s)`);
  return errorCount ? 1 : 0;
}

main()
  .then((code) => {
    process.exitCode = code;
  })
  .catch((error) => {
    console.error(`error: ${error.message}`);
    process.exitCode = 1;
  });
