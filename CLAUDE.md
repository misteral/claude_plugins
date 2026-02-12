# Claude Plugins — Project Instructions

## Creating Skills and Plugins

**Always use `/skill-creator`** to create new skills — it handles the full checklist automatically.

Spec: https://agentskills.io/specification

## Plugin/Skill Checklist (reference)

When creating a new plugin or adding a skill, **always** complete ALL of these steps:

### 1. Plugin directory structure

```
plugins/<name>-plugin/
├── .claude-plugin/
│   └── plugin.json          # обязательно! без него плагин не активируется
└── skills/
    └── <skill-name>/
        ├── SKILL.md          # описание скила (frontmatter: name, description)
        └── references/       # опционально, доп. файлы
```

### 2. `.claude-plugin/plugin.json` (внутри плагина)

```json
{
  "name": "<name>-plugin",
  "description": "Краткое описание плагина",
  "version": "1.0.0",
  "author": {
    "name": "Aleksandr Bobrov"
  },
  "keywords": ["keyword1", "keyword2"]
}
```

### 3. Регистрация в marketplace

Добавить плагин в `.claude-plugin/marketplace.json` (корень репозитория):

```json
{
  "name": "<name>-plugin",
  "source": "./plugins/<name>-plugin",
  "description": "Описание плагина"
}
```

**Без этого шага плагин не будет виден и не активируется!**

### 4. SKILL.md frontmatter

Каждый скил должен иметь корректный frontmatter с описанием:

```yaml
---
name: skill-name
description: Описание скила — что делает и когда использовать. Это описание отображается в списке доступных скилов.
---
```
