#!/bin/bash

# Безопасная автоматическая очистка кеша

set -e

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

FREED_SPACE=0

echo -e "${GREEN}=== Автоматическая очистка кеша ===${NC}\n"

# Функция для подсчета освобожденного места
calculate_freed() {
    local dir=$1
    if [ -d "$dir" ]; then
        du -sk "$dir" 2>/dev/null | awk '{print $1}'
    else
        echo 0
    fi
}

# 1. Hugging Face cache
if [ -d "$HOME/.cache/huggingface" ]; then
    echo -e "${YELLOW}Очистка Hugging Face cache...${NC}"
    SIZE=$(calculate_freed "$HOME/.cache/huggingface")
    rm -rf "$HOME/.cache/huggingface"
    echo -e "${GREEN}✓ Удалено: ~$((SIZE/1024))MB${NC}\n"
    FREED_SPACE=$((FREED_SPACE + SIZE))
fi

# 2. PyTorch cache
if [ -d "$HOME/.cache/torch" ]; then
    echo -e "${YELLOW}Очистка PyTorch cache...${NC}"
    SIZE=$(calculate_freed "$HOME/.cache/torch")
    rm -rf "$HOME/.cache/torch"
    echo -e "${GREEN}✓ Удалено: ~$((SIZE/1024))MB${NC}\n"
    FREED_SPACE=$((FREED_SPACE + SIZE))
fi

# 3. UV cache
if command -v uv &> /dev/null; then
    echo -e "${YELLOW}Очистка UV cache...${NC}"
    uv cache clean 2>&1 | tail -n 1
    echo ""
fi

# 4. npm cache
if command -v npm &> /dev/null; then
    echo -e "${YELLOW}Очистка npm cache...${NC}"
    npm cache clean --force 2>&1 | grep -v "npm warn" || true
    echo -e "${GREEN}✓ npm cache очищен${NC}\n"
fi

# 5. Yarn cache (если установлен)
if command -v yarn &> /dev/null; then
    echo -e "${YELLOW}Очистка Yarn cache...${NC}"
    yarn cache clean 2>&1 | tail -n 1 || true
    echo ""
fi

# 6. Docker cleanup (если установлен)
if command -v docker &> /dev/null && docker info &> /dev/null; then
    echo -e "${YELLOW}Очистка Docker...${NC}"

    # Удаление неиспользуемых образов
    echo "  - Удаление неиспользуемых образов..."
    docker image prune -a -f 2>&1 | grep "Total reclaimed" || true

    # Удаление неиспользуемых volumes
    echo "  - Удаление неиспользуемых volumes..."
    docker volume prune -f 2>&1 | grep "Total reclaimed" || true

    echo -e "${GREEN}✓ Docker очищен${NC}\n"
fi

# 7. Colima fstrim (если Colima запущен)
if command -v colima &> /dev/null && colima status &> /dev/null; then
    echo -e "${YELLOW}Выполнение fstrim для Colima VM...${NC}"
    colima ssh -- sudo fstrim -av 2>&1 | grep "trimmed" || true
    echo -e "${GREEN}✓ Colima disk trimmed${NC}\n"
fi

echo -e "${GREEN}=== Очистка завершена! ===${NC}"

if [ $FREED_SPACE -gt 0 ]; then
    echo -e "Освобождено: ~$((FREED_SPACE/1024/1024))GB"
fi

echo ""
echo "Для более детального анализа используйте:"
echo "  ./find_large_dirs.sh"
