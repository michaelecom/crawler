# 🕷️ Enterprise Web Crawler

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Высокопроизводительный асинхронный веб-краулер enterprise-уровня для глубокого анализа структуры веб-сайтов с поддержкой миллионов страниц.

## ✨ Основные возможности

### 🚀 Производительность
- **Асинхронная обработка** миллионов страниц через asyncio + aiohttp
- **Поддержка JavaScript** сайтов через Playwright (headless browser)
- **Распределённый краулинг** для горизонтального масштабирования
- **Интеллектуальная дедупликация** URL и контента
- **Адаптивный rate limiting** для защиты от блокировки

### 📊 Аналитика и статистика
- HTTP статус-коды и время ответа
- Размер страниц и типы контента
- Внутренние/внешние ссылки
- SSL/TLS информация
- SEO метрики (meta-теги, структурированные данные)
- Детектирование битых ссылок

### 💾 Хранение данных
- **SQLite** для быстрого старта
- **PostgreSQL** для production
- Возможность возобновления после сбоя
- Checkpoint механизм для длительных сессий

### 🎨 Интерфейсы
- **CLI** приложение (Typer + Rich)
- **Web UI** с real-time мониторингом (FastAPI)
- **REST API** для интеграции
- **Python библиотека** для программного использования

## 📋 Требования

- Python 3.14 или выше
- UV (рекомендуется) или pip
- 2GB+ RAM для больших сайтов

## 🔧 Установка

### С помощью UV (рекомендуется)

\`\`\`bash
# Установите UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Клонируйте репозиторий
git clone https://github.com/yourusername/webcrawler.git
cd webcrawler

# Создайте виртуальное окружение
uv venv
source .venv/bin/activate

# Установите зависимости
uv pip install -e .

# Установите Playwright browsers
playwright install chromium
\`\`\`

## 🚀 Быстрый старт

\`\`\`bash
# Простейший краулинг
crawler crawl --url https://example.com

# С конфигурацией
crawler crawl --url https://example.com --config config.yaml

# Просмотр статистики
crawler stats --session-id abc123
\`\`\`

## 📝 Конфигурация

Основная конфигурация в \`webcrawler/config/default.yaml\`:

\`\`\`yaml
crawler:
  max_depth: 0
  max_pages: 0
  enable_javascript: false

rate_limiting:
  requests_per_second: 5
  max_concurrent_requests: 100
\`\`\`

## 🐳 Docker

\`\`\`bash
docker build -t webcrawler .
docker run webcrawler crawl --url https://example.com
\`\`\`

## 📚 Документация

- [CLAUDE.md](CLAUDE.md) - Техническое задание
- [Конфигурация](webcrawler/config/default.yaml) - Полная конфигурация

## 🗺️ Roadmap

### Фаза 1: MVP ✅
- [x] Базовая структура
- [x] Конфигурация
- [ ] Core модули
- [ ] CLI интерфейс

### Фаза 2-4: В разработке 🚧

## 📄 Лицензия

MIT License - см. [LICENSE](LICENSE)

---

**Сделано с ❤️ для enterprise веб-анализа**
