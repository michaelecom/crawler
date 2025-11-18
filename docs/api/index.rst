API Reference
=============

Полная документация по публичному API Enterprise Web Crawler.

.. toctree::
   :maxdepth: 2
   :caption: Модули:

   core
   storage
   analyzers
   export
   utils


Core Modules
------------

Основные модули краулера.

.. autosummary::
   :toctree: generated
   :recursive:

   webcrawler.core.crawler
   webcrawler.core.fetcher
   webcrawler.core.js_fetcher
   webcrawler.core.parser
   webcrawler.core.url_manager
   webcrawler.core.queue_manager
   webcrawler.core.session_manager


Storage Layer
-------------

Слой хранения данных.

.. autosummary::
   :toctree: generated
   :recursive:

   webcrawler.storage.database
   webcrawler.storage.models
   webcrawler.storage.repository


Analyzers
---------

Модули анализа контента.

.. autosummary::
   :toctree: generated
   :recursive:

   webcrawler.analyzers.robots_parser
   webcrawler.analyzers.sitemap_parser
   webcrawler.analyzers.content_analyzer
   webcrawler.analyzers.link_extractor
   webcrawler.analyzers.stats_calculator


Export
------

Экспорт данных.

.. autosummary::
   :toctree: generated
   :recursive:

   webcrawler.export.json_exporter
   webcrawler.export.html_exporter
   webcrawler.export.pdf_exporter
   webcrawler.export.excel_exporter
   webcrawler.export.graph_visualizer


Utilities
---------

Вспомогательные модули.

.. autosummary::
   :toctree: generated
   :recursive:

   webcrawler.utils.config
   webcrawler.utils.rate_limiter
   webcrawler.utils.logger
   webcrawler.utils.validators
   webcrawler.utils.helpers


Quick Links
-----------

Наиболее используемые классы и функции:

Основные классы
~~~~~~~~~~~~~~~

* :class:`webcrawler.core.crawler.Crawler` - Главный класс краулера
* :class:`webcrawler.core.session_manager.CrawlSession` - Сессия краулинга
* :class:`webcrawler.utils.config.Config` - Конфигурация
* :class:`webcrawler.storage.database.DatabaseManager` - Менеджер БД

Конфигурация
~~~~~~~~~~~~

* :func:`webcrawler.utils.config.init_config` - Инициализация конфигурации
* :func:`webcrawler.storage.database.init_db_manager` - Инициализация БД

Экспорт
~~~~~~~

* :class:`webcrawler.export.json_exporter.JSONExporter` - JSON экспорт
* :class:`webcrawler.export.html_exporter.HTMLExporter` - HTML экспорт
* :class:`webcrawler.export.pdf_exporter.PDFExporter` - PDF экспорт
* :class:`webcrawler.export.excel_exporter.ExcelExporter` - Excel экспорт

Repositories
~~~~~~~~~~~~

* :class:`webcrawler.storage.repository.CrawlSessionRepository` - Сессии
* :class:`webcrawler.storage.repository.URLRepository` - URL
* :class:`webcrawler.storage.repository.LinkRepository` - Ссылки
* :class:`webcrawler.storage.repository.ErrorRepository` - Ошибки

Индексы и поиск
---------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
