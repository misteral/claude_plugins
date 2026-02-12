---
name: skill-creator
description: Create new Claude Code skills and plugins. Use when asked to create, scaffold, or add a new skill or plugin. Handles full setup including SKILL.md, plugin.json, and marketplace registration.
argument-hint: <skill-name> [in <plugin-name>]
---

# Skill Creator

Creates new skills following the [Agent Skills](https://agentskills.io/specification) open standard and this project's conventions.

## Usage

- `/skill-creator my-skill` — create a new skill in a new plugin
- `/skill-creator my-skill in developer-plugin` — add skill to existing plugin

## Workflow

### Step 1: Parse Arguments

Extract from `$ARGUMENTS`:
- **skill-name** — required, the name of the skill to create
- **plugin-name** — optional, existing plugin to add the skill to

If no plugin specified, ask the user whether to:
1. Create a new `<skill-name>-plugin`
2. Add to an existing plugin (list available ones)

### Step 2: Gather Requirements

Ask the user:
1. **What does the skill do?** — for the `description` field
2. **Does it need special tools?** — for `allowed-tools` (e.g., `Bash(git:*)`)
3. **Does it need reference files?** — for `references/` directory
4. **Does it need scripts?** — for `scripts/` directory

### Step 3: Validate Skill Name

The name MUST follow these rules (from agentskills.io spec):
- Max 64 characters
- Only lowercase letters, numbers, and hyphens (`a-z`, `0-9`, `-`)
- Must NOT start or end with `-`
- Must NOT contain consecutive hyphens (`--`)
- Must match the parent directory name

### Step 4: Create Directory Structure

```
plugins/<plugin-name>/
├── .claude-plugin/
│   └── plugin.json              # create if new plugin
└── skills/
    └── <skill-name>/
        ├── SKILL.md             # always created
        ├── references/          # if needed
        └── scripts/             # if needed
```

### Step 5: Write SKILL.md

Use this template:

```yaml
---
name: <skill-name>
description: <1-2 sentences, max 1024 chars. Describe WHAT it does AND WHEN to use it. Include keywords for auto-detection.>
allowed-tools: <space-delimited list, only if needed>
argument-hint: <usage hint, only if needed>
metadata:
  author: aleksandrbobrov
  version: "1.0"
compatibility: <only if specific requirements exist>
---
```

Body content guidelines:
- Keep under 500 lines — move details to `references/`
- Include: step-by-step instructions, examples, edge cases
- Use progressive disclosure: metadata (~100 tokens) → instructions (<5000 tokens) → resources (on demand)

### Step 6: Create plugin.json (if new plugin)

Write `.claude-plugin/plugin.json`:

```json
{
  "name": "<plugin-name>",
  "description": "<plugin description>",
  "version": "1.0.0",
  "author": {
    "name": "Aleksandr Bobrov"
  },
  "keywords": ["<relevant>", "<keywords>"]
}
```

### Step 7: Register in Marketplace (if new plugin)

Add entry to `.claude-plugin/marketplace.json` at the repository root:

```json
{
  "name": "<plugin-name>",
  "source": "./plugins/<plugin-name>",
  "description": "<plugin description>"
}
```

**This step is CRITICAL — without it the plugin will not activate!**

### Step 8: Verify

Read back the created files and confirm:
- [ ] `SKILL.md` has valid frontmatter (`name` matches directory name)
- [ ] `description` is specific and includes trigger keywords
- [ ] `.claude-plugin/plugin.json` exists
- [ ] Plugin is registered in root `marketplace.json`
- [ ] No unnecessary files created (no README.md, CHANGELOG.md, etc.)

## Description Writing Guide

Good descriptions include WHAT + WHEN:

```yaml
# Good — specific, includes trigger keywords
description: Extract text and tables from PDF files, fill PDF forms, and merge multiple PDFs. Use when working with PDF documents.

# Bad — too vague
description: Helps with PDFs.
```

## Common Mistakes to Avoid

1. Forgetting `.claude-plugin/plugin.json` — plugin won't activate
2. Forgetting marketplace registration — plugin won't be visible
3. Vague `description` — skill won't auto-trigger correctly
4. `name` doesn't match directory name — validation fails
5. SKILL.md too long — split into `references/` files
6. Creating unnecessary docs (README, CHANGELOG) inside skill directory
