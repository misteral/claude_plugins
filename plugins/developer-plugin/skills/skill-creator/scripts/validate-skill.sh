#!/usr/bin/env bash
# Validate an Agent Skill directory per https://agentskills.io/specification
# Also checks Claude Code extensions and project-specific plugin integration.
# Usage: validate-skill.sh path/to/skill

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

errors=()
warnings=()

err()  { errors+=("$1"); }
warn() { warnings+=("$1"); }

# --- Args ---
SKILL_DIR="${1:-}"
if [[ -z "$SKILL_DIR" ]]; then
  echo "Usage: validate-skill.sh <path/to/skill>"
  exit 1
fi

# --- Directory checks ---
if [[ ! -e "$SKILL_DIR" ]]; then
  echo -e "${RED}FAIL${NC} Path does not exist: $SKILL_DIR"
  exit 1
fi
if [[ ! -d "$SKILL_DIR" ]]; then
  echo -e "${RED}FAIL${NC} Not a directory: $SKILL_DIR"
  exit 1
fi

SKILL_MD=""
if [[ -f "$SKILL_DIR/SKILL.md" ]]; then
  SKILL_MD="$SKILL_DIR/SKILL.md"
elif [[ -f "$SKILL_DIR/skill.md" ]]; then
  SKILL_MD="$SKILL_DIR/skill.md"
else
  echo -e "${RED}FAIL${NC} Missing required file: SKILL.md"
  exit 1
fi

# --- Parse frontmatter with awk (handles code blocks with --- safely) ---
frontmatter=$(awk 'NR==1 && /^---/{found=1; next} found && /^---/{exit} found{print}' "$SKILL_MD")

if [[ -z "$frontmatter" ]]; then
  first_line=$(head -1 "$SKILL_MD")
  if [[ "$first_line" != "---"* ]]; then
    echo -e "${RED}FAIL${NC} SKILL.md must start with YAML frontmatter (---)"
  else
    echo -e "${RED}FAIL${NC} SKILL.md frontmatter not properly closed with ---"
  fi
  exit 1
fi

# Body = everything after the second ---
body=$(awk 'NR==1 && /^---/{n++; next} /^---/ && n==1{n++; next} n>=2{print}' "$SKILL_MD")

# Helper: extract a top-level scalar YAML field, trimming whitespace
get_field() {
  local field="$1"
  local val
  val=$(echo "$frontmatter" | awk -F': ' -v key="$field" '$0 ~ "^"key":" {sub("^"key":[ ]*",""); print; exit}')
  # Strip surrounding quotes
  val="${val#\"}" ; val="${val%\"}"
  val="${val#\'}" ; val="${val%\'}"
  # Trim whitespace
  val="${val#"${val%%[![:space:]]*}"}"
  val="${val%"${val##*[![:space:]]}"}"
  echo "$val"
}

# Collect all top-level keys (lines not starting with whitespace)
all_keys=$(echo "$frontmatter" | awk -F':' '/^[a-z]/{print $1}' | sort -u)

# --- Allowed fields (agentskills.io spec + Claude Code extensions) ---
# Spec: name, description, license, metadata, compatibility, allowed-tools
# Claude Code: argument-hint, disable-model-invocation, user-invocable, model, context, agent, hooks
allowed_fields=(
  name description license metadata compatibility allowed-tools
  argument-hint disable-model-invocation user-invocable model context agent hooks
)

for key in $all_keys; do
  found=0
  for af in "${allowed_fields[@]}"; do
    if [[ "$key" == "$af" ]]; then
      found=1
      break
    fi
  done
  if (( found == 0 )); then
    err "Unexpected field in frontmatter: '$key'"
  fi
done

# --- Required fields ---
name=$(get_field "name")
description=$(get_field "description")

if [[ -z "$name" ]]; then
  err "Missing required field: name"
fi
if [[ -z "$description" ]]; then
  err "Missing required field: description"
fi

# --- Name validation ---
if [[ -n "$name" ]]; then
  name_len=${#name}

  if (( name_len > 64 )); then
    err "Skill name '$name' exceeds 64 character limit ($name_len chars)"
  fi

  if [[ "$name" != "$(printf '%s' "$name" | tr '[:upper:]' '[:lower:]')" ]]; then
    err "Skill name '$name' must be lowercase"
  fi

  if [[ "$name" == -* ]] || [[ "$name" == *- ]]; then
    err "Skill name cannot start or end with a hyphen"
  fi

  if [[ "$name" == *--* ]]; then
    err "Skill name cannot contain consecutive hyphens"
  fi

  if ! printf '%s' "$name" | grep -qE '^[a-z0-9-]+$'; then
    err "Skill name '$name' contains invalid characters. Only lowercase letters, digits, and hyphens allowed."
  fi

  # Directory name must match skill name
  dir_name=$(basename "$SKILL_DIR")
  if [[ "$dir_name" != "$name" ]]; then
    err "Directory name '$dir_name' must match skill name '$name'"
  fi
fi

# --- Description validation ---
if [[ -n "$description" ]]; then
  desc_len=${#description}
  if (( desc_len > 1024 )); then
    err "Description exceeds 1024 character limit ($desc_len chars)"
  fi
  if (( desc_len < 20 )); then
    warn "Description is very short ($desc_len chars). Include WHAT it does and WHEN to use it."
  fi
fi

# --- Compatibility validation ---
compat=$(get_field "compatibility")
if [[ -n "$compat" ]]; then
  compat_len=${#compat}
  if (( compat_len > 500 )); then
    err "Compatibility exceeds 500 character limit ($compat_len chars)"
  fi
fi

# --- Body content check ---
body_lines=$(echo "$body" | wc -l | tr -d ' ')
if (( body_lines > 500 )); then
  warn "SKILL.md body is $body_lines lines (recommended: <500). Consider splitting into references/."
fi
if [[ -z "$(printf '%s' "$body" | tr -d '[:space:]')" ]]; then
  warn "SKILL.md has no body content after frontmatter."
fi

# --- Plugin integration checks (project-specific) ---
plugin_root=""
check_dir=$(cd "$SKILL_DIR" && pwd)
for _ in 1 2 3 4 5; do
  check_dir=$(dirname "$check_dir")
  if [[ -d "$check_dir/.claude-plugin" ]]; then
    plugin_root="$check_dir"
    break
  fi
done

if [[ -n "$plugin_root" ]]; then
  if [[ ! -f "$plugin_root/.claude-plugin/plugin.json" ]]; then
    err "Missing .claude-plugin/plugin.json in plugin root: $plugin_root"
  fi

  # Check marketplace registration
  repo_root="$plugin_root"
  for _ in 1 2 3; do
    repo_root=$(dirname "$repo_root")
    if [[ -f "$repo_root/.claude-plugin/marketplace.json" ]]; then
      break
    fi
  done

  if [[ -f "$repo_root/.claude-plugin/marketplace.json" ]]; then
    plugin_dir_name=$(basename "$plugin_root")
    if ! grep -q "\"$plugin_dir_name\"" "$repo_root/.claude-plugin/marketplace.json"; then
      err "Plugin '$plugin_dir_name' not registered in marketplace.json"
    fi
  fi
else
  warn "No .claude-plugin/ directory found in parent directories."
fi

# --- Results ---
echo ""
echo "Validating: $SKILL_MD"
echo "---"

if [[ ${#warnings[@]} -gt 0 ]]; then
  for w in "${warnings[@]}"; do
    echo -e "${YELLOW}WARN${NC}  $w"
  done
fi

if [[ ${#errors[@]} -gt 0 ]]; then
  for e in "${errors[@]}"; do
    echo -e "${RED}FAIL${NC}  $e"
  done
  echo ""
  echo -e "${RED}Validation failed with ${#errors[@]} error(s).${NC}"
  exit 1
fi

echo -e "${GREEN}PASS${NC}  Skill '$name' is valid."
exit 0
