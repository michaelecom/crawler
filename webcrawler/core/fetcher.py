"""
Асинхронный HTTP fetcher для загрузки веб-страниц.

Использует aiohttp для производительных async HTTP запросов
с поддержкой прокси, SSL/TLS, редиректов и retry механизма.
"""

import asyncio
import ssl
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import aiohttp
import certifi

from webcrawler.utils.config import Config
from webcrawler.utils.helpers import retry_with_backoff
from webcrawler.utils.logger import LoggerMixin
from webcrawler.utils.rate_limiter import RateLimiter
from webcrawler.utils.validators import sanitize_url, validate_content_type


@dataclass
class FetchResult:
    """
    Результат загрузки страницы.

    Содержит контент и метаданные HTTP ответа.
    """

    url: str
    status_code: int
    content: bytes
    headers: dict[str, str]
    content_type: str
    encoding: Optional[str] = None
    response_time: float = 0.0
    download_time: float = 0.0
    final_url: str = field(default="")  # После редиректов
    redirect_chain: list[str] = field(default_factory=list)
    ssl_info: Optional[dict] = None
    error: Optional[str] = None

    @property
    def is_successful(self) -> bool:
        """Проверить, был ли запрос успешным."""
        return 200 <= self.status_code < 300

    @property
    def is_redirect(self) -> bool:
        """Проверить, был ли редирект."""
        return 300 <= self.status_code < 400

    @property
    def is_client_error(self) -> bool:
        """Проверить, клиентская ли ошибка (4xx)."""
        return 400 <= self.status_code < 500

    @property
    def is_server_error(self) -> bool:
        """Проверить, серверная ли ошибка (5xx)."""
        return 500 <= self.status_code < 600

    @property
    def content_length(self) -> int:
        """Получить размер контента в байтах."""
        return len(self.content)


class HTTPFetcher(LoggerMixin):
    """
    Асинхронный HTTP fetcher для загрузки страниц.

    Обеспечивает:
    - Асинхронные HTTP/HTTPS запросы через aiohttp
    - Rate limiting (через RateLimiter)
    - Обработку прокси
    - SSL/TLS поддержку
    - Retry механизм с exponential backoff
    - Сбор метаданных (заголовки, время ответа, SSL info)

    Example:
        >>> config = Config.from_yaml("config.yaml")
        >>> rate_limiter = RateLimiter(requests_per_second=5)
        >>> fetcher = HTTPFetcher(config, rate_limiter)
        >>> await fetcher.start()
        >>>
        >>> result = await fetcher.fetch("https://example.com")
        >>> if result.is_successful:
        ...     print(f"Downloaded {result.content_length} bytes")
        >>>
        >>> await fetcher.close()
    """

    def __init__(self, config: Config, rate_limiter: RateLimiter):
        """
        Инициализация HTTP fetcher.

        Args:
            config: Конфигурация приложения
            rate_limiter: Rate limiter для контроля частоты запросов
        """
        self.config = config
        self.rate_limiter = rate_limiter
        self.session: Optional[aiohttp.ClientSession] = None

        # Статистика
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_bytes_downloaded": 0,
            "total_response_time": 0.0,
        }

        self.logger.info(
            "http_fetcher_initialized",
            timeout=config.rate_limiting.request_timeout,
            max_retries=config.rate_limiting.max_retries,
        )

    async def start(self) -> None:
        """
        Запустить HTTP fetcher и создать aiohttp session.

        Должно вызываться перед использованием fetcher.

        Example:
            >>> fetcher = HTTPFetcher(config, rate_limiter)
            >>> await fetcher.start()
        """
        if self.session:
            self.logger.warning("http_fetcher_already_started")
            return

        # Настройка SSL контекста
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED

        # Настройка TCP connector
        connector = aiohttp.TCPConnector(
            limit=self.config.rate_limiting.max_concurrent_requests,
            limit_per_host=10,  # Максимум соединений на хост
            ttl_dns_cache=300,  # Кеш DNS на 5 минут
            ssl=ssl_context,
            enable_cleanup_closed=True,
        )

        # Настройка timeout
        timeout = aiohttp.ClientTimeout(
            total=self.config.rate_limiting.request_timeout,
            connect=10,  # Таймаут подключения
            sock_read=30,  # Таймаут чтения сокета
        )

        # Настройка прокси
        proxy = self.config.get_proxy_url() if self.config.proxy.enabled else None
        if proxy:
            self.logger.info("http_fetcher_using_proxy", proxy=proxy.split("@")[-1])

        # Создаём session
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={"User-Agent": self.config.robots.custom_user_agent},
            trust_env=True,  # Использовать переменные окружения для прокси
        )

        self.logger.info("http_fetcher_started")

    async def close(self) -> None:
        """
        Закрыть HTTP fetcher и освободить ресурсы.

        Должно вызываться при завершении работы.

        Example:
            >>> await fetcher.close()
        """
        if self.session:
            await self.session.close()
            self.session = None
            self.logger.info("http_fetcher_closed")

    @retry_with_backoff(max_retries=3, backoff_factor=2.0, initial_delay=1.0)
    async def fetch(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[dict] = None,
        allow_redirects: bool = True,
    ) -> FetchResult:
        """
        Загрузить страницу по URL.

        Args:
            url: URL для загрузки
            method: HTTP метод (GET, POST, HEAD, etc.)
            headers: Дополнительные заголовки
            allow_redirects: Следовать ли редиректам

        Returns:
            FetchResult: Результат загрузки

        Raises:
            RuntimeError: Если fetcher не запущен
            aiohttp.ClientError: При ошибках HTTP

        Example:
            >>> result = await fetcher.fetch("https://example.com")
            >>> print(result.status_code, result.content_type)
            200 text/html
        """
        if not self.session:
            raise RuntimeError("HTTPFetcher не запущен. Вызовите start() перед использованием.")

        # Санитизация URL
        url = sanitize_url(url)

        # Rate limiting
        async with self.rate_limiter.acquire(url):
            start_time = asyncio.get_event_loop().time()
            redirect_chain = []

            try:
                # Подготовка заголовков
                request_headers = {
                    "Accept": "*/*",
                    "Accept-Encoding": "gzip, deflate",
                    "Connection": "keep-alive",
                }
                if headers:
                    request_headers.update(headers)

                # Выполняем запрос
                async with self.session.request(
                    method=method,
                    url=url,
                    headers=request_headers,
                    allow_redirects=allow_redirects,
                    max_redirects=10,
                ) as response:
                    response_time = asyncio.get_event_loop().time() - start_time

                    # Собираем редиректы
                    if response.history:
                        redirect_chain = [str(r.url) for r in response.history]

                    # Загружаем контент
                    download_start = asyncio.get_event_loop().time()

                    # Проверяем размер контента
                    content_length = response.headers.get("Content-Length")
                    if content_length:
                        content_length = int(content_length)
                        if content_length > self.config.crawler.max_file_size:
                            self.logger.warning(
                                "content_too_large",
                                url=url,
                                size=content_length,
                                limit=self.config.crawler.max_file_size,
                            )
                            raise ValueError(f"Content too large: {content_length} bytes")

                    # Читаем контент
                    content = await response.read()
                    download_time = asyncio.get_event_loop().time() - download_start

                    # Проверяем фактический размер
                    if len(content) > self.config.crawler.max_file_size:
                        self.logger.warning(
                            "downloaded_content_too_large", url=url, size=len(content)
                        )
                        raise ValueError(f"Downloaded content too large: {len(content)} bytes")

                    # Собираем SSL информацию
                    ssl_info = None
                    if response.connection and response.connection.transport:
                        ssl_obj = response.connection.transport.get_extra_info("ssl_object")
                        if ssl_obj:
                            ssl_info = {
                                "version": ssl_obj.version(),
                                "cipher": ssl_obj.cipher()[0] if ssl_obj.cipher() else None,
                            }

                    # Создаём результат
                    result = FetchResult(
                        url=url,
                        status_code=response.status,
                        content=content,
                        headers=dict(response.headers),
                        content_type=response.headers.get("Content-Type", "").split(";")[0].strip(),
                        encoding=response.charset,
                        response_time=response_time,
                        download_time=download_time,
                        final_url=str(response.url),
                        redirect_chain=redirect_chain,
                        ssl_info=ssl_info,
                    )

                    # Обновляем статистику
                    self.stats["total_requests"] += 1
                    if result.is_successful:
                        self.stats["successful_requests"] += 1
                        self.stats["total_bytes_downloaded"] += len(content)
                    else:
                        self.stats["failed_requests"] += 1

                    self.stats["total_response_time"] += response_time

                    self.logger.debug(
                        "page_fetched",
                        url=url,
                        status=response.status,
                        size=len(content),
                        response_time=round(response_time, 3),
                    )

                    # Адаптивный rate limiting
                    if response.status == 429:  # Too Many Requests
                        self.rate_limiter.report_blocked(url)
                    elif response.status >= 500:
                        self.rate_limiter.adjust_delay(url, increase=True)

                    return result

            except asyncio.TimeoutError as e:
                self.logger.error("fetch_timeout", url=url, timeout=self.config.rate_limiting.request_timeout)
                self.stats["failed_requests"] += 1
                raise

            except aiohttp.ClientError as e:
                self.logger.error("fetch_client_error", url=url, error=str(e), error_type=type(e).__name__)
                self.stats["failed_requests"] += 1
                raise

            except Exception as e:
                self.logger.error("fetch_unexpected_error", url=url, error=str(e), error_type=type(e).__name__)
                self.stats["failed_requests"] += 1
                raise

    async def fetch_with_validation(
        self, url: str, allowed_content_types: Optional[list[str]] = None
    ) -> FetchResult:
        """
        Загрузить страницу с валидацией Content-Type.

        Args:
            url: URL для загрузки
            allowed_content_types: Разрешённые типы контента

        Returns:
            FetchResult: Результат загрузки

        Raises:
            ValueError: Если Content-Type не разрешён

        Example:
            >>> result = await fetcher.fetch_with_validation(
            ...     "https://example.com",
            ...     allowed_content_types=["text/html", "application/json"]
            ... )
        """
        # Сначала делаем HEAD запрос для проверки Content-Type
        head_result = await self.fetch(url, method="HEAD", allow_redirects=True)

        # Проверяем Content-Type
        allowed_types = allowed_content_types or self.config.crawler.allowed_content_types

        if not validate_content_type(head_result.content_type, allowed_types):
            self.logger.warning(
                "content_type_not_allowed",
                url=url,
                content_type=head_result.content_type,
                allowed=allowed_types,
            )
            raise ValueError(f"Content-Type не разрешён: {head_result.content_type}")

        # Если Content-Type OK, загружаем полный контент
        return await self.fetch(url)

    def get_stats(self) -> dict:
        """
        Получить статистику fetcher.

        Returns:
            dict: Словарь со статистикой

        Example:
            >>> stats = fetcher.get_stats()
            >>> print(f"Success rate: {stats['success_rate']:.2%}")
        """
        stats = self.stats.copy()

        if stats["total_requests"] > 0:
            stats["success_rate"] = stats["successful_requests"] / stats["total_requests"]
            stats["avg_response_time"] = (
                stats["total_response_time"] / stats["total_requests"]
            )
        else:
            stats["success_rate"] = 0.0
            stats["avg_response_time"] = 0.0

        return stats

    async def __aenter__(self):
        """Context manager support."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager support."""
        await self.close()
