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
