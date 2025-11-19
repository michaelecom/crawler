# Техническое задание: Enterprise Web Crawler

## Общее описание проекта

Разработка высокопроизводительного веб-краулера enterprise-уровня для глубокого анализа структуры веб-сайтов с поддержкой миллионов страниц. Проект ориентирован на качество кода Senior Python Developer (15+ лет опыта) для BigTech компаний.

**Язык разработки**: Python 3.14
**Уровень сложности**: Senior/Principal Engineer
**Документация**: полная на русском языке
**Комментарии в коде**: обязательны, на русском

---

## Ключевые возможности

### 1. Функциональные требования

#### Краулинг
- ✅ Асинхронная обработка миллионов страниц (asyncio + aiohttp)
- ✅ Рекурсивный обход всех страниц домена/IP
- ✅ Поддержка JavaScript-сайтов через headless browser (Playwright)
- ✅ Обработка всех типов контента (HTML, PDF, изображения, CSS, JS, API endpoints)
- ✅ Настраиваемая глубина обхода через YAML конфигурацию
- ✅ Обработка поддоменов (настраиваемо)
- ✅ Интеллектуальная дедупликация URL (каноникализация)

#### Этика и ограничения
- ✅ Парсинг и использование robots.txt как источника информации
- ✅ Парсинг sitemap.xml для оптимизации
- ✅ Адаптивный rate limiting (per domain, настраиваемый)
- ✅ Уважительные задержки между запросами (защита от бана)
- ✅ User-Agent кастомизация
- ✅ Поддержка прокси (опционально)

#### Статистика и метрики
Собирать детальную информацию по каждой странице:
- HTTP статус-коды (200, 301, 302, 404, 500, 503 и т.д.)
- Время ответа сервера (response time)
- Размер страницы (в байтах)
- Content-Type и кодировка
- Количество внутренних ссылок (на тот же домен)
- Количество внешних ссылок (на другие домены)
- Глубина страницы от начальной точки входа
- Количество посещений каждого URL (если на него ведут множественные ссылки)
- HTTP заголовки (Server, X-Powered-By, Cache-Control и т.д.)
- SSL/TLS информация (версия протокола, сертификат)
- Редиректы (цепочка переадресаций)
- Обнаруженные ошибки (timeout, connection refused, DNS ошибки)
- Наличие мета-тегов (description, keywords, robots)
- Структурированные данные (Schema.org, Open Graph)
- Языки страницы (из тега lang)
- Время последнего изменения (Last-Modified)
- ETag для версионирования

#### Дедупликация и учёт ссылок
- Каждая уникальная страница обрабатывается **один раз**
- Если страница уже обработана и все ссылки с неё извлечены, **не добавляем её повторно**
- Но если **разные страницы ведут на одну и ту же ссылку**, это учитывается в статистике (счётчик посещений)
- Детектирование дубликатов контента (через хеширование)

### 2. Хранение данных

#### База данных
- **Основное хранилище**: SQLite (файл `crawler.db`)
- **Миграция на PostgreSQL**: архитектура должна поддерживать переключение через адаптер/ORM
- **ORM**: SQLAlchemy 2.x (современный async стиль)
- **Схема БД** должна включать:
  - `urls` - таблица URL с метаданными
  - `crawl_sessions` - сессии краулинга
  - `links` - граф связей между страницами
  - `statistics` - агрегированная статистика
  - `errors` - журнал ошибок
  - `content_hashes` - для детектирования дубликатов контента

#### Персистентность
- Возможность **возобновления краулинга** после сбоя
- Сохранение состояния очереди URL
- Checkpoint механизм для длительных краулинг-сессий
- Graceful shutdown с сохранением текущего прогресса

### 3. Архитектура

#### Компоненты системы

```
webcrawler/
├── core/
│   ├── crawler.py          # Основной движок краулера
│   ├── fetcher.py          # HTTP/HTTPS fetcher (aiohttp)
│   ├── js_fetcher.py       # JavaScript renderer (Playwright)
│   ├── parser.py           # HTML/XML парсер (BeautifulSoup4 + lxml)
│   ├── url_manager.py      # Менеджер URL (дедупликация, нормализация)
│   ├── queue_manager.py    # Приоритетная очередь URL
│   └── session_manager.py  # Управление сессиями краулинга
├── storage/
│   ├── database.py         # Абстракция БД (адаптер SQLite/PostgreSQL)
│   ├── models.py           # SQLAlchemy модели
│   ├── migrations/         # Alembic миграции
│   └── repository.py       # Репозиторий паттерн для доступа к данным
├── analyzers/
│   ├── robots_parser.py    # Парсер robots.txt
│   ├── sitemap_parser.py   # Парсер sitemap.xml
│   ├── content_analyzer.py # Анализ контента (мета-теги, структура)
│   ├── link_extractor.py   # Извлечение ссылок
│   └── stats_calculator.py # Расчёт статистики
├── utils/
│   ├── config.py           # Загрузка YAML конфигурации
│   ├── rate_limiter.py     # Rate limiting механизм
│   ├── logger.py           # Настройка логирования
│   ├── validators.py       # Валидация URL, доменов
│   └── helpers.py          # Вспомогательные функции
├── distributed/            # Модуль для распределённого краулинга
│   ├── coordinator.py      # Координатор задач (Redis/RabbitMQ)
│   ├── worker.py           # Worker для обработки задач
│   └── queue_backend.py    # Абстракция для очередей
├── export/
│   ├── html_exporter.py    # Экспорт в HTML отчёт
│   ├── pdf_exporter.py     # Экспорт в PDF (ReportLab)
│   ├── excel_exporter.py   # Экспорт в Excel (openpyxl)
│   ├── json_exporter.py    # Экспорт в JSON
│   └── graph_visualizer.py # Визуализация графа ссылок (NetworkX + Plotly)
├── cli/
│   └── main.py             # CLI приложение (Typer/Click)
├── web/
│   ├── app.py              # Web UI (FastAPI)
│   ├── api/                # REST API endpoints
│   ├── templates/          # HTML шаблоны (Jinja2)
│   ├── static/             # CSS/JS для веб-интерфейса
│   └── websocket.py        # WebSocket для мониторинга в реальном времени
├── lib/
│   └── api.py              # Публичное API для использования как библиотека
├── tests/
│   ├── unit/               # Unit тесты
│   ├── integration/        # Интеграционные тесты
│   └── performance/        # Performance тесты
├── docs/
│   ├── architecture.md     # Описание архитектуры
│   ├── api_reference.md    # API документация
│   ├── user_guide.md       # Руководство пользователя
│   └── deployment.md       # Инструкции по развёртыванию
├── config/
│   ├── default.yaml        # Конфигурация по умолчанию
│   └── example.yaml        # Пример конфигурации
├── pyproject.toml          # Poetry/UV для управления зависимостями
├── README.md               # Основная документация (русский)
└── CLAUDE.md               # Этот файл (референс для рабочих сессий)
```

#### Асинхронная обработка
- **asyncio** для основного event loop
- **aiohttp** для HTTP запросов
- **asyncpg** для PostgreSQL (когда миграция)
- **aiosqlite** для асинхронного SQLite
- Пул соединений для оптимизации
- Семафоры для контроля конкурентности (избежание race conditions)
- Корректная обработка asyncio.gather с error handling

#### Распределённая архитектура (опционально)
- **Redis** как бэкенд для распределённой очереди и синхронизации
- **RabbitMQ/Celery** как альтернатива для task queue
- Поддержка горизонтального масштабирования (несколько worker'ов)
- Координация через distributed locks
- Архитектура должна работать как в standalone, так и в distributed режиме

### 4. Конфигурация (YAML)

Пример структуры `config.yaml`:

```yaml
crawler:
  # Начальные точки для краулинга
  start_urls:
    - "https://example.com"

  # Глубина рекурсивного обхода (0 = без ограничений)
  max_depth: 0

  # Максимальное количество страниц для краулинга
  max_pages: 1000000

  # Включать поддомены
  include_subdomains: true

  # Обрабатывать только указанный домен/IP
  restrict_to_domain: true

  # JavaScript рендеринг
  enable_javascript: true
  javascript_timeout: 30  # секунд

  # Типы контента для обработки
  allowed_content_types:
    - "text/html"
    - "application/pdf"
    - "text/plain"
    - "application/json"
    - "image/*"
    - "text/css"
    - "application/javascript"

# Rate limiting
rate_limiting:
  # Запросов в секунду (per domain)
  requests_per_second: 5

  # Задержка между запросами (мс)
  delay_between_requests: 200

  # Максимум конкурентных запросов
  max_concurrent_requests: 100

  # Таймаут запроса (секунд)
  request_timeout: 30

  # Количество повторов при ошибке
  max_retries: 3

# Robots.txt
robots:
  # Соблюдать robots.txt
  obey_robots: true

  # User-agent для парсинга robots.txt
  user_agent: "MyWebCrawler/1.0"

  # Кастомный User-Agent для запросов
  custom_user_agent: "Mozilla/5.0 (compatible; MyWebCrawler/1.0; +https://example.com/bot)"

# База данных
database:
  # Тип БД: sqlite или postgresql
  type: "sqlite"

  # Путь к SQLite файлу
  sqlite_path: "data/crawler.db"

  # PostgreSQL настройки (для миграции)
  postgresql:
    host: "localhost"
    port: 5432
    database: "webcrawler"
    user: "crawler"
    password: "secure_password"
    pool_size: 20

# Распределённый краулинг
distributed:
  enabled: false

  # Redis для координации
  redis:
    host: "localhost"
    port: 6379
    db: 0

  # Количество worker'ов
  workers: 4

# Экспорт
export:
  # Форматы для экспорта
  formats:
    - "json"
    - "html"
    - "pdf"
    - "excel"

  # Директория для экспорта
  output_dir: "exports/"

  # Визуализация графа
  graph_visualization:
    enabled: true
    max_nodes: 10000  # Ограничение для больших сайтов
    layout: "force_directed"  # или "hierarchical"

# Логирование
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  file: "logs/crawler.log"
  rotation: "1 day"
  retention: "30 days"
  format: "detailed"  # или "json"

# Производительность
performance:
  # Размер батча для записи в БД
  db_batch_size: 1000

  # Checkpoint интервал (секунд)
  checkpoint_interval: 300

  # Размер кеша для URL
  url_cache_size: 100000

# Мониторинг
monitoring:
  # Метрики в реальном времени
  enable_metrics: true

  # Prometheus endpoint
  prometheus_port: 9090

  # WebSocket порт для real-time мониторинга
  websocket_port: 8765
```

### 5. Интерфейсы

#### CLI приложение
```bash
# Запуск краулинга
crawler crawl --url https://example.com --config config.yaml

# Возобновление сессии
crawler resume --session-id abc123

# Экспорт результатов
crawler export --session-id abc123 --format pdf --output report.pdf

# Визуализация графа
crawler visualize --session-id abc123 --output graph.html

# Статистика
crawler stats --session-id abc123

# Список сессий
crawler sessions list

# Очистка старых данных
crawler cleanup --older-than 30d
```

**Библиотека**: Typer или Click (с rich для красивого вывода)

#### Web UI (FastAPI)
- Dashboard с мониторингом в реальном времени
- Запуск/остановка/возобновление краулинга через веб-интерфейс
- Визуализация статистики (графики, таблицы)
- Интерактивная визуализация графа ссылок (D3.js/Cytoscape.js)
- Экспорт отчётов прямо из UI
- WebSocket для live updates
- REST API для интеграции

Эндпоинты:
- `POST /api/v1/crawl/start` - запуск краулинга
- `GET /api/v1/crawl/{session_id}/status` - статус сессии
- `POST /api/v1/crawl/{session_id}/pause` - пауза
- `POST /api/v1/crawl/{session_id}/resume` - возобновление
- `GET /api/v1/crawl/{session_id}/stats` - статистика
- `GET /api/v1/crawl/{session_id}/export/{format}` - экспорт
- `GET /api/v1/sessions` - список всех сессий
- `DELETE /api/v1/sessions/{session_id}` - удаление сессии

#### Библиотека (программный API)
```python
from webcrawler import Crawler, Config

# Инициализация
config = Config.from_yaml("config.yaml")
crawler = Crawler(config)

# Запуск краулинга
async def main():
    session = await crawler.start("https://example.com")

    # Подписка на события
    @session.on_page_crawled
    async def on_page(url, metadata):
        print(f"Обработано: {url}")

    # Ожидание завершения
    await session.wait_for_completion()

    # Получение статистики
    stats = await session.get_statistics()

    # Экспорт
    await session.export("html", "report.html")

asyncio.run(main())
```

### 6. Технологический стек

#### Обязательные зависимости
- **Python 3.14** (минимальная версия)
- **asyncio** - асинхронная обработка
- **aiohttp** - HTTP клиент
- **aiosqlite** - асинхронный SQLite
- **SQLAlchemy 2.x** - ORM (async стиль)
- **Alembic** - миграции БД
- **Playwright** - headless browser для JS
- **BeautifulSoup4** - парсинг HTML
- **lxml** - быстрый XML/HTML парсер
- **Pydantic 2.x** - валидация данных и конфигурации
- **PyYAML** - работа с YAML
- **Typer** или **Click** - CLI интерфейс
- **Rich** - красивый CLI вывод
- **FastAPI** - веб-фреймворк
- **Uvicorn** - ASGI сервер
- **Jinja2** - шаблоны
- **NetworkX** - построение графа
- **Plotly** - визуализация графов
- **ReportLab** - PDF генерация
- **openpyxl** - Excel экспорт
- **python-dotenv** - переменные окружения
- **structlog** - структурированное логирование

#### Опциональные зависимости
- **asyncpg** - PostgreSQL драйвер
- **Redis** (aioredis) - распределённая очередь
- **Celery** - task queue
- **Prometheus client** - метрики
- **Sentry SDK** - мониторинг ошибок

#### Dev зависимости
- **pytest** + **pytest-asyncio** - тестирование
- **pytest-cov** - coverage
- **black** - форматирование кода
- **ruff** - линтер (замена flake8/pylint)
- **mypy** - type checking
- **pre-commit** - git hooks
- **pytest-benchmark** - performance тесты

### 7. Качество кода (Senior уровень)

#### Архитектурные паттерны
- ✅ **Clean Architecture** / Hexagonal Architecture
- ✅ **Repository Pattern** для доступа к данным
- ✅ **Strategy Pattern** для разных типов fetchers (HTTP, JS)
- ✅ **Observer Pattern** для событий краулинга
- ✅ **Factory Pattern** для создания экспортеров
- ✅ **Singleton Pattern** для глобальной конфигурации
- ✅ **Dependency Injection** для тестируемости

#### Best Practices
- ✅ Type hints везде (Python 3.14 typing синтаксис)
- ✅ Docstrings (Google/NumPy стиль) на русском
- ✅ Комментарии к сложной логике на русском
- ✅ SOLID принципы
- ✅ DRY (Don't Repeat Yourself)
- ✅ KISS (Keep It Simple, Stupid)
- ✅ Явное лучше неявного (Zen of Python)
- ✅ Обработка всех исключений
- ✅ Graceful degradation
- ✅ Defensive programming

#### Тестирование
- ✅ Unit тесты (coverage > 85%)
- ✅ Integration тесты
- ✅ Мокирование внешних зависимостей
- ✅ Fixture для тестовых данных
- ✅ Performance тесты (для краулинга миллионов URL)
- ✅ Тесты на race conditions
- ✅ Тесты на memory leaks

#### Безопасность
- ✅ Валидация всех входных данных
- ✅ Защита от SQL injection (через ORM)
- ✅ Защита от path traversal
- ✅ Санитизация URL
- ✅ Ограничение размера загружаемых файлов
- ✅ Таймауты для всех операций
- ✅ Безопасное хранение credentials

#### Performance
- ✅ Профилирование критических участков
- ✅ Оптимизация SQL запросов (индексы, batch inserts)
- ✅ Connection pooling
- ✅ Кеширование где возможно
- ✅ Lazy loading для больших результатов
- ✅ Memory-efficient обработка больших файлов
- ✅ Избежание memory leaks в long-running процессах

### 8. Документация

#### README.md (русский)
- Описание проекта
- Quick Start
- Установка
- Основные примеры использования
- Ссылки на детальную документацию

#### docs/architecture.md
- Детальное описание архитектуры
- Диаграммы компонентов (PlantUML/Mermaid)
- Объяснение ключевых решений
- Паттерны и best practices

#### docs/user_guide.md
- Пошаговые инструкции для пользователей
- Все функции и возможности
- Примеры конфигурации
- Troubleshooting

#### docs/api_reference.md
- Автогенерация из docstrings (Sphinx/MkDocs)
- Полное описание всех публичных API
- Примеры кода

#### docs/deployment.md
- Инструкции по развёртыванию
- Docker/Docker Compose
- Systemd service
- Kubernetes манифесты
- Мониторинг и логирование

#### Комментарии в коде (пример стиля)
```python
async def fetch_page(url: str, session: aiohttp.ClientSession) -> PageResult:
    """
    Асинхронно загружает страницу по указанному URL.

    Функция выполняет HTTP GET запрос с учётом rate limiting,
    обрабатывает редиректы и возвращает метаданные страницы.

    Args:
        url: Абсолютный URL страницы для загрузки
        session: Активная aiohttp сессия для переиспользования соединений

    Returns:
        PageResult: Объект с контентом страницы и метаданными

    Raises:
        HTTPError: При ошибках HTTP (4xx, 5xx)
        TimeoutError: При превышении таймаута запроса
        ConnectionError: При проблемах с сетевым соединением

    Example:
        >>> async with aiohttp.ClientSession() as session:
        ...     result = await fetch_page("https://example.com", session)
        ...     print(result.status_code)  # 200
    """
    # Применяем rate limiting для данного домена
    # чтобы не перегружать сервер и избежать блокировки
    await self.rate_limiter.acquire(url)

    try:
        # Выполняем запрос с настроенным таймаутом
        async with session.get(url, timeout=self.config.timeout) as response:
            # Логируем статус для дебага
            logger.debug(f"Получен ответ {response.status} для {url}")

            # Извлекаем контент
            content = await response.read()

            # Собираем метаданные для статистики
            return PageResult(
                url=str(response.url),  # Может измениться после редиректов
                status_code=response.status,
                headers=dict(response.headers),
                content=content,
                response_time=response.elapsed.total_seconds(),
            )
    except asyncio.TimeoutError:
        # Переупаковываем asyncio исключение в наше
        raise TimeoutError(f"Таймаут при загрузке {url}")
```

### 9. Дополнительные фичи (Nice to have)

#### Расширенная аналитика
- Детектирование битых ссылок (404, 500)
- Анализ SEO метрик (title length, meta descriptions, h1-h6)
- Обнаружение проблем с производительностью (медленные страницы)
- Анализ безопасности (mixed content, устаревшие протоколы)
- Детектирование дубликатов title/description

#### Оптимизации
- Bloom filter для быстрой проверки посещённых URL
- URL frontier с приоритизацией (важные страницы первыми)
- Адаптивный rate limiting (замедление при ошибках 429)
- Intelligent crawling (фокус на важных разделах)
- Incremental crawling (пересмотр только изменённых страниц)

#### Мониторинг
- Prometheus метрики (страниц/сек, ошибок, memory usage)
- Grafana dashboard для визуализации
- Health check endpoint
- Alerting при критических ошибках

#### Экспорт
- Генерация интерактивного HTML отчёта с графиками
- PDF с визуализацией структуры сайта
- Excel с множественными листами (по категориям)
- GraphML для импорта в Gephi/Cytoscape
- Neo4j экспорт для graph database анализа

---

## Приоритеты разработки

### Фаза 1: Ядро (MVP)
1. Базовый асинхронный краулер (aiohttp)
2. SQLite хранилище
3. URL менеджер с дедупликацией
4. Robots.txt парсер
5. Базовая статистика
6. CLI интерфейс
7. Конфигурация через YAML

### Фаза 2: Расширенные возможности
1. JavaScript рендеринг (Playwright)
2. Sitemap парсер
3. Все типы контента
4. Rate limiting
5. Персистентность и возобновление
6. Расширенная статистика
7. Экспорт в JSON/HTML

### Фаза 3: Enterprise функции
1. PostgreSQL миграция
2. Распределённый краулинг
3. Web UI (FastAPI)
4. Real-time мониторинг
5. Визуализация графа
6. PDF/Excel экспорт
7. Библиотека API

### Фаза 4: Оптимизация
1. Performance туning
2. Prometheus metrics
3. Advanced аналитика
4. Bloom filters
5. Incremental crawling
6. Documentation полировка

---

## Метрики успеха

- ✅ Обработка **1M+ страниц** без падений
- ✅ Memory usage < 2GB для 1M URL в очереди
- ✅ Скорость: **100+ страниц/сек** (с rate limiting)
- ✅ Code coverage > **85%**
- ✅ Type coverage > **95%** (mypy strict mode)
- ✅ Zero критичных уязвимостей (Bandit/Safety)
- ✅ Документация: 100% публичных API задокументированы
- ✅ Успешное возобновление после сбоя за < 10 сек

---

## Подтверждённые параметры проекта

1. ✅ **Управление зависимостями**: UV (современный и быстрый менеджер пакетов)
2. ✅ **Docker**: Создать сразу (Dockerfile + docker-compose.yml)
3. ✅ **CI/CD**: GitHub Actions для автотестов, линтеров и сборки
4. ✅ **Лицензия**: MIT License (максимальная свобода для open source)
5. ✅ **Поддержка прокси**: Да, с аутентификацией (HTTP/HTTPS/SOCKS5)
6. ✅ **Лимит размера файлов**: 100 MB (защита от перегрузки памяти)

---

## Примечания для Claude между сессиями

### Текущий статус
- [x] Техническое задание создано и утверждено
- [x] Параметры проекта подтверждены
- [ ] Проект инициализирован (структура директорий)
- [ ] pyproject.toml настроен с UV
- [ ] Базовая конфигурация создана
- [ ] Core модули реализованы
- [ ] Storage слой настроен (SQLAlchemy)
- [ ] Analyzers реализованы
- [ ] Utils готовы
- [ ] CLI интерфейс создан
- [ ] Docker конфигурация готова
- [ ] GitHub Actions настроен
- [ ] Unit тесты написаны
- [ ] Документация создана
- [ ] Фаза 1 MVP завершена

### Следующие шаги
1. ✅ Обновить CLAUDE.md с подтверждёнными параметрами
2. ⏳ Создать структуру проекта (директории и __init__.py файлы)
3. ⏳ Настроить pyproject.toml с UV и всеми зависимостями
4. ⏳ Создать базовую конфигурацию (config.yaml, .env.example)
5. ⏳ Реализовать core модули (crawler, fetcher, parser, url_manager)
6. ⏳ Настроить SQLAlchemy модели и database слой
7. ⏳ Реализовать analyzers (robots, sitemap, content, links)
8. ⏳ Создать utils (config, rate_limiter, logger, validators)
9. ⏳ Реализовать CLI интерфейс (Typer + Rich)
10. ⏳ Создать Dockerfile и docker-compose.yml
11. ⏳ Настроить GitHub Actions для CI/CD
12. ⏳ Написать unit тесты
13. ⏳ Создать README.md и базовую документацию
14. ⏳ Добавить LICENSE (MIT) и .gitignore

### Известные проблемы
_Пока нет_

### Технические решения
- **Менеджер пакетов**: UV для быстрого управления зависимостями
- **Контейнеризация**: Docker Multi-stage build для оптимизации размера образа
- **CI/CD**: GitHub Actions с кешированием зависимостей
- **Лицензия**: MIT для максимальной открытости
- **Прокси**: aiohttp-proxy для поддержки HTTP/HTTPS/SOCKS5 с аутентификацией
- **Лимиты**: 100 MB максимальный размер загружаемого файла

---

**Версия документа**: 1.1
**Дата создания**: 2025-11-18
**Последнее обновление**: 2025-11-18
**Автор**: Claude (Anthropic)
