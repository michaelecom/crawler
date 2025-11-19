"""
Парсер robots.txt для соблюдения правил краулинга.

Использует стандартную библиотеку urllib.robotparser для парсинга
и проверки разрешений на краулинг URL.
"""

from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from webcrawler.utils.logger import LoggerMixin


class RobotsParser(LoggerMixin):
    """
    Парсер robots.txt для проверки разрешений краулинга.

    Парсит robots.txt и предоставляет методы для проверки
    разрешения на краулинг конкретных URL.

    Example:
        >>> parser = RobotsParser("https://example.com", user_agent="MyBot/1.0")
        >>> await parser.fetch()
        >>> if parser.can_fetch("/page"):
        ...     print("Allowed to crawl")
    """

    def __init__(self, base_url: str, user_agent: str = "*"):
        """
        Инициализация robots.txt парсера.

        Args:
            base_url: Базовый URL сайта (схема + домен)
            user_agent: User-agent для проверки правил
        """
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent

        # URL к robots.txt
        parsed = urlparse(base_url)
        self.robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        # Парсер
        self.parser = RobotFileParser(self.robots_url)

        # Флаги состояния
        self.fetched = False
        self.exists = False
        self.parse_error = False

        # Sitemap URLs из robots.txt
        self.sitemaps: list[str] = []

        # Crawl delay (если указан)
        self.crawl_delay: Optional[float] = None

        self.logger.debug(
            "robots_parser_initialized",
            robots_url=self.robots_url,
            user_agent=user_agent
        )

    async def fetch(self, timeout: int = 10) -> bool:
        """
        Загрузить и распарсить robots.txt.

        Args:
            timeout: Таймаут загрузки в секундах

        Returns:
            bool: True если robots.txt успешно загружен и распаршен

        Example:
            >>> parser = RobotsParser("https://example.com")
            >>> success = await parser.fetch()
            >>> if success:
            ...     print("robots.txt loaded")
        """
        try:
            # Загружаем robots.txt (синхронно, т.к. RobotFileParser не async)
            # В production можно заменить на async версию через aiohttp
            import asyncio
            await asyncio.to_thread(self.parser.read)

            self.fetched = True
            self.exists = True

            # Извлекаем sitemaps
            self._extract_sitemaps()

            # Извлекаем crawl-delay
            self._extract_crawl_delay()

            self.logger.info(
                "robots_txt_fetched",
                url=self.robots_url,
                sitemaps_found=len(self.sitemaps),
                crawl_delay=self.crawl_delay
            )

            return True

        except Exception as e:
            self.fetched = True
            self.exists = False
            self.parse_error = True

            self.logger.warning(
                "robots_txt_fetch_failed",
                url=self.robots_url,
                error=str(e),
                error_type=type(e).__name__
            )

            return False

    def can_fetch(self, url: str) -> bool:
        """
        Проверить, разрешён ли краулинг URL.

        Args:
            url: URL для проверки (может быть относительным или абсолютным)

        Returns:
            bool: True если краулинг разрешён

        Example:
            >>> if parser.can_fetch("/admin"):
            ...     print("Can crawl /admin")
            ... else:
            ...     print("Cannot crawl /admin")
        """
        # Если robots.txt не был загружен или не существует, разрешаем всё
        if not self.fetched or not self.exists:
            return True

        # Если была ошибка парсинга, разрешаем (fail-open подход)
        if self.parse_error:
            return True

        # Преобразуем относительный URL в абсолютный
        if not url.startswith(("http://", "https://")):
            url = urljoin(self.base_url, url)

        # Проверяем разрешение
        try:
            return self.parser.can_fetch(self.user_agent, url)
        except Exception as e:
            self.logger.warning(
                "robots_can_fetch_error",
                url=url,
                error=str(e)
            )
            # При ошибке разрешаем (fail-open)
            return True

    def _extract_sitemaps(self) -> None:
        """Извлечь sitemap URLs из robots.txt."""
        try:
            # RobotFileParser не предоставляет прямого доступа к sitemap,
            # поэтому парсим вручную
            if hasattr(self.parser, 'entries') and self.parser.entries:
                for entry in self.parser.entries:
                    if hasattr(entry, 'sitemaps'):
                        self.sitemaps.extend(entry.sitemaps)

            # Альтернативный способ - читаем через parser._entries
            if hasattr(self.parser, '_entries'):
                for entry in self.parser._entries:
                    # Извлекаем sitemap директивы
                    pass  # TODO: implement if needed

        except Exception as e:
            self.logger.debug("sitemap_extraction_failed", error=str(e))

    def _extract_crawl_delay(self) -> None:
        """Извлечь crawl-delay директиву из robots.txt."""
        try:
            # Получаем crawl-delay для нашего user-agent
            delay = self.parser.crawl_delay(self.user_agent)
            if delay:
                self.crawl_delay = float(delay)
        except Exception as e:
            self.logger.debug("crawl_delay_extraction_failed", error=str(e))

    def get_crawl_delay(self) -> Optional[float]:
        """
        Получить рекомендуемую задержку между запросами.

        Returns:
            Optional[float]: Задержка в секундах или None

        Example:
            >>> delay = parser.get_crawl_delay()
            >>> if delay:
            ...     await asyncio.sleep(delay)
        """
        return self.crawl_delay

    def get_sitemaps(self) -> list[str]:
        """
        Получить список sitemap URLs из robots.txt.

        Returns:
            list[str]: Список sitemap URLs

        Example:
            >>> sitemaps = parser.get_sitemaps()
            >>> for sitemap_url in sitemaps:
            ...     print(f"Found sitemap: {sitemap_url}")
        """
        return self.sitemaps.copy()

    def is_accessible(self) -> bool:
        """
        Проверить, доступен ли robots.txt.

        Returns:
            bool: True если robots.txt был успешно загружен
        """
        return self.fetched and self.exists and not self.parse_error
