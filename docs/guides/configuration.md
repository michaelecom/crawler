# Конфигурация

Полное руководство по настройке Enterprise Web Crawler через YAML конфигурацию.

## Структура конфигурации

Конфигурация загружается из YAML файла. По умолчанию используется `config/default.yaml`, но можно указать свой файл через параметр `--config`.

```yaml
# config.yaml
crawler:
  # Настройки краулинга

rate_limiting:
  # Ограничения скорости

robots:
  # Работа с robots.txt

database:
  # Настройки БД

distributed:
  # Распределённый режим

export:
  # Экспорт данных

logging:
  # Логирование

performance:
  # Производительность

monitoring:
  # Мониторинг
```

## Секция: crawler

Основные настройки краулинга.

```yaml
crawler:
  # Начальные URL для краулинга
  start_urls:
    - "https://example.com"
    - "https://test.com"

  # Максимальная глубина рекурсии
  # 0 = без ограничений
  # 1 = только start_urls
  # 2 = start_urls + ссылки с них
  max_depth: 0

  # Максимальное количество страниц
  # 0 = без ограничений
  max_pages: 1000000

  # Обрабатывать поддомены
  # true: example.com, blog.example.com, api.example.com
  # false: только example.com
  include_subdomains: true

  # Ограничиться только доменом из start_url
  # true: только example.com
  # false: может переходить на другие домены
  restrict_to_domain: true

  # Включить JavaScript рендеринг
  # Использует Playwright для SPA/динамических сайтов
  enable_javascript: false

  # Таймаут для JavaScript рендеринга (секунды)
  javascript_timeout: 30

  # Типы контента для обработки
  allowed_content_types:
    - "text/html"
    - "application/xhtml+xml"
    - "application/pdf"
    - "text/plain"
    - "application/json"
    - "application/xml"
    - "image/*"
    - "text/css"
    - "application/javascript"

  # Игнорировать SSL ошибки
  # ВНИМАНИЕ: используйте только для тестирования!
  ignore_ssl_errors: false

  # Следовать редиректам
  follow_redirects: true

  # Максимальное количество редиректов
  max_redirects: 10
```

### Примеры использования

#### Краулинг только главной страницы

```yaml
crawler:
  start_urls:
    - "https://example.com"
  max_depth: 1
  max_pages: 1
```

#### Полный краулинг домена

```yaml
crawler:
  start_urls:
    - "https://example.com"
  max_depth: 0
  max_pages: 0
  include_subdomains: true
  restrict_to_domain: true
```

#### SPA приложение с JavaScript

```yaml
crawler:
  start_urls:
    - "https://spa-example.com"
  enable_javascript: true
  javascript_timeout: 60
```

## Секция: rate_limiting

Контроль скорости запросов для вежливого краулинга.

```yaml
rate_limiting:
  # Запросов в секунду (per domain)
  # Рекомендуется: 1-10 для вежливого краулинга
  requests_per_second: 5.0

  # Задержка между запросами (миллисекунды)
  # Минимальная пауза между запросами к одному домену
  delay_between_requests: 200

  # Максимум конкурентных запросов
  # Общее количество одновременных соединений
  max_concurrent_requests: 100

  # Максимум конкурентных запросов на домен
  # Ограничение для каждого отдельного домена
  max_concurrent_per_domain: 10

  # Таймаут запроса (секунды)
  request_timeout: 30

  # Таймаут соединения (секунды)
  connect_timeout: 10

  # Количество повторов при ошибке
  max_retries: 3

  # Экспоненциальная задержка между повторами
  retry_backoff_factor: 2.0

  # Адаптивные задержки
  # Автоматическое замедление при ошибках 429/503
  adaptive_delays: true

  # Коэффициент замедления при ошибках
  adaptive_slowdown_factor: 2.0

  # Коэффициент ускорения при успехе
  adaptive_speedup_factor: 0.9
```

### Профили rate limiting

#### Агрессивный краулинг (высокая скорость)

```yaml
rate_limiting:
  requests_per_second: 20.0
  delay_between_requests: 50
  max_concurrent_requests: 200
  max_concurrent_per_domain: 20
  adaptive_delays: true
```

#### Консервативный краулинг (вежливый)

```yaml
rate_limiting:
  requests_per_second: 2.0
  delay_between_requests: 500
  max_concurrent_requests: 50
  max_concurrent_per_domain: 5
  adaptive_delays: true
```

#### Медленный краулинг (минимальная нагрузка)

```yaml
rate_limiting:
  requests_per_second: 0.5
  delay_between_requests: 2000
  max_concurrent_requests: 10
  max_concurrent_per_domain: 2
  adaptive_delays: true
```

## Секция: robots

Работа с robots.txt и User-Agent.

```yaml
robots:
  # Соблюдать robots.txt
  # true: парсить и следовать правилам
  # false: игнорировать robots.txt (НЕ рекомендуется!)
  obey_robots: true

  # Кеширование robots.txt (секунды)
  # Как долго хранить robots.txt в памяти
  cache_ttl: 3600

  # User-Agent для парсинга robots.txt
  # Какую секцию robots.txt использовать
  user_agent: "MyWebCrawler"

  # Кастомный User-Agent для HTTP запросов
  # Идентификация краулера для серверов
  custom_user_agent: "Mozilla/5.0 (compatible; MyWebCrawler/1.0; +https://example.com/bot)"

  # Honour Crawl-delay директиву
  # Если в robots.txt указан Crawl-delay, использовать его
  honour_crawl_delay: true

  # Максимальный Crawl-delay (секунды)
  # Ограничение на слишком большие задержки
  max_crawl_delay: 60
```

### Примеры User-Agent

#### Идентификация как исследовательский бот

```yaml
robots:
  custom_user_agent: "ResearchBot/1.0 (University Research; +https://university.edu/research)"
```

#### Идентификация как мониторинг сервис

```yaml
robots:
  custom_user_agent: "UptimeMonitor/2.0 (+https://monitor.com/bot)"
```

#### Симуляция браузера (не рекомендуется)

```yaml
robots:
  custom_user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
```

## Секция: database

Настройки хранилища данных.

```yaml
database:
  # Тип БД: sqlite или postgresql
  type: "sqlite"

  # SQLite настройки
  sqlite_path: "data/crawler.db"

  # PostgreSQL настройки
  postgresql:
    host: "localhost"
    port: 5432
    database: "webcrawler"
    user: "crawler"
    password: "secure_password"

    # Размер пула соединений
    pool_size: 20

    # Максимум overflow соединений
    max_overflow: 10

    # Таймаут получения соединения (секунды)
    pool_timeout: 30

    # Время жизни соединения (секунды)
    pool_recycle: 3600

    # Pre-ping перед использованием
    pool_pre_ping: true

  # Автоматическое создание таблиц
  create_tables: true

  # Echo SQL запросов (для дебага)
  echo: false
```

### Миграция с SQLite на PostgreSQL

```yaml
# Шаг 1: Экспортируем данные из SQLite
database:
  type: "sqlite"
  sqlite_path: "data/crawler.db"
```

```bash
crawler export --session-id <id> --format json --output backup.json
```

```yaml
# Шаг 2: Переключаемся на PostgreSQL
database:
  type: "postgresql"
  postgresql:
    host: "localhost"
    port: 5432
    database: "webcrawler"
    user: "crawler"
    password: "secure_password"
    pool_size: 20
```

```bash
crawler import --file backup.json
```

## Секция: distributed

Распределённый краулинг с несколькими worker'ами.

```yaml
distributed:
  # Включить распределённый режим
  enabled: false

  # Тип координатора: redis или rabbitmq
  coordinator_type: "redis"

  # Redis настройки
  redis:
    host: "localhost"
    port: 6379
    db: 0
    password: null

    # Префикс ключей
    key_prefix: "webcrawler:"

    # TTL для задач (секунды)
    task_ttl: 3600

  # RabbitMQ настройки
  rabbitmq:
    host: "localhost"
    port: 5672
    vhost: "/"
    user: "guest"
    password: "guest"

    # Имя очереди
    queue_name: "webcrawler_tasks"

    # Prefetch count
    prefetch_count: 10

  # Количество worker'ов
  workers: 4

  # Heartbeat интервал (секунды)
  heartbeat_interval: 30

  # Distributed locks timeout (секунды)
  lock_timeout: 300
```

### Запуск распределённого краулинга

```bash
# Запуск координатора
crawler coordinator --config config.yaml

# Запуск worker'ов (в отдельных терминалах)
crawler worker --config config.yaml --worker-id 1
crawler worker --config config.yaml --worker-id 2
crawler worker --config config.yaml --worker-id 3
crawler worker --config config.yaml --worker-id 4

# Или через Docker Compose
docker-compose up --scale worker=4
```

## Секция: export

Настройки экспорта данных.

```yaml
export:
  # Поддерживаемые форматы
  formats:
    - "json"
    - "html"
    - "pdf"
    - "excel"
    - "csv"
    - "graphml"

  # Директория для экспорта
  output_dir: "exports/"

  # Включить сжатие для больших экспортов
  compress: true

  # Формат сжатия: gzip или zip
  compression_format: "gzip"

  # HTML отчёт настройки
  html_report:
    # Включить интерактивные графики
    include_charts: true

    # Тема: light или dark
    theme: "light"

    # Включить граф ссылок
    include_graph: true

  # PDF отчёт настройки
  pdf_report:
    # Размер страницы: A4, Letter
    page_size: "A4"

    # Ориентация: portrait или landscape
    orientation: "portrait"

    # Включить оглавление
    include_toc: true

  # Excel экспорт настройки
  excel_export:
    # Листы для включения
    sheets:
      - "summary"
      - "urls"
      - "errors"
      - "statistics"

    # Автоширина колонок
    auto_width: true

  # Визуализация графа
  graph_visualization:
    enabled: true

    # Максимум узлов для рендеринга
    max_nodes: 10000

    # Layout: force_directed, hierarchical, circular
    layout: "force_directed"

    # Формат: html, png, svg
    format: "html"
```

## Секция: logging

Настройки логирования.

```yaml
logging:
  # Уровень логирования
  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  level: "INFO"

  # Файл для логов
  file: "logs/crawler.log"

  # Ротация логов
  # 1 day, 1 week, 100 MB
  rotation: "1 day"

  # Срок хранения
  # 30 days, 1 week
  retention: "30 days"

  # Формат логов
  # simple, detailed, json
  format: "detailed"

  # Логировать в консоль
  console: true

  # Логировать в файл
  file_logging: true

  # Логировать в syslog
  syslog: false

  # Сжимать старые логи
  compress_rotated: true
```

### Форматы логов

#### Simple

```
2025-11-18 10:30:45 INFO Crawler started
2025-11-18 10:30:46 INFO Fetched https://example.com (200)
```

#### Detailed

```
2025-11-18 10:30:45 [INFO] webcrawler.core.crawler - Crawler started for https://example.com
2025-11-18 10:30:46 [INFO] webcrawler.core.fetcher - Fetched https://example.com (status=200, time=0.234s)
```

#### JSON

```json
{"timestamp": "2025-11-18T10:30:45Z", "level": "INFO", "logger": "webcrawler.core.crawler", "message": "Crawler started", "session_id": "abc123"}
{"timestamp": "2025-11-18T10:30:46Z", "level": "INFO", "logger": "webcrawler.core.fetcher", "message": "Fetched URL", "url": "https://example.com", "status": 200, "time": 0.234}
```

## Секция: performance

Оптимизация производительности.

```yaml
performance:
  # Размер батча для записи в БД
  # Запись данных группами для ускорения
  db_batch_size: 1000

  # Интервал flush батча (секунды)
  db_batch_flush_interval: 10

  # Checkpoint интервал (секунды)
  # Сохранение состояния для возобновления
  checkpoint_interval: 300

  # Размер кеша для URL
  # LRU кеш для дедупликации URL
  url_cache_size: 100000

  # Размер кеша для robots.txt
  robots_cache_size: 10000

  # Размер кеша для DNS
  dns_cache_size: 10000

  # Prefetch размер для БД
  db_prefetch_size: 1000

  # Использовать connection pooling
  use_connection_pool: true

  # Размер буфера для парсинга
  parse_buffer_size: 8192
```

## Секция: monitoring

Мониторинг и метрики.

```yaml
monitoring:
  # Включить метрики
  enable_metrics: true

  # Prometheus endpoint
  prometheus_enabled: true
  prometheus_port: 9090
  prometheus_path: "/metrics"

  # WebSocket для real-time мониторинга
  websocket_enabled: true
  websocket_port: 8765

  # Health check endpoint
  health_check_enabled: true
  health_check_port: 8080
  health_check_path: "/health"

  # Sentry для отслеживания ошибок
  sentry_enabled: false
  sentry_dsn: ""
  sentry_environment: "production"
  sentry_traces_sample_rate: 0.1
```

## Environment Variables

Любой параметр конфигурации может быть переопределён через переменные окружения:

```bash
# Формат: CRAWLER_<SECTION>_<PARAMETER>

# Database
export CRAWLER_DB_TYPE=postgresql
export CRAWLER_DB_HOST=localhost
export CRAWLER_DB_PORT=5432
export CRAWLER_DB_NAME=webcrawler
export CRAWLER_DB_USER=crawler
export CRAWLER_DB_PASSWORD=secure_password

# Rate limiting
export CRAWLER_RATE_REQUESTS_PER_SECOND=10
export CRAWLER_RATE_MAX_CONCURRENT=200

# Logging
export CRAWLER_LOG_LEVEL=DEBUG
export CRAWLER_LOG_FILE=/var/log/crawler.log

# Distributed
export CRAWLER_DISTRIBUTED_ENABLED=true
export CRAWLER_REDIS_HOST=redis.example.com
export CRAWLER_REDIS_PORT=6379
```

## Приоритет конфигурации

1. **Environment variables** (высший приоритет)
2. **Параметры командной строки** (`--config`, `--max-pages`, и т.д.)
3. **Кастомный YAML файл** (`--config config.yaml`)
4. **Дефолтный YAML** (`config/default.yaml`)

## Примеры полных конфигураций

### Локальная разработка

```yaml
crawler:
  max_depth: 3
  max_pages: 100
  enable_javascript: false

rate_limiting:
  requests_per_second: 10.0
  max_concurrent_requests: 50

database:
  type: "sqlite"
  sqlite_path: "data/dev.db"

logging:
  level: "DEBUG"
  console: true

distributed:
  enabled: false
```

### Production краулинг

```yaml
crawler:
  max_depth: 0
  max_pages: 10000000
  enable_javascript: true
  include_subdomains: true

rate_limiting:
  requests_per_second: 5.0
  max_concurrent_requests: 200
  adaptive_delays: true

database:
  type: "postgresql"
  postgresql:
    host: "db.example.com"
    database: "webcrawler_prod"
    pool_size: 50

logging:
  level: "INFO"
  format: "json"
  file: "/var/log/crawler/crawler.log"

distributed:
  enabled: true
  coordinator_type: "redis"
  workers: 16

monitoring:
  enable_metrics: true
  prometheus_enabled: true
  sentry_enabled: true
```

## Валидация конфигурации

Проверить корректность конфигурации:

```bash
crawler validate-config --config config.yaml
```

Вывод примера конфигурации:

```bash
crawler config-template > my-config.yaml
```

## Следующие шаги

- [JavaScript рендеринг](javascript_rendering.md)
- [Распределённый краулинг](distributed_crawling.md)
- [Экспорт данных](export_formats.md)
