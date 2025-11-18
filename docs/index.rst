==================================================
Enterprise Web Crawler - Документация
==================================================

.. image:: https://img.shields.io/badge/python-3.14+-blue.svg
   :target: https://python.org
   :alt: Python 3.14+

.. image:: https://img.shields.io/badge/license-MIT-green.svg
   :target: https://opensource.org/licenses/MIT
   :alt: MIT License

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://github.com/psf/black
   :alt: Code Style: Black

Добро пожаловать в документацию **Enterprise Web Crawler** — мощного и масштабируемого веб-краулера для анализа веб-сайтов.

.. toctree::
   :maxdepth: 2
   :caption: Начало работы:

   guides/quickstart
   guides/installation
   guides/configuration

.. toctree::
   :maxdepth: 2
   :caption: Руководства:

   guides/basic_usage
   guides/advanced_usage
   guides/javascript_rendering
   guides/distributed_crawling
   guides/export_formats

.. toctree::
   :maxdepth: 2
   :caption: API Reference:

   api/index

.. toctree::
   :maxdepth: 2
   :caption: Развёртывание:

   guides/docker
   guides/production
   guides/monitoring
   guides/troubleshooting

.. toctree::
   :maxdepth: 1
   :caption: Дополнительно:

   guides/contributing
   guides/changelog
   guides/faq

Возможности
===========

✅ **Асинхронная обработка**
   Миллионы страниц с использованием asyncio и aiohttp

✅ **JavaScript рендеринг**
   Поддержка SPA через Playwright (Chromium, Firefox, WebKit)

✅ **Robots.txt & Sitemap**
   Автоматическое соблюдение правил и оптимизация через sitemap

✅ **Rate Limiting**
   Per-domain адаптивное ограничение с защитой от блокировки

✅ **Дедупликация**
   Bloom filter для O(1) проверки уникальности URL

✅ **Базы данных**
   SQLite и PostgreSQL с асинхронным ORM (SQLAlchemy 2.x)

✅ **Docker Ready**
   Multi-stage builds, docker-compose с PostgreSQL, Redis, Prometheus

✅ **CI/CD**
   GitHub Actions с тестами, линтингом, security scans

✅ **Мониторинг**
   Real-time статистика, WebSocket, Prometheus metrics

Quick Start
===========

Установка
---------

.. code-block:: bash

   # Клонирование репозитория
   git clone https://github.com/yourusername/crawler.git
   cd crawler

   # Установка зависимостей через UV
   uv pip install -e .

   # Или через Docker
   docker-compose up -d

Базовое использование
---------------------

.. code-block:: bash

   # Запуск краулинга
   crawler crawl https://example.com

   # С настройками
   crawler crawl https://example.com \
     --max-pages 1000 \
     --max-depth 3 \
     --javascript

   # Просмотр статистики
   crawler stats <session-id>

Программный API
---------------

.. code-block:: python

   import asyncio
   from webcrawler import Crawler
   from webcrawler.utils.config import Config
   from webcrawler.storage.database import init_db_manager

   async def main():
       # Загрузка конфигурации
       config = Config.from_yaml("config.yaml")

       # Инициализация БД
       db = await init_db_manager(config, create_tables=True)

       # Создание краулера
       crawler = Crawler(config, db)

       # Запуск сессии
       session = await crawler.start_crawl("https://example.com")

       # Подписка на события
       @session.on_event
       def handle_event(event):
           if event.event_type == "page_crawled":
               print(f"Crawled: {event.url}")

       # Ожидание завершения
       await session.wait_for_completion()

       # Статистика
       stats = session.get_statistics()
       print(f"Обработано страниц: {stats.urls_crawled}")

   asyncio.run(main())

Архитектура
===========

Краулер построен на принципах **Clean Architecture** с чёткой модульностью:

.. code-block:: text

   webcrawler/
   ├── core/          # Ядро системы
   │   ├── crawler.py          # Главный движок
   │   ├── fetcher.py          # HTTP клиент
   │   ├── js_fetcher.py       # JavaScript рендеринг
   │   ├── parser.py           # HTML парсер
   │   └── url_manager.py      # Управление URL
   ├── storage/       # Хранилище данных
   │   ├── models.py           # SQLAlchemy модели
   │   ├── database.py         # Database manager
   │   └── repository.py       # Repository pattern
   ├── utils/         # Утилиты
   │   ├── config.py           # Конфигурация
   │   ├── logger.py           # Логирование
   │   ├── validators.py       # Валидация
   │   └── rate_limiter.py     # Rate limiting
   ├── analyzers/     # Анализаторы
   │   ├── robots_parser.py    # robots.txt
   │   └── sitemap_parser.py   # sitemap.xml
   └── cli/           # CLI интерфейс

Основные компоненты
-------------------

**Crawler**
   Главный координатор системы, управляет сессиями краулинга

**Fetcher**
   HTTP клиент с поддержкой rate limiting, retry, proxy

**Parser**
   HTML парсер для извлечения ссылок, метаданных, structured data

**URLManager**
   Очередь URL с Bloom filter дедупликацией

**DatabaseManager**
   Async подключения к SQLite/PostgreSQL с pooling

**RateLimiter**
   Per-domain адаптивное ограничение запросов

Примеры использования
=====================

См. раздел :doc:`guides/basic_usage` для детальных примеров.

Индексы и таблицы
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
