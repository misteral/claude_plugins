---
name: audiobook
description: Convert book chapters from Calibre library to audiobook (MP3) using Google Gemini TTS. Use when user wants to create audiobook from specific chapters of a book.
allowed-tools: Bash(calibredb:*) Bash(ebook-convert:*) Bash(uv:*)
argument-hint: <chapters> книги <book title>
metadata:
  author: aleksandrbobrov
  version: "2.0"
compatibility: Requires Calibre, ffmpeg, uv, GOOGLE_API_KEY
---

# Audiobook Creator Skill

Converts specific chapters from books in your Calibre library to MP3 audiobooks using Google Gemini TTS.

## Example Commands

- `/audiobook 7 и 8 главу книги Убийства и кексики`
- `/audiobook chapters 1-3 of "The Great Gatsby"`
- `/audiobook главы 5, 6, 7 книги "Война и мир"`

## Configuration

**Calibre Library Path:** `/Users/aleksandrbobrov/Library/Mobile Documents/com~apple~CloudDocs/CalibreLib`

**Scripts Directory:** `scripts/` (relative to this SKILL.md)

## Workflow

### Step 1: Parse User Request

Extract:
- **Book title**: e.g., "Убийства и кексики"
- **Chapters**: e.g., "7 и 8" → chapters 7, 8

Chapter formats:
- `главу 7` / `chapter 7` → single chapter
- `главы 7 и 8` / `chapters 7 and 8` → multiple
- `главы 1-5` / `chapters 1-5` → range
- `главы 1, 3, 5` → specific list

### Step 2: Find Book in Calibre

```bash
CALIBRE_LIB="/Users/aleksandrbobrov/Library/Mobile Documents/com~apple~CloudDocs/CalibreLib"
calibredb list --library-path "$CALIBRE_LIB" --search "title:~<book_title>" -f title,authors,formats --for-machine
```

Get book ID from results.

### Step 3: Export and Convert

```bash
WORK_DIR=$(mktemp -d)
calibredb export <BOOK_ID> --library-path "$CALIBRE_LIB" --to-dir="$WORK_DIR" --single-dir --dont-write-opf --dont-save-cover --formats=epub,fb2

# Convert to text
BOOK_FILE=$(ls "$WORK_DIR"/*.{epub,fb2,mobi} 2>/dev/null | head -1)
ebook-convert "$BOOK_FILE" "$WORK_DIR/book.txt"
```

### Step 4: Extract Chapters

```bash
SCRIPTS_DIR="<path-to-this-skill>/scripts"
uv run --project "$SCRIPTS_DIR" python "$SCRIPTS_DIR/extract_chapters.py" \
  "$WORK_DIR/book.txt" \
  --chapters 7,8 \
  --output "$WORK_DIR/chapters.md"
```

To list chapters first:
```bash
uv run --project "$SCRIPTS_DIR" python "$SCRIPTS_DIR/extract_chapters.py" "$WORK_DIR/book.txt" --list
```

### Step 5: Convert to Audiobook

```bash
uv run --project "$SCRIPTS_DIR" python "$SCRIPTS_DIR/md_to_audiobook.py" \
  "$WORK_DIR/chapters.md" \
  --voice Kore \
  --output ~/Downloads/"<BookTitle>_chapters_<X-Y>.mp3"
```

### Step 6: Cleanup

```bash
rm -rf "$WORK_DIR"
```

## Available Voices

| Voice | Style |
|-------|-------|
| Puck | Upbeat |
| Charon | Informative |
| Kore | Firm (default) |
| Fenrir | Excitable |
| Aoede | Breezy |
| Leda | Youthful |
| Orus | Firm |
| Zephyr | Bright |

## Response Format

```
Found book: "<Title>" by <Author>
Book ID: <ID>

Extracting chapters <X-Y>...
Content: ~<N> characters

Converting to audiobook...
Voice: <voice>

Audiobook saved to: ~/Downloads/<filename>.mp3
Size: <X.XX> MB
```

## Error Handling

- **Book not found**: Show available books with similar titles
- **Chapter not found**: List available chapters with `--list`
- **No GOOGLE_API_KEY**: "Please set GOOGLE_API_KEY environment variable"
- **ffmpeg missing**: "Install with: brew install ffmpeg"
