# Claude Plugins

A collection of useful Claude Code plugins.

## Installation

Install all plugins from this marketplace using:

```bash
/plugin marketplace add misteral/claude_plugins
```

Or install a specific plugin:

```bash
/plugin add misteral/claude_plugins/rutracker-plugin
```

## Available Plugins

### audiobook-plugin

Convert book chapters from your Calibre library to MP3 audiobooks using Google Gemini TTS via Vertex AI.

**Features:**
- Extract specific chapters from books in Calibre library
- High-quality text-to-speech with professional narration voice (Despina)
- Support for various chapter formats: single, multiple, ranges
- Automatic book search by title
- Output as MP3 to Downloads folder

**Usage:**
- `/audiobook chapters 1-3 of "The Great Gatsby"` - Convert chapter range
- `/audiobook chapter 7 of "Book Title"` - Convert single chapter
- `/audiobook chapters 1, 3, 5 of "Book Title"` - Convert specific chapters

**Requirements:**
- [Calibre](https://calibre-ebook.com/) with `calibredb` and `ebook-convert`
- [ffmpeg](https://ffmpeg.org/) for audio processing
- [uv](https://github.com/astral-sh/uv) Python package manager
- Google Cloud authentication (`gcloud auth application-default login`)

---

### rutracker-plugin

Search for torrents on rutracker.org and download using aria2c.

**Features:**
- Login to rutracker.org
- Search torrents by film name
- Auto-select best torrent based on seeders and quality
- Download via magnet link using aria2c

**Usage:**
- `/rutracker login` - Open login page for authentication
- `/rutracker <film name>` - Search and download a torrent

**Requirements:**
- [Playwright MCP](https://github.com/anthropics/claude-code-mcp-servers) for browser automation
- [aria2c](https://aria2.github.io/) for downloading torrents

## License

MIT
