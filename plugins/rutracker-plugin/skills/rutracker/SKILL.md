---
name: rutracker
description: Search for torrents on rutracker.org and download using aria2c
allowed-tools: Bash(aria2c:*)
argument-hint: [film name] or "login"
---

# Rutracker Torrent Finder Skill

This skill uses Playwright MCP to browse rutracker.org, find torrents, and download them with aria2c.

## Commands

- `/rutracker login` - Open rutracker login page for manual authentication
- `/rutracker <film name>` - Search, auto-select best torrent, and download

## CRITICAL: Handling Large Snapshots

Playwright snapshots are 150-200KB and WILL exceed token limits. **ALWAYS save to file and grep:**

```bash
# Save snapshot to file instead of returning inline
mcp__playwright__browser_snapshot with filename="/tmp/snapshot.txt"

# Then use grep to extract needed data
```

## Workflow

### If argument is "login":

1. Navigate to `https://rutracker.org/forum/login.php`
2. Take snapshot with `filename="/tmp/rt_login.txt"`
3. Tell user: "Please log in to rutracker.org in the browser window. Type 'done' when finished."
4. When user confirms, take another snapshot and grep for "Выход" to verify login

### If argument is a film name (search query):

1. **Check login status**:
   - Navigate to `https://rutracker.org/forum/index.php`
   - Take snapshot with `filename="/tmp/rt_check.txt"`
   - Check login:
     ```bash
     grep -q "Выход" /tmp/rt_check.txt && echo "LOGGED_IN" || echo "NOT_LOGGED_IN"
     ```
   - If NOT_LOGGED_IN, tell user to run `/rutracker login` first

2. **Search for torrents**:
   - Use Russian title + year for best results: `Перелом 2007`
   - Navigate to: `https://rutracker.org/forum/tracker.php?nm=<URL_ENCODED_QUERY>`
   - Save snapshot to file: `filename="/tmp/rt_search.txt"`

3. **Parse results with grep**:
   ```bash
   # Extract torrent rows - look for pattern: row "..." containing title, size, seeders
   # Results are in format: row "status title author size seeders leechers downloads date"
   tail -c 80000 /tmp/rt_search.txt | grep -E "row.*Fracture|row.*Перелом" | head -20
   ```

   Each row contains: title, size (like "2.19 GB"), seeders count, and ref for clicking.
   Look for `link "Title..." [ref=eXXXX]` to get the clickable reference.

4. **Auto-select best torrent**:
   - **For original audio**: look for "Original Eng" or "Original" in title
   - **Audio markers**:
     - `Dub` = Russian dubbing only
     - `AVO` = Author's voiceover (одноголосый перевод)
     - `Original Eng` = Original English audio track included
     - `Sub` = Subtitles
   - Filter: size 1-5 GB, has "Original" if user requested it
   - Sort by: maximum seeders
   - Pick automatically or show top 5 if no perfect match

5. **Get magnet link**:
   - Click on torrent link using `mcp__playwright__browser_click` with the ref
   - Save snapshot: `filename="/tmp/rt_topic.txt"`
   - Extract magnet:
     ```bash
     grep -oE 'magnet:\?xt=urn:btih:[A-Z0-9]+[^"\\]+' /tmp/rt_topic.txt | head -1
     ```

6. **Download with aria2c**:
   ```bash
   aria2c "<MAGNET_LINK>" --dir=~/Movies --seed-time=0 --summary-interval=1
   ```
   - Use `--summary-interval=1` (not 0) to see progress
   - Run in background with `run_in_background=true`
   - Check progress with `tail -20 <output_file>`

## Key Grep Patterns

### Login Detection
```bash
grep -q "Выход" /tmp/snapshot.txt && echo "logged_in" || echo "not_logged_in"
```

### Search Results Extraction
```bash
# Get last 80KB where results table is located
tail -c 80000 /tmp/rt_search.txt | grep -E "row.*\[ref=" | grep -i "<search_term>"
```

### Torrent Row Structure (YAML format)
```
row "status ✓ Category Title [ref=eXXXX] Author Size Seeders Leechers Downloads Date"
```
- `gridcell "Title" [ref=eXXXX]` - clickable link reference
- `gridcell "2.19 GB"` - size
- `gridcell "47"` - seeders (first number after size)

### Magnet Link Extraction
```bash
grep -oE 'magnet:\?xt=urn:btih:[A-Z0-9]+[^"\\]+' /tmp/rt_topic.txt | head -1
```

## Audio Track Guide

When user wants original soundtrack, look for these markers in torrent title:
- ✅ `Original Eng` - has original English audio
- ✅ `Eng` after audio section - English track included
- ❌ `Dub` alone - only Russian dubbing, no original
- ⚠️ `Dub + Original` - has both Russian dub AND original

## Response Format

```
Found best match:
  Title: <torrent title>
  Size: <size>
  Seeders: <count>
  Audio: <audio tracks info>

Downloading to ~/Movies...
```

## Error Handling

- If not logged in: "You need to log in first. Run `/rutracker login`"
- If no results: "No torrents found for '<query>'"
- If no results match criteria: Show top 5 by seeders and ask user to choose
- If magnet link not found: Report error and show topic URL for manual access

## Notes

- Browser session persists - login needed only once per session
- Always URL-encode the search query
- Prefer torrents with more seeders for faster downloads
- Size filter (1-5 GB) targets good quality movie rips
- For 1080p quality, expect 8-15 GB files
- BDRip-AVC ~2GB is good balance of quality/size for 720p
