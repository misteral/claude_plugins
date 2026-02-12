---
name: disk-cleanup
description: Find and clean up large files and directories to free disk space. Analyzes cache directories, Docker/Colima storage, build artifacts, and system temp files. Use when disk space is low or user asks to free up space, find large files, or clean cache.
metadata:
  author: aleksandrbobrov
  version: "1.0"
  created: "2026-02-11"
---

# Disk Cleanup Skill

Comprehensive disk cleanup and analysis toolkit for macOS and Linux systems.

## When to Use

- User asks to free up disk space
- User wants to find large files or directories
- User mentions "disk full", "out of space", "clean cache"
- User asks about Docker/Colima storage usage
- User wants to optimize storage

## Quick Start

### 1. Find Large Directories

Use the provided script to analyze disk usage:

```bash
scripts/find_large_dirs.sh [num_results]
```

Default shows top 20 largest directories. Pass a number to show more/fewer results.

### 2. Analyze Specific Areas

Common large directories to check:

**macOS-specific:**
- `~/.cache/` - Application caches (often 10-50GB+)
- `~/.colima/` - Docker/Colima VM disks (often 20-50GB+)
- `~/Library/Caches/` - System caches
- `~/Downloads/` - Old downloads
- `~/Movies/`, `~/Music/` - Media files

**Development tools:**
- `~/.npm/` - npm cache
- `~/.cargo/` - Rust packages
- `~/.rustup/` - Rust toolchains
- `~/.cache/uv/` - Python uv cache
- `~/.cache/huggingface/` - ML models
- `node_modules/` directories in projects

### 3. Safe Cleanup Targets

#### Cache Directories (Always Safe)

```bash
# Hugging Face models (safe - will re-download if needed)
rm -rf ~/.cache/huggingface

# Python uv cache
uv cache clean

# PyTorch cache
rm -rf ~/.cache/torch

# npm cache
npm cache clean --force

# Yarn cache
yarn cache clean
```

#### Docker/Colima Cleanup

```bash
# Remove unused images
docker image prune -a -f

# Remove unused volumes
docker volume prune -f

# Remove build cache
docker buildx prune -af

# CRITICAL: Trim VM filesystem to reclaim space
colima ssh -- sudo fstrim -av
```

**Note:** After Docker cleanup, ALWAYS run `fstrim` to actually reclaim disk space on the host!

## Step-by-Step Process

### Phase 1: Discovery

1. Run `scripts/find_large_dirs.sh` to get overview
2. Check home directory first level: `du -h -d 1 ~/ | sort -hr | head -n 20`
3. Investigate specific large directories

### Phase 2: Analysis

For each large directory, determine:
- **Purpose:** What is it? (cache, data, builds, etc.)
- **Safety:** Can it be deleted or cleaned?
- **Impact:** What happens if deleted?

See `references/CLEANUP_NOTES.md` for detailed analysis of common directories.

### Phase 3: Cleanup

**Order of operations:**

1. **Caches first** (safest, often largest gains)
   - Application caches (`~/.cache/`)
   - Package manager caches (npm, uv, cargo)
   - ML model caches (huggingface)

2. **Docker/Colima** (if applicable)
   - Remove unused images
   - Prune volumes
   - Clear build cache
   - **IMPORTANT:** Run fstrim to reclaim space

3. **Build artifacts** (project-specific)
   - `node_modules/` (can regenerate with `npm install`)
   - `target/` in Rust projects
   - `build/`, `dist/` directories

4. **Downloads and temp files**
   - Old files in `~/Downloads/`
   - Browser cache
   - Trash (empty from GUI or check size first)

### Phase 4: Verification

```bash
# Check reclaimed space
du -sh ~/.cache ~/.colima ~/Developer

# Verify Docker is clean
docker system df

# For Colima, check actual disk size
du -h -d 2 ~/.colima
```

## Important Notes

### macOS Trash Access

macOS blocks terminal access to `~/.Trash` due to TCC (Transparency, Consent, and Control). User must empty trash manually from Finder.

### Colima/Docker Space Reclamation

Docker/Colima uses virtual disks that don't automatically shrink when files are deleted. **You must run `fstrim`** to actually reclaim space:

```bash
colima ssh -- sudo fstrim -av
```

This is CRITICAL - without fstrim, the .colima directory size won't decrease even after deleting files.

### Build Cache Trade-offs

Deleting build caches (Docker buildx, npm, cargo) saves space but means:
- First rebuild will be slower
- May need to re-download packages
- Generally safe but has performance cost

## Safety Guidelines

**Always safe to delete:**
- Cache directories (`~/.cache/`, `~/.npm/`, etc.)
- Docker unused images/volumes/build cache
- Temp files and downloads

**Check before deleting:**
- Project directories (may have uncommitted work)
- Database volumes (may contain important data)
- Custom configuration files

**Never delete without asking:**
- User documents
- Source code repositories
- Database data directories
- Anything in active use

## Scripts Reference

- `scripts/find_large_dirs.sh` - Find and analyze large directories
- `scripts/cleanup_cache.sh` - Safe automated cache cleanup

## Additional Resources

- `references/CLEANUP_NOTES.md` - Detailed notes from cleanup sessions
- `references/DOCKER_CLEANUP.md` - Docker/Colima specific procedures
