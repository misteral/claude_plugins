#!/bin/bash

# Скрипт для поиска папок, занимающих много места

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Анализ дискового пространства ===${NC}\n"

# Директория для анализа (по умолчанию домашняя)
TARGET_DIR="${1:-$HOME}"
NUM_RESULTS="${2:-20}"

echo -e "${YELLOW}Анализируем: $TARGET_DIR${NC}"
echo -e "${YELLOW}Показываем топ-$NUM_RESULTS папок${NC}\n"

# Проверка первого уровня
echo -e "${GREEN}📊 Топ-$NUM_RESULTS папок (первый уровень):${NC}"
echo "----------------------------------------"
du -h -d 1 "$TARGET_DIR" 2>/dev/null | \
    sort -hr | \
    head -n "$NUM_RESULTS" | \
    awk '{printf "%-10s %s\n", $1, $2}'

echo ""
echo -e "${GREEN}🔍 Детальный анализ (до 3 уровней вложенности):${NC}\n"

# Более глубокий анализ
du -h -d 3 "$TARGET_DIR" 2>/dev/null | \
    sort -hr | \
    head -n 15 | \
    awk '{printf "%-10s %s\n", $1, $2}'

echo ""
echo -e "${BLUE}=== Проверка специфичных директорий ===${NC}\n"

# Кеш директории
if [ -d "$HOME/.cache" ]; then
    echo -e "${YELLOW}📦 Кеш (~/.cache):${NC}"
    du -h -d 1 "$HOME/.cache" 2>/dev/null | sort -hr | head -n 10
    echo ""
fi

# Docker/Colima
if [ -d "$HOME/.colima" ]; then
    echo -e "${YELLOW}🐳 Colima/Docker:${NC}"
    du -sh "$HOME/.colima" 2>/dev/null
    echo ""
fi

# npm
if [ -d "$HOME/.npm" ]; then
    echo -e "${YELLOW}📦 npm cache:${NC}"
    du -sh "$HOME/.npm" 2>/dev/null
    echo ""
fi

# cargo
if [ -d "$HOME/.cargo" ]; then
    echo -e "${YELLOW}🦀 Cargo:${NC}"
    du -sh "$HOME/.cargo" 2>/dev/null
    echo ""
fi

echo -e "${GREEN}=== Готово! ===${NC}"
echo ""
echo "Использование:"
echo "  $0 [директория] [количество]"
echo ""
echo "Примеры:"
echo "  $0                    # Анализ домашней директории, топ-20"
echo "  $0 ~/Developer 30     # Анализ ~/Developer, топ-30"
