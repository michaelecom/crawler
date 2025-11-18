# Базовое использование

Примеры базового использования Enterprise Web Crawler.

## CLI команды

### Краулинг сайта

```bash
# Простой краулинг
crawler crawl https://example.com

# С лимитами
crawler crawl https://example.com \
  --max-pages 1000 \
  --max-depth 3

# С JavaScript
crawler crawl https://spa-example.com \
  --javascript

# С кастомной конфигурацией
crawler crawl https://example.com \
  --config my-config.yaml

# Сохранение session ID
crawler crawl https://example.com \
  --output session.txt
```

### Управление сессиями

```bash
# Список всех сессий
crawler sessions

# Фильтр по статусу
crawler sessions --status completed
crawler sessions --status running

# Лимит записей
crawler sessions --limit 50

# Статистика сессии
crawler stats <session-id>

# Возобновление остановленной сессии
crawler resume <session-id>

# Очистка старых сессий
crawler cleanup --older-than 30

# Подтверждение без запроса
crawler cleanup --older-than 30 --yes
```

## Python API

### Базовый краулинг

```python
import asyncio
from webcrawler import Crawler
from webcrawler.utils.config import init_config
from webcrawler.storage.database import init_db_manager

async def basic_crawl():
    # Инициализация
    config = init_config("config.yaml")
    db = await init_db_manager(config, create_tables=True)

    # Краулер
    crawler = Crawler(config, db)

    # Запуск
    session = await crawler.start_crawl(
        url="https://example.com",
        max_depth=3,
        max_pages=1000
    )

    # Ожидание завершения
    await session.wait_for_completion()

    # Результаты
    stats = session.get_statistics()
    print(f"Обработано: {stats.urls_crawled}")
    print(f"Найдено: {stats.urls_discovered}")
    print(f"Ошибок: {stats.urls_failed}")

    # Cleanup
    await db.close()

asyncio.run(basic_crawl())
```

### С event callbacks

```python
async def crawl_with_events():
    config = init_config()
    db = await init_db_manager(config, create_tables=True)
    crawler = Crawler(config, db)

    session = await crawler.start_crawl("https://example.com")

    # Подписка на события
    @session.on_event
    def handle_page(event):
        if event.event_type == "page_crawled":
            print(f"✓ {event.url} ({event.status_code})")

    @session.on_event
    def handle_error(event):
        if event.event_type == "error":
            print(f"✗ {event.url}: {event.error}")

    @session.on_event
    def handle_progress(event):
        if event.event_type == "progress":
            stats = event.statistics
            print(f"Progress: {stats.urls_crawled}/{stats.urls_discovered}")

    await session.wait_for_completion()
    await db.close()

asyncio.run(crawl_with_events())
```

### Pause/Resume

```python
async def crawl_with_pause():
    config = init_config()
    db = await init_db_manager(config, create_tables=True)
    crawler = Crawler(config, db)

    session = await crawler.start_crawl("https://example.com")

    # Краулим немного
    await asyncio.sleep(10)

    # Пауза
    await session.pause()
    print("Паузаsed")

    # Ждём
    await asyncio.sleep(5)

    # Возобновление
    await session.resume_session()
    print("Resumed")

    await session.wait_for_completion()
    await db.close()

asyncio.run(crawl_with_pause())
```

### Graceful shutdown

```python
import signal

async def crawl_with_shutdown():
    config = init_config()
    db = await init_db_manager(config, create_tables=True)
    crawler = Crawler(config, db)

    # Настройка signal handlers
    crawler.setup_signal_handlers()

    session = await crawler.start_crawl("https://example.com")

    # При Ctrl+C краулер gracefully остановится
    try:
        await session.wait_for_completion()
    except KeyboardInterrupt:
        print("Stopping...")
        await crawler.stop_all_sessions()

    await db.close()

asyncio.run(crawl_with_shutdown())
```

## Работа с конфигурацией

### Программная конфигурация

```python
from webcrawler.utils.config import Config

# Создание config из dict
config = Config(**{
    "crawler": {
        "max_depth": 3,
        "max_pages": 1000,
        "enable_javascript": True,
    },
    "rate_limiting": {
        "requests_per_second": 10.0,
    },
    # ... другие секции
})

# Из YAML
config = Config.from_yaml("config.yaml")

# Override параметров
config.crawler.max_pages = 500
config.rate_limiting.requests_per_second = 5.0
```

### Environment variables

```python
import os

# Set environment variables
os.environ["CRAWLER_DB_TYPE"] = "postgresql"
os.environ["CRAWLER_DB_HOST"] = "localhost"

# Config автоматически подхватит
config = init_config()
```

## Работа с БД

### Запросы через repositories

```python
from webcrawler.storage.repository import URLRepository, CrawlSessionRepository

async with db.session() as db_session:
    # URLs
    url_repo = URLRepository(db_session)

    # Получить URL по хешу
    url = await url_repo.get_by_url_hash(session_id, url_hash)

    # Pending URLs
    pending = await url_repo.get_pending_urls(session_id, limit=100)

    # Статистика
    count = await url_repo.count_by_status(session_id, "completed")

    # Sessions
    session_repo = CrawlSessionRepository(db_session)

    # Все сессии
    sessions = await session_repo.get_all(limit=10)

    # По ID
    session = await session_repo.get_by_session_id(session_id)
```

### Health checks

```python
# Проверка здоровья БД
is_healthy = await db.check_health()
print(f"DB healthy: {is_healthy}")

# Информация о таблицах
info = await db.get_table_info()
for table, count in info.items():
    print(f"{table}: {count} rows")

# Размер БД
size = await db.get_database_size()
print(f"Database size: {size / 1024 / 1024:.2f} MB")
```

## Советы и best practices

### 1. Rate limiting

```python
# Для вежливого краулинга используйте консервативные настройки
config.rate_limiting.requests_per_second = 2.0
config.rate_limiting.delay_between_requests = 500  # 500ms

# Включите adaptive delays
config.rate_limiting.adaptive_delays = True
```

### 2. Robots.txt

```python
# Всегда соблюдайте robots.txt
config.robots.obey_robots = True

# Используйте осмысленный User-Agent
config.robots.custom_user_agent = "MyBot/1.0 (+https://mysite.com/bot)"
```

### 3. Checkpoint

```python
# Для длительных сессий используйте checkpoint
config.performance.checkpoint_interval = 300  # 5 минут

# Это позволит возобновить после сбоя
```

### 4. Memory management

```python
# Для больших сайтов ограничьте max_pages
config.crawler.max_pages = 10000

# Используйте batch inserts
config.performance.db_batch_size = 1000

# Ограничьте cache
config.performance.url_cache_size = 100000
```

## Следующие шаги

- [JavaScript рендеринг](javascript_rendering.md)
- [Распределённый краулинг](distributed_crawling.md)
- [Экспорт данных](export_formats.md)
