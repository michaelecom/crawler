"""
Парсер sitemap.xml для оптимизации краулинга.

Парсит sitemap.xml и sitemap index файлы,
извлекает URL с метаданными (приоритет, частота обновления).
"""

import gzip
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

import aiohttp

from webcrawler.utils.logger import LoggerMixin


@dataclass
class SitemapURL:
    """
    URL из sitemap с метаданными.
    """

    loc: str  # URL страницы
    lastmod: Optional[datetime] = None  # Дата последнего изменения
    changefreq: Optional[str] = None  # Частота изменений
    priority: Optional[float] = None  # Приоритет (0.0-1.0)


class SitemapParser(LoggerMixin):
    """
    Парсер sitemap.xml файлов.

    Поддерживает:
    - Обычные sitemap.xml
    - Sitemap index (ссылки на другие sitemap)
    - Gzip сжатые sitemap (.xml.gz)
    - Рекурсивный парсинг sitemap index

    Example:
        >>> parser = SitemapParser()
        >>> urls = await parser.fetch_and_parse("https://example.com/sitemap.xml")
        >>> for url_entry in urls:
        ...     print(f"{url_entry.loc} (priority: {url_entry.priority})")
    """

    # XML namespaces для sitemap
    NAMESPACES = {
        "": "http://www.sitemaps.org/schemas/sitemap/0.9",
        "image": "http://www.google.com/schemas/sitemap-image/1.1",
        "video": "http://www.google.com/schemas/sitemap-video/1.1",
        "news": "http://www.google.com/schemas/sitemap-news/0.9",
    }

    def __init__(self, timeout: int = 30, max_urls: int = 50000):
        """
        Инициализация sitemap парсера.

        Args:
            timeout: Таймаут загрузки sitemap (секунды)
            max_urls: Максимальное количество URL для извлечения
        """
        self.timeout = timeout
        self.max_urls = max_urls
        self.logger.debug("sitemap_parser_initialized", timeout=timeout, max_urls=max_urls)

    async def fetch_and_parse(
        self,
        sitemap_url: str,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> list[SitemapURL]:
        """
        Загрузить и распарсить sitemap.

        Args:
            sitemap_url: URL sitemap файла
            session: Опциональная aiohttp сессия (для переиспользования)

        Returns:
            list[SitemapURL]: Список URL из sitemap

        Example:
            >>> urls = await parser.fetch_and_parse("https://example.com/sitemap.xml")
            >>> print(f"Found {len(urls)} URLs")
        """
        # Создаём сессию если не передана
        own_session = False
        if not session:
            session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
            own_session = True

        try:
            # Загружаем sitemap
            content = await self._fetch_sitemap(sitemap_url, session)

            if not content:
                return []

            # Парсим содержимое
            urls = self._parse_sitemap_content(content, sitemap_url)

            self.logger.info(
                "sitemap_parsed",
                url=sitemap_url,
                urls_found=len(urls)
            )

            return urls

        except Exception as e:
            self.logger.error(
                "sitemap_fetch_failed",
                url=sitemap_url,
                error=str(e),
                error_type=type(e).__name__
            )
            return []

        finally:
            if own_session:
                await session.close()

    async def _fetch_sitemap(
        self,
        sitemap_url: str,
        session: aiohttp.ClientSession
    ) -> Optional[bytes]:
        """
        Загрузить sitemap файл.

        Args:
            sitemap_url: URL sitemap
            session: aiohttp сессия

        Returns:
            Optional[bytes]: Содержимое sitemap или None
        """
        try:
            async with session.get(sitemap_url) as response:
                if response.status != 200:
                    self.logger.warning(
                        "sitemap_fetch_non_200",
                        url=sitemap_url,
                        status=response.status
                    )
                    return None

                content = await response.read()

                # Если это gzip, распаковываем
                if sitemap_url.endswith(".gz") or response.headers.get("Content-Encoding") == "gzip":
                    try:
                        content = gzip.decompress(content)
                    except Exception as e:
                        self.logger.warning("gzip_decompression_failed", error=str(e))

                return content

        except Exception as e:
            self.logger.error("sitemap_download_error", url=sitemap_url, error=str(e))
            return None

    def _parse_sitemap_content(
        self,
        content: bytes,
        base_url: str
    ) -> list[SitemapURL]:
        """
        Парсить содержимое sitemap XML.

        Args:
            content: XML содержимое
            base_url: Базовый URL (для относительных ссылок)

        Returns:
            list[SitemapURL]: Список извлечённых URL
        """
        try:
            root = ET.fromstring(content)

            # Определяем тип sitemap: index или urlset
            if root.tag.endswith("sitemapindex"):
                # Это sitemap index - содержит ссылки на другие sitemap
                return self._parse_sitemap_index(root, base_url)
            elif root.tag.endswith("urlset"):
                # Это обычный sitemap
                return self._parse_urlset(root, base_url)
            else:
                self.logger.warning("unknown_sitemap_format", root_tag=root.tag)
                return []

        except ET.ParseError as e:
            self.logger.error("xml_parse_error", error=str(e))
            return []

    def _parse_urlset(self, root: ET.Element, base_url: str) -> list[SitemapURL]:
        """
        Парсить <urlset> sitemap.

        Args:
            root: Корневой XML элемент
            base_url: Базовый URL

        Returns:
            list[SitemapURL]: Список URL
        """
        urls = []

        for url_elem in root.findall(".//{{{}}}url".format(self.NAMESPACES[""])):
            # Извлекаем loc
            loc_elem = url_elem.find("{{{}}}loc".format(self.NAMESPACES[""]))
            if loc_elem is None or not loc_elem.text:
                continue

            loc = loc_elem.text.strip()

            # Преобразуем относительные URL в абсолютные
            if not loc.startswith(("http://", "https://")):
                loc = urljoin(base_url, loc)

            # Извлекаем lastmod
            lastmod = None
            lastmod_elem = url_elem.find("{{{}}}lastmod".format(self.NAMESPACES[""]))
            if lastmod_elem is not None and lastmod_elem.text:
                lastmod = self._parse_datetime(lastmod_elem.text)

            # Извлекаем changefreq
            changefreq = None
            changefreq_elem = url_elem.find("{{{}}}changefreq".format(self.NAMESPACES[""]))
            if changefreq_elem is not None and changefreq_elem.text:
                changefreq = changefreq_elem.text.strip()

            # Извлекаем priority
            priority = None
            priority_elem = url_elem.find("{{{}}}priority".format(self.NAMESPACES[""]))
            if priority_elem is not None and priority_elem.text:
                try:
                    priority = float(priority_elem.text)
                except ValueError:
                    pass

            # Создаём SitemapURL
            sitemap_url = SitemapURL(
                loc=loc,
                lastmod=lastmod,
                changefreq=changefreq,
                priority=priority
            )

            urls.append(sitemap_url)

            # Проверяем лимит
            if len(urls) >= self.max_urls:
                self.logger.warning("sitemap_max_urls_reached", max_urls=self.max_urls)
                break

        return urls

    def _parse_sitemap_index(self, root: ET.Element, base_url: str) -> list[SitemapURL]:
        """
        Парсить <sitemapindex> - список sitemap файлов.

        Args:
            root: Корневой XML элемент
            base_url: Базовый URL

        Returns:
            list[SitemapURL]: Список sitemap URLs для дальнейшей обработки
        """
        sitemap_urls = []

        for sitemap_elem in root.findall(".//{{{}}}sitemap".format(self.NAMESPACES[""])):
            loc_elem = sitemap_elem.find("{{{}}}loc".format(self.NAMESPACES[""]))
            if loc_elem is None or not loc_elem.text:
                continue

            loc = loc_elem.text.strip()

            # Преобразуем относительные URL
            if not loc.startswith(("http://", "https://")):
                loc = urljoin(base_url, loc)

            # Для sitemap index возвращаем ссылки как есть
            # Caller должен рекурсивно обработать их
            sitemap_url = SitemapURL(loc=loc)
            sitemap_urls.append(sitemap_url)

        self.logger.info(
            "sitemap_index_parsed",
            sitemaps_found=len(sitemap_urls)
        )

        return sitemap_urls

    def _parse_datetime(self, date_string: str) -> Optional[datetime]:
        """
        Парсить дату из sitemap.

        Args:
            date_string: Строка с датой (ISO 8601)

        Returns:
            Optional[datetime]: Объект datetime или None
        """
        # Поддерживаемые форматы sitemap
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_string, fmt)
            except ValueError:
                continue

        return None

    async def fetch_all_sitemaps(
        self,
        sitemap_urls: list[str],
        session: Optional[aiohttp.ClientSession] = None,
    ) -> list[SitemapURL]:
        """
        Загрузить и распарсить несколько sitemap файлов.

        Args:
            sitemap_urls: Список sitemap URLs
            session: Опциональная aiohttp сессия

        Returns:
            list[SitemapURL]: Объединённый список URL из всех sitemap

        Example:
            >>> sitemaps = ["https://example.com/sitemap1.xml", "https://example.com/sitemap2.xml"]
            >>> all_urls = await parser.fetch_all_sitemaps(sitemaps)
        """
        import asyncio

        # Создаём сессию если нужно
        own_session = False
        if not session:
            session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
            own_session = True

        try:
            # Загружаем все sitemap параллельно
            tasks = [
                self.fetch_and_parse(sitemap_url, session)
                for sitemap_url in sitemap_urls
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Объединяем результаты
            all_urls = []
            for result in results:
                if isinstance(result, list):
                    all_urls.extend(result)

                    # Проверяем лимит
                    if len(all_urls) >= self.max_urls:
                        break

            # Ограничиваем до max_urls
            all_urls = all_urls[:self.max_urls]

            self.logger.info(
                "all_sitemaps_fetched",
                sitemaps_count=len(sitemap_urls),
                total_urls=len(all_urls)
            )

            return all_urls

        finally:
            if own_session:
                await session.close()
