"""
Главный движок веб-краулера.

Координирует все компоненты системы: загрузку страниц, парсинг,
сохранение в БД, управление очередью URL, соблюдение robots.txt.
"""

import asyncio
import signal
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

from sqlalchemy import select

from webcrawler.analyzers.robots_parser import RobotsParser
from webcrawler.analyzers.sitemap_parser import SitemapParser
from webcrawler.core.fetcher import FetchResult, HTTPFetcher
from webcrawler.core.parser import HTMLParser
from webcrawler.core.url_manager import URLManager
from webcrawler.storage.database import DatabaseManager
from webcrawler.storage.models import CrawlSession as CrawlSessionModel
from webcrawler.storage.models import URL as URLModel
from webcrawler.storage.repository import (
    CrawlSessionRepository,
    ErrorRepository,
    LinkRepository,
    StatisticsRepository,
    URLRepository,
)
from webcrawler.utils.config import Config
from webcrawler.utils.helpers import compute_sha256, format_bytes, format_duration
from webcrawler.utils.logger import LoggerMixin
from webcrawler.utils.rate_limiter import RateLimiter
from webcrawler.utils.validators import is_valid_url, normalize_url


class CrawlStatus(str, Enum):
    """Статусы сессии краулинга."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CrawlStatistics:
    """
    Статистика краулинга в реальном времени.
    """

    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None

    # Счётчики
    urls_discovered: int = 0
    urls_crawled: int = 0
    urls_failed: int = 0
    urls_skipped: int = 0

    # По статус-кодам
    status_2xx: int = 0
    status_3xx: int = 0
    status_4xx: int = 0
    status_5xx: int = 0

    # Производительность
    total_bytes_downloaded: int = 0
    avg_response_time: float = 0.0
    pages_per_second: float = 0.0

    # Ошибки
    errors_count: int = 0

    # Текущий прогресс
    current_depth: int = 0
    current_url: Optional[str] = None

    def update_response_time(self, response_time: float) -> None:
        """
        Обновить среднее время ответа.

        Args:
            response_time: Время ответа в секундах
        """
        if self.urls_crawled == 0:
            self.avg_response_time = response_time
        else:
            # Скользящее среднее
            self.avg_response_time = (
                self.avg_response_time * (self.urls_crawled - 1) + response_time
            ) / self.urls_crawled

    def calculate_pages_per_second(self) -> None:
        """Пересчитать скорость краулинга."""
        if self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
        else:
            duration = (datetime.utcnow() - self.start_time).total_seconds()

        if duration > 0:
            self.pages_per_second = self.urls_crawled / duration

    def to_dict(self) -> dict:
        """Конвертировать в словарь для логирования."""
        return {
            "session_id": self.session_id,
            "urls_discovered": self.urls_discovered,
            "urls_crawled": self.urls_crawled,
            "urls_failed": self.urls_failed,
            "urls_skipped": self.urls_skipped,
            "status_2xx": self.status_2xx,
            "status_3xx": self.status_3xx,
            "status_4xx": self.status_4xx,
            "status_5xx": self.status_5xx,
            "total_bytes": format_bytes(self.total_bytes_downloaded),
            "avg_response_time": f"{self.avg_response_time:.3f}s",
            "pages_per_second": f"{self.pages_per_second:.2f}",
            "current_depth": self.current_depth,
            "current_url": self.current_url,
        }


@dataclass
class CrawlEvent:
    """
    Событие краулинга для callback'ов.
    """

    event_type: str  # page_crawled, error, progress, completed
    url: Optional[str] = None
    status_code: Optional[int] = None
    error: Optional[str] = None
    statistics: Optional[CrawlStatistics] = None
    metadata: dict = field(default_factory=dict)


class Crawler(LoggerMixin):
    """
    Главный движок веб-краулера.

    Координирует все компоненты: fetcher, parser, URL manager, database.
    Управляет жизненным циклом краулинга, событиями и статистикой.

    Example:
        >>> config = Config.from_yaml("config.yaml")
        >>> db = await init_db_manager(config, create_tables=True)
        >>> crawler = Crawler(config, db)
        >>> session = await crawler.start_crawl("https://example.com")
        >>> await session.wait_for_completion()
        >>> stats = session.get_statistics()
        >>> print(f"Crawled {stats.urls_crawled} pages")
    """

    def __init__(self, config: Config, db_manager: DatabaseManager):
        """
        Инициализация краулера.

        Args:
            config: Объект конфигурации
            db_manager: Менеджер базы данных
        """
        self.config = config
        self.db_manager = db_manager

        # Компоненты (инициализируются при старте сессии)
        self.rate_limiter: Optional[RateLimiter] = None
        self.fetcher: Optional[HTTPFetcher] = None

        # Активные сессии краулинга
        self.active_sessions: dict[str, "CrawlSession"] = {}

        # Graceful shutdown
        self.shutdown_event = asyncio.Event()

        self.logger.info("crawler_initialized", config_file=config.config_file)

    async def start_crawl(
        self,
        start_url: str,
        session_id: Optional[str] = None,
        **kwargs,
    ) -> "CrawlSession":
        """
        Запустить новую сессию краулинга.

        Args:
            start_url: Начальный URL для краулинга
            session_id: ID сессии (если не указан, генерируется автоматически)
            **kwargs: Дополнительные параметры (max_depth, max_pages, etc.)

        Returns:
            CrawlSession: Объект сессии краулинга

        Raises:
            ValueError: Если start_url невалиден

        Example:
            >>> session = await crawler.start_crawl(
            ...     "https://example.com",
            ...     max_depth=3,
            ...     max_pages=1000
            ... )
        """
        # Валидация URL
        if not is_valid_url(start_url):
            raise ValueError(f"Invalid start URL: {start_url}")

        # Нормализация URL
        start_url = normalize_url(start_url)

        # Генерация session_id если не указан
        if not session_id:
            import uuid

            session_id = f"crawl_{uuid.uuid4().hex[:16]}"

        # Проверка что сессия не существует
        if session_id in self.active_sessions:
            raise ValueError(f"Session {session_id} already running")

        # Инициализация компонентов (если ещё не инициализированы)
        if not self.rate_limiter:
            self.rate_limiter = RateLimiter(
                requests_per_second=self.config.rate_limiting.requests_per_second,
                max_concurrent_requests=self.config.rate_limiting.max_concurrent_requests,
                adaptive=self.config.rate_limiting.adaptive_delays,
            )

        if not self.fetcher:
            self.fetcher = HTTPFetcher(self.config, self.rate_limiter)
            await self.fetcher.start()

        # Создание сессии краулинга
        crawl_session = CrawlSession(
            session_id=session_id,
            start_url=start_url,
            config=self.config,
            db_manager=self.db_manager,
            rate_limiter=self.rate_limiter,
            fetcher=self.fetcher,
            **kwargs,
        )

        # Регистрация сессии
        self.active_sessions[session_id] = crawl_session

        # Запуск сессии в фоне
        asyncio.create_task(crawl_session.run())

        self.logger.info(
            "crawl_session_started", session_id=session_id, start_url=start_url
        )

        return crawl_session

    async def resume_crawl(self, session_id: str) -> "CrawlSession":
        """
        Возобновить ранее остановленную сессию.

        Args:
            session_id: ID сессии для возобновления

        Returns:
            CrawlSession: Возобновлённая сессия

        Raises:
            ValueError: Если сессия не найдена или не может быть возобновлена

        Example:
            >>> session = await crawler.resume_crawl("crawl_abc123")
        """
        # Проверка что сессия не активна
        if session_id in self.active_sessions:
            return self.active_sessions[session_id]

        # Загрузка сессии из БД
        async with self.db_manager.session() as db_session:
            session_repo = CrawlSessionRepository(db_session)
            db_crawl_session = await session_repo.get_by_session_id(session_id)

            if not db_crawl_session:
                raise ValueError(f"Session {session_id} not found")

            if db_crawl_session.status not in [
                CrawlStatus.PAUSED,
                CrawlStatus.FAILED,
            ]:
                raise ValueError(
                    f"Cannot resume session with status {db_crawl_session.status}"
                )

            start_url = db_crawl_session.start_url

        # Создание сессии
        crawl_session = await self.start_crawl(
            start_url=start_url,
            session_id=session_id,
            resume=True,
        )

        self.logger.info("crawl_session_resumed", session_id=session_id)

        return crawl_session

    async def stop_all_sessions(self) -> None:
        """
        Остановить все активные сессии (graceful shutdown).

        Example:
            >>> await crawler.stop_all_sessions()
        """
        self.logger.info("stopping_all_sessions", count=len(self.active_sessions))

        # Сигнал shutdown
        self.shutdown_event.set()

        # Остановка всех сессий
        tasks = []
        for session in self.active_sessions.values():
            tasks.append(session.stop())

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # Закрытие fetcher
        if self.fetcher:
            await self.fetcher.close()

        self.active_sessions.clear()

        self.logger.info("all_sessions_stopped")

    async def get_session(self, session_id: str) -> Optional["CrawlSession"]:
        """
        Получить активную сессию по ID.

        Args:
            session_id: ID сессии

        Returns:
            Optional[CrawlSession]: Сессия или None если не найдена
        """
        return self.active_sessions.get(session_id)

    def setup_signal_handlers(self) -> None:
        """
        Настроить обработчики сигналов для graceful shutdown.

        Example:
            >>> crawler.setup_signal_handlers()
        """

        def signal_handler(signum, frame):
            """Обработчик SIGINT/SIGTERM."""
            self.logger.info("signal_received", signal=signum)
            asyncio.create_task(self.stop_all_sessions())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        self.logger.debug("signal_handlers_configured")


class CrawlSession(LoggerMixin):
    """
    Сессия краулинга для одного start_url.

    Управляет жизненным циклом краулинга: запуск, пауза, возобновление, остановка.
    Координирует все компоненты и собирает статистику.
    """

    def __init__(
        self,
        session_id: str,
        start_url: str,
        config: Config,
        db_manager: DatabaseManager,
        rate_limiter: RateLimiter,
        fetcher: HTTPFetcher,
        max_depth: Optional[int] = None,
        max_pages: Optional[int] = None,
        resume: bool = False,
        **kwargs,
    ):
        """
        Инициализация сессии краулинга.

        Args:
            session_id: Уникальный ID сессии
            start_url: Начальный URL
            config: Конфигурация
            db_manager: Менеджер БД
            rate_limiter: Rate limiter
            fetcher: HTTP fetcher
            max_depth: Максимальная глубина (override config)
            max_pages: Максимум страниц (override config)
            resume: Возобновление существующей сессии
            **kwargs: Дополнительные параметры
        """
        self.session_id = session_id
        self.start_url = start_url
        self.config = config
        self.db_manager = db_manager
        self.rate_limiter = rate_limiter
        self.fetcher = fetcher

        # Параметры краулинга (с возможностью override)
        self.max_depth = max_depth or config.crawler.max_depth
        self.max_pages = max_pages or config.crawler.max_pages
        self.resume = resume

        # URL менеджер
        self.url_manager = URLManager(config, start_url)

        # Repositories
        self.session_repo: Optional[CrawlSessionRepository] = None
        self.url_repo: Optional[URLRepository] = None
        self.link_repo: Optional[LinkRepository] = None
        self.error_repo: Optional[ErrorRepository] = None
        self.stats_repo: Optional[StatisticsRepository] = None

        # ID сессии в БД
        self.db_session_id: Optional[int] = None

        # Статистика
        self.statistics = CrawlStatistics(
            session_id=session_id, start_time=datetime.utcnow()
        )

        # Robots.txt парсер (кеш по доменам)
        self.robots_parsers: dict[str, RobotsParser] = {}

        # Статус сессии
        self.status = CrawlStatus.PENDING
        self.pause_event = asyncio.Event()
        self.pause_event.set()  # Изначально не на паузе

        # Checkpoint
        self.last_checkpoint_time = time.time()
        self.checkpoint_interval = config.performance.checkpoint_interval

        # Event callbacks
        self.event_callbacks: list[Callable[[CrawlEvent], None]] = []

        # Флаг для остановки
        self.stop_requested = False

        self.logger.info(
            "crawl_session_initialized",
            session_id=session_id,
            start_url=start_url,
            max_depth=self.max_depth,
            max_pages=self.max_pages,
        )

    async def run(self) -> None:
        """
        Главный цикл краулинга.

        Обрабатывает URL из очереди, сохраняет результаты,
        управляет checkpoint'ами и статистикой.
        """
        try:
            # Инициализация сессии в БД
            await self._initialize_db_session()

            # Обновление статуса
            self.status = CrawlStatus.RUNNING
            await self._update_session_status(CrawlStatus.RUNNING)

            # Если не resume, добавляем start_url в очередь
            if not self.resume:
                await self.url_manager.add_url(self.start_url, depth=0)
                self.statistics.urls_discovered += 1
            else:
                # При resume загружаем pending URLs из БД
                await self._load_pending_urls()

            # Парсинг robots.txt и sitemap для start_url
            await self._process_robots_and_sitemap(self.start_url)

            # Главный цикл краулинга
            while self.url_manager.should_continue_crawling() and not self.stop_requested:
                # Проверка паузы
                await self.pause_event.wait()

                # Проверка лимита страниц
                if self.max_pages > 0 and self.statistics.urls_crawled >= self.max_pages:
                    self.logger.info(
                        "max_pages_reached",
                        max_pages=self.max_pages,
                        crawled=self.statistics.urls_crawled,
                    )
                    break

                # Получение следующего URL
                url_item = await self.url_manager.get_next_url()
                if not url_item:
                    break

                # Обработка URL
                await self._process_url(url_item.url, url_item.depth)

                # Checkpoint
                await self._checkpoint_if_needed()

            # Завершение
            self.status = CrawlStatus.COMPLETED
            self.statistics.end_time = datetime.utcnow()
            self.statistics.calculate_pages_per_second()

            await self._update_session_status(CrawlStatus.COMPLETED)
            await self._finalize_statistics()

            # Event: завершение
            await self._emit_event(
                CrawlEvent(event_type="completed", statistics=self.statistics)
            )

            self.logger.info(
                "crawl_session_completed",
                session_id=self.session_id,
                statistics=self.statistics.to_dict(),
            )

        except Exception as e:
            self.status = CrawlStatus.FAILED
            self.statistics.end_time = datetime.utcnow()

            await self._update_session_status(CrawlStatus.FAILED, error_message=str(e))

            self.logger.error(
                "crawl_session_failed",
                session_id=self.session_id,
                error=str(e),
                error_type=type(e).__name__,
            )

            # Event: ошибка
            await self._emit_event(
                CrawlEvent(event_type="error", error=str(e), statistics=self.statistics)
            )

            raise

    async def _process_url(self, url: str, depth: int) -> None:
        """
        Обработать один URL: загрузить, распарсить, сохранить.

        Args:
            url: URL для обработки
            depth: Глубина от start_url
        """
        self.statistics.current_url = url
        self.statistics.current_depth = depth

        try:
            # Проверка robots.txt
            if not await self._check_robots_allowed(url):
                self.logger.debug("url_disallowed_by_robots", url=url)
                self.statistics.urls_skipped += 1
                return

            # Загрузка страницы
            fetch_result = await self.fetcher.fetch(url)

            # Обновление статистики
            self.statistics.urls_crawled += 1
            self.statistics.total_bytes_downloaded += len(fetch_result.content)
            self.statistics.update_response_time(fetch_result.response_time)

            # Счётчик по статус-кодам
            if 200 <= fetch_result.status_code < 300:
                self.statistics.status_2xx += 1
            elif 300 <= fetch_result.status_code < 400:
                self.statistics.status_3xx += 1
            elif 400 <= fetch_result.status_code < 500:
                self.statistics.status_4xx += 1
            elif 500 <= fetch_result.status_code < 600:
                self.statistics.status_5xx += 1

            # Сохранение URL в БД
            url_id = await self._save_url_to_db(url, fetch_result, depth)

            # Если успешная загрузка, парсим HTML и извлекаем ссылки
            if fetch_result.is_successful and url_id:
                await self._parse_and_extract_links(fetch_result, url_id, depth)

            # Event: страница обработана
            await self._emit_event(
                CrawlEvent(
                    event_type="page_crawled",
                    url=url,
                    status_code=fetch_result.status_code,
                    metadata={
                        "depth": depth,
                        "response_time": fetch_result.response_time,
                        "content_size": len(fetch_result.content),
                    },
                    statistics=self.statistics,
                )
            )

        except Exception as e:
            self.statistics.urls_failed += 1
            self.statistics.errors_count += 1

            # Сохранение ошибки в БД
            await self._save_error_to_db(url, e)

            self.logger.warning(
                "url_processing_failed",
                url=url,
                error=str(e),
                error_type=type(e).__name__,
            )

            # Event: ошибка обработки URL
            await self._emit_event(
                CrawlEvent(
                    event_type="error",
                    url=url,
                    error=str(e),
                    statistics=self.statistics,
                )
            )

    async def _parse_and_extract_links(
        self, fetch_result: FetchResult, source_url_id: int, current_depth: int
    ) -> None:
        """
        Распарсить HTML и извлечь ссылки.

        Args:
            fetch_result: Результат загрузки страницы
            source_url_id: ID source URL в БД
            current_depth: Текущая глубина
        """
        # Проверка Content-Type
        content_type = fetch_result.headers.get("content-type", "")
        if not content_type.startswith("text/html"):
            self.logger.debug(
                "skipping_non_html_content",
                url=fetch_result.url,
                content_type=content_type,
            )
            return

        try:
            # Парсинг HTML
            parser = HTMLParser(base_url=fetch_result.url)
            parsed_page = parser.parse(fetch_result.content)

            # Обновление метаданных URL в БД
            await self._update_url_metadata(source_url_id, parsed_page)

            # Извлечение и обработка ссылок
            for link in parsed_page.links:
                # Пропускаем external ссылки если настроено
                if link.is_external and not self.config.crawler.include_external_links:
                    continue

                # Пропускаем nofollow ссылки если настроено
                if link.is_nofollow and not self.config.crawler.follow_nofollow_links:
                    continue

                # Добавление URL в очередь
                new_depth = current_depth + 1
                added = await self.url_manager.add_url(link.url, depth=new_depth)

                if added:
                    self.statistics.urls_discovered += 1

                # Сохранение связи (link) в БД
                await self._save_link_to_db(
                    source_url_id=source_url_id,
                    target_url=link.url,
                    link_data=link,
                )

        except Exception as e:
            self.logger.warning(
                "html_parsing_failed",
                url=fetch_result.url,
                error=str(e),
                error_type=type(e).__name__,
            )

    async def _check_robots_allowed(self, url: str) -> bool:
        """
        Проверить разрешён ли URL в robots.txt.

        Args:
            url: URL для проверки

        Returns:
            bool: True если разрешён
        """
        if not self.config.robots.obey_robots:
            return True

        from urllib.parse import urlparse

        domain = urlparse(url).netloc

        # Получаем или создаём robots parser для домена
        if domain not in self.robots_parsers:
            robots_parser = RobotsParser(
                base_url=f"https://{domain}",
                user_agent=self.config.robots.user_agent,
            )
            await robots_parser.fetch()
            self.robots_parsers[domain] = robots_parser

        robots = self.robots_parsers[domain]
        return robots.can_fetch(url)

    async def _process_robots_and_sitemap(self, url: str) -> None:
        """
        Обработать robots.txt и sitemap.xml для домена.

        Args:
            url: URL для извлечения домена
        """
        from urllib.parse import urlparse

        domain = urlparse(url).netloc
        base_url = f"https://{domain}"

        try:
            # Robots.txt
            robots = RobotsParser(base_url, self.config.robots.user_agent)
            await robots.fetch()

            # Получаем sitemap URLs из robots.txt
            sitemap_urls = robots.get_sitemaps()

            # Если не нашли, пробуем стандартные пути
            if not sitemap_urls and self.config.sitemap.auto_discover:
                sitemap_urls = [
                    f"{base_url}/sitemap.xml",
                    f"{base_url}/sitemap_index.xml",
                ]

            # Парсинг sitemap
            if sitemap_urls and self.config.sitemap.enabled:
                sitemap_parser = SitemapParser(
                    timeout=self.config.sitemap.timeout,
                    max_urls=self.config.sitemap.max_urls,
                )

                all_sitemap_urls = await sitemap_parser.fetch_all_sitemaps(
                    sitemap_urls
                )

                # Добавляем URL из sitemap в очередь с приоритетом
                for sitemap_url in all_sitemap_urls:
                    await self.url_manager.add_url(sitemap_url.loc, depth=0)
                    self.statistics.urls_discovered += 1

                self.logger.info(
                    "sitemap_processed",
                    domain=domain,
                    urls_from_sitemap=len(all_sitemap_urls),
                )

        except Exception as e:
            self.logger.warning(
                "robots_sitemap_processing_failed",
                domain=domain,
                error=str(e),
            )

    async def _initialize_db_session(self) -> None:
        """Инициализировать сессию в базе данных."""
        async with self.db_manager.session() as db_session:
            self.session_repo = CrawlSessionRepository(db_session)

            if not self.resume:
                # Создание новой сессии
                crawl_session = await self.session_repo.create(
                    session_id=self.session_id,
                    start_url=self.start_url,
                    max_depth=self.max_depth,
                    max_pages=self.max_pages,
                    include_subdomains=self.config.crawler.include_subdomains,
                    enable_javascript=self.config.crawler.enable_javascript,
                    config=self.config.model_dump(),
                )
                self.db_session_id = crawl_session.id
            else:
                # Загрузка существующей сессии
                crawl_session = await self.session_repo.get_by_session_id(
                    self.session_id
                )
                if crawl_session:
                    self.db_session_id = crawl_session.id

        self.logger.debug(
            "db_session_initialized",
            session_id=self.session_id,
            db_session_id=self.db_session_id,
        )

    async def _save_url_to_db(
        self, url: str, fetch_result: FetchResult, depth: int
    ) -> Optional[int]:
        """
        Сохранить URL в базу данных.

        Args:
            url: URL
            fetch_result: Результат загрузки
            depth: Глубина

        Returns:
            Optional[int]: ID созданного/обновлённого URL
        """
        async with self.db_manager.session() as db_session:
            url_repo = URLRepository(db_session)

            # Вычисление хеша
            from webcrawler.utils.helpers import compute_url_hash

            url_hash = compute_url_hash(url)

            # Проверка существования
            existing_url = await url_repo.get_by_url_hash(self.db_session_id, url_hash)

            if existing_url:
                # Инкремент счётчика посещений
                await url_repo.increment_visit_count(existing_url.id)
                return existing_url.id

            # Создание нового URL
            from urllib.parse import urlparse

            parsed = urlparse(url)

            url_model = await url_repo.create(
                session_id=self.db_session_id,
                url=url,
                depth=depth,
                domain=parsed.netloc,
                http_status_code=fetch_result.status_code,
                content_type=fetch_result.headers.get("content-type"),
                content_length=len(fetch_result.content),
                response_time=fetch_result.response_time,
                headers=fetch_result.headers,
                redirect_url=fetch_result.redirect_chain[-1]
                if fetch_result.redirect_chain
                else None,
                redirect_chain=fetch_result.redirect_chain,
                ssl_version=fetch_result.ssl_info.get("version")
                if fetch_result.ssl_info
                else None,
                ssl_cipher=fetch_result.ssl_info.get("cipher")
                if fetch_result.ssl_info
                else None,
            )

            return url_model.id

    async def _update_url_metadata(self, url_id: int, parsed_page) -> None:
        """
        Обновить метаданные URL после парсинга.

        Args:
            url_id: ID URL в БД
            parsed_page: Результат парсинга
        """
        async with self.db_manager.session() as db_session:
            url_repo = URLRepository(db_session)

            # Вычисление content hash
            content_hash = None
            if parsed_page.title:
                content_hash = compute_sha256(parsed_page.title)

            await url_repo.update_metadata(
                url_id=url_id,
                title=parsed_page.title,
                meta_description=parsed_page.meta_description,
                meta_keywords=parsed_page.meta_keywords,
                meta_robots=parsed_page.meta_robots,
                language=parsed_page.language,
                has_schema_org=parsed_page.has_schema_org,
                has_open_graph=parsed_page.has_open_graph,
                structured_data=parsed_page.structured_data,
                internal_links_count=parsed_page.internal_links_count,
                external_links_count=parsed_page.external_links_count,
                content_hash=content_hash,
                canonical_url=parsed_page.canonical_url,
            )

    async def _save_link_to_db(
        self, source_url_id: int, target_url: str, link_data
    ) -> None:
        """
        Сохранить связь между URL в БД.

        Args:
            source_url_id: ID source URL
            target_url: Target URL
            link_data: Данные о ссылке (ParsedLink)
        """
        async with self.db_manager.session() as db_session:
            url_repo = URLRepository(db_session)
            link_repo = LinkRepository(db_session)

            # Получаем или создаём target URL
            from webcrawler.utils.helpers import compute_url_hash

            target_hash = compute_url_hash(target_url)
            target_url_model = await url_repo.get_by_url_hash(
                self.db_session_id, target_hash
            )

            if not target_url_model:
                # Создаём target URL (pending)
                from urllib.parse import urlparse

                parsed = urlparse(target_url)
                target_url_model = await url_repo.create(
                    session_id=self.db_session_id,
                    url=target_url,
                    depth=0,  # Будет обновлено при краулинге
                    domain=parsed.netloc,
                )

            # Создаём связь
            try:
                await link_repo.create(
                    session_id=self.db_session_id,
                    source_url_id=source_url_id,
                    target_url_id=target_url_model.id,
                    link_type=link_data.link_type,
                    anchor_text=link_data.anchor_text,
                    rel_attribute=link_data.rel,
                    is_nofollow=link_data.is_nofollow,
                )
            except Exception as e:
                # Может быть duplicate constraint violation (это OK)
                self.logger.debug(
                    "link_creation_skipped", source=source_url_id, target=target_url
                )

    async def _save_error_to_db(self, url: str, error: Exception) -> None:
        """
        Сохранить ошибку в БД.

        Args:
            url: URL с ошибкой
            error: Исключение
        """
        async with self.db_manager.session() as db_session:
            error_repo = ErrorRepository(db_session)

            import traceback

            await error_repo.create(
                session_id=self.db_session_id,
                url=url,
                error_type=type(error).__name__,
                error_message=str(error),
                error_details={"traceback": traceback.format_exc()},
            )

    async def _update_session_status(
        self, status: CrawlStatus, error_message: Optional[str] = None
    ) -> None:
        """
        Обновить статус сессии в БД.

        Args:
            status: Новый статус
            error_message: Сообщение об ошибке (опционально)
        """
        async with self.db_manager.session() as db_session:
            session_repo = CrawlSessionRepository(db_session)

            await session_repo.update_status(
                session_id=self.db_session_id,
                status=status.value,
                error_message=error_message,
            )

            # Обновление статистики
            await session_repo.update_stats(
                session_id=self.db_session_id,
                total_urls_discovered=self.statistics.urls_discovered,
                total_urls_crawled=self.statistics.urls_crawled,
                total_urls_failed=self.statistics.urls_failed,
                total_bytes_downloaded=self.statistics.total_bytes_downloaded,
            )

    async def _finalize_statistics(self) -> None:
        """Сохранить финальную статистику в БД."""
        async with self.db_manager.session() as db_session:
            stats_repo = StatisticsRepository(db_session)

            await stats_repo.update_statistics(
                session_id=self.db_session_id,
                total_urls=self.statistics.urls_discovered,
                total_pages_crawled=self.statistics.urls_crawled,
                total_errors=self.statistics.errors_count,
                status_2xx_count=self.statistics.status_2xx,
                status_3xx_count=self.statistics.status_3xx,
                status_4xx_count=self.statistics.status_4xx,
                status_5xx_count=self.statistics.status_5xx,
                avg_response_time=self.statistics.avg_response_time,
                total_bytes_downloaded=self.statistics.total_bytes_downloaded,
                pages_per_second=self.statistics.pages_per_second,
            )

    async def _checkpoint_if_needed(self) -> None:
        """Сохранить checkpoint если прошло достаточно времени."""
        current_time = time.time()

        if current_time - self.last_checkpoint_time >= self.checkpoint_interval:
            await self._update_session_status(self.status)
            self.last_checkpoint_time = current_time

            self.logger.debug(
                "checkpoint_saved",
                session_id=self.session_id,
                urls_crawled=self.statistics.urls_crawled,
            )

    async def _load_pending_urls(self) -> None:
        """Загрузить pending URLs из БД при resume."""
        async with self.db_manager.session() as db_session:
            url_repo = URLRepository(db_session)

            pending_urls = await url_repo.get_pending_urls(
                session_id=self.db_session_id, limit=10000
            )

            for url_model in pending_urls:
                await self.url_manager.add_url(url_model.url, depth=url_model.depth)
                self.statistics.urls_discovered += 1

            self.logger.info(
                "pending_urls_loaded",
                session_id=self.session_id,
                count=len(pending_urls),
            )

    async def _emit_event(self, event: CrawlEvent) -> None:
        """
        Отправить событие всем подписчикам.

        Args:
            event: Событие краулинга
        """
        for callback in self.event_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                self.logger.warning("event_callback_failed", error=str(e))

    def on_event(self, callback: Callable[[CrawlEvent], None]) -> None:
        """
        Подписаться на события краулинга.

        Args:
            callback: Функция-обработчик события

        Example:
            >>> def on_page(event: CrawlEvent):
            ...     print(f"Crawled: {event.url}")
            >>> session.on_event(on_page)
        """
        self.event_callbacks.append(callback)

    async def pause(self) -> None:
        """
        Приостановить краулинг.

        Example:
            >>> await session.pause()
        """
        self.pause_event.clear()
        self.status = CrawlStatus.PAUSED
        await self._update_session_status(CrawlStatus.PAUSED)

        self.logger.info("crawl_session_paused", session_id=self.session_id)

    async def resume_session(self) -> None:
        """
        Возобновить приостановленный краулинг.

        Example:
            >>> await session.resume_session()
        """
        self.pause_event.set()
        self.status = CrawlStatus.RUNNING
        await self._update_session_status(CrawlStatus.RUNNING)

        self.logger.info("crawl_session_resumed", session_id=self.session_id)

    async def stop(self) -> None:
        """
        Остановить краулинг (graceful shutdown).

        Example:
            >>> await session.stop()
        """
        self.stop_requested = True
        self.pause_event.set()  # Разблокировать если на паузе

        # Ожидание завершения текущих операций
        await asyncio.sleep(1)

        self.status = CrawlStatus.PAUSED
        await self._update_session_status(CrawlStatus.PAUSED)

        self.logger.info("crawl_session_stopped", session_id=self.session_id)

    async def wait_for_completion(self) -> None:
        """
        Ожидать завершения краулинга.

        Example:
            >>> await session.wait_for_completion()
            >>> print("Crawling completed!")
        """
        while self.status in [CrawlStatus.PENDING, CrawlStatus.RUNNING]:
            await asyncio.sleep(1)

    def get_statistics(self) -> CrawlStatistics:
        """
        Получить текущую статистику.

        Returns:
            CrawlStatistics: Объект статистики

        Example:
            >>> stats = session.get_statistics()
            >>> print(f"Pages crawled: {stats.urls_crawled}")
        """
        self.statistics.calculate_pages_per_second()
        return self.statistics
