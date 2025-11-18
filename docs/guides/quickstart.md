# Быстрый старт

Это руководство поможет вам начать работу с Enterprise Web Crawler за 5 минут.

## Требования

- Python 3.12+ (рекомендуется 3.14)
- UV package manager или pip
- Docker (опционально)

## Установка

### Через UV (рекомендуется)

```bash
# Клонирование репозитория
git clone https://github.com/yourusername/crawler.git
cd crawler

# Установка через UV
uv pip install -e .

# Установка Playwright browsers (для JavaScript)
playwright install chromium
```

### Через Docker

```bash
# Quick start
make quickstart

# Или вручную
docker-compose up -d
```

## Первый запуск

### CLI

```bash
# Простой краулинг
crawler crawl https://example.com

# С настройками
crawler crawl https://example.com \
  --max-pages 100 \
  --max-depth 2 \
  --config config.yaml
```

### Python API

```python
import asyncio
from webcrawler import Crawler
from webcrawler.utils.config import init_config
from webcrawler.storage.database import init_db_manager

async def main():
    # Инициализация
    config = init_config()
    db = await init_db_manager(config, create_tables=True)

    # Краулинг
    crawler = Crawler(config, db)
    session = await crawler.start_crawl("https://example.com")

    # Ожидание
    await session.wait_for_completion()

    # Результаты
    stats = session.get_statistics()
    print(f"Обработано: {stats.urls_crawled} страниц")

    # Cleanup
    await db.close()

asyncio.run(main())
```

## Конфигурация

Создайте файл конфигурации:

```bash
crawler init --output my-config.yaml
```

Отредактируйте `my-config.yaml`:

```yaml
crawler:
  max_depth: 3
  max_pages: 1000
  enable_javascript: true

rate_limiting:
  requests_per_second: 5
  max_concurrent_requests: 100

database:
  type: sqlite
  sqlite_path: data/crawler.db
```

Используйте:

```bash
crawler crawl https://example.com --config my-config.yaml
```

## Просмотр результатов

```bash
# Список сессий
crawler sessions

# Статистика сессии
crawler stats <session-id>

# Экспорт (будущая функция)
crawler export <session-id> --format json
```

## Docker

### Development

```bash
# Запуск dev окружения
make dev

# Вход в контейнер
make shell

# Внутри контейнера
crawler crawl https://example.com
```

### Production

```bash
# Запуск production stack
make build
make up

# Проверка логов
make logs

# Остановка
make down
```

## Следующие шаги

- [Детальная установка](installation.md)
- [Конфигурация](configuration.md)
- [Базовое использование](basic_usage.md)
- [JavaScript рендеринг](javascript_rendering.md)
