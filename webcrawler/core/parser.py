"""
HTML парсер для извлечения ссылок и метаданных.

Использует BeautifulSoup4 + lxml для быстрого и надёжного парсинга HTML.
Извлекает ссылки, мета-теги, структурированные данные и другие метаданные.
"""

import json
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from webcrawler.utils.helpers import clean_text
from webcrawler.utils.logger import LoggerMixin
from webcrawler.utils.validators import is_absolute_url, is_valid_url


@dataclass
class ParsedLink:
    """
    Извлечённая ссылка с метаданными.
    """

    url: str
    anchor_text: Optional[str] = None
    rel: Optional[str] = None
    link_type: str = "hyperlink"  # hyperlink, redirect, canonical, alternate, etc.
    is_nofollow: bool = False
    is_external: bool = False


@dataclass
class ParsedPage:
    """
    Результат парсинга страницы.

    Содержит все извлечённые данные: ссылки, метаданные, структурированные данные.
    """

    url: str
    title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: Optional[str] = None
    meta_robots: Optional[str] = None
    language: Optional[str] = None

    # Ссылки
    links: list[ParsedLink] = field(default_factory=list)
    internal_links_count: int = 0
    external_links_count: int = 0

    # Структурированные данные
    has_schema_org: bool = False
    has_open_graph: bool = False
    structured_data: dict = field(default_factory=dict)

    # Заголовки
    h1_tags: list[str] = field(default_factory=list)
    h2_tags: list[str] = field(default_factory=list)

    # Изображения
    images_count: int = 0
    images: list[dict] = field(default_factory=list)

    # Скрипты и стили
    scripts_count: int = 0
    stylesheets_count: int = 0

    # Canonical URL
    canonical_url: Optional[str] = None

    # Альтернативные версии
    alternate_urls: list[dict] = field(default_factory=list)


class HTMLParser(LoggerMixin):
    """
    HTML парсер для извлечения ссылок и метаданных.

    Использует BeautifulSoup4 с lxml парсером для производительности.
    Извлекает:
    - Все типы ссылок (a, link, canonical, alternate)
    - Мета-теги (title, description, keywords, robots)
    - Структурированные данные (Schema.org, Open Graph)
    - Заголовки (h1-h6)
    - Изображения и их атрибуты
    - Скрипты и стили

    Example:
        >>> parser = HTMLParser(base_url="https://example.com")
        >>> html_content = b"<html><body><a href='/page'>Link</a></body></html>"
        >>> result = parser.parse(html_content)
        >>> print(f"Found {len(result.links)} links")
    """

    def __init__(self, base_url: str):
        """
        Инициализация HTML парсера.

        Args:
            base_url: Базовый URL страницы (для преобразования относительных ссылок)
        """
        self.base_url = base_url
        self.base_domain = urlparse(base_url).netloc

        self.logger.debug("html_parser_initialized", base_url=base_url)

    def parse(self, html_content: bytes | str, encoding: Optional[str] = None) -> ParsedPage:
        """
        Парсить HTML контент и извлечь все данные.

        Args:
            html_content: HTML контент (bytes или str)
            encoding: Кодировка контента (если известна)

        Returns:
            ParsedPage: Результат парсинга

        Example:
            >>> result = parser.parse(html_bytes)
            >>> print(result.title)
            'Example Page'
        """
        # Декодируем контент если это bytes
        if isinstance(html_content, bytes):
            if encoding:
                try:
                    html_content = html_content.decode(encoding)
                except UnicodeDecodeError:
                    # Fallback на utf-8 с игнорированием ошибок
                    html_content = html_content.decode("utf-8", errors="ignore")
            else:
                # Пытаемся определить кодировку автоматически
                html_content = html_content.decode("utf-8", errors="ignore")

        # Создаём BeautifulSoup объект с lxml парсером
        try:
            soup = BeautifulSoup(html_content, "lxml")
        except Exception as e:
            self.logger.warning("lxml_parser_failed_fallback_to_html_parser", error=str(e))
            # Fallback на html.parser
            soup = BeautifulSoup(html_content, "html.parser")

        # Создаём результат
        result = ParsedPage(url=self.base_url)

        # Извлекаем базовые метаданные
        self._extract_metadata(soup, result)

        # Извлекаем ссылки
        self._extract_links(soup, result)

        # Извлекаем структурированные данные
        self._extract_structured_data(soup, result)

        # Извлекаем заголовки
        self._extract_headings(soup, result)

        # Извлекаем изображения
        self._extract_images(soup, result)

        # Извлекаем скрипты и стили
        self._extract_scripts_and_styles(soup, result)

        # Извлекаем canonical и alternate URLs
        self._extract_special_links(soup, result)

        # Подсчитываем внутренние/внешние ссылки
        self._categorize_links(result)

        self.logger.debug(
            "html_parsed",
            url=self.base_url,
            links_found=len(result.links),
            internal=result.internal_links_count,
            external=result.external_links_count,
        )

        return result

    def _extract_metadata(self, soup: BeautifulSoup, result: ParsedPage) -> None:
        """
        Извлечь базовые метаданные (title, meta tags).

        Args:
            soup: BeautifulSoup объект
            result: Результат для заполнения
        """
        # Title
        title_tag = soup.find("title")
        if title_tag:
            result.title = clean_text(title_tag.get_text())

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            result.meta_description = clean_text(meta_desc["content"])

        # Meta keywords
        meta_keywords = soup.find("meta", attrs={"name": "keywords"})
        if meta_keywords and meta_keywords.get("content"):
            result.meta_keywords = clean_text(meta_keywords["content"])

        # Meta robots
        meta_robots = soup.find("meta", attrs={"name": "robots"})
        if meta_robots and meta_robots.get("content"):
            result.meta_robots = clean_text(meta_robots["content"])

        # Language
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            result.language = html_tag["lang"]

    def _extract_links(self, soup: BeautifulSoup, result: ParsedPage) -> None:
        """
        Извлечь все ссылки со страницы.

        Args:
            soup: BeautifulSoup объект
            result: Результат для заполнения
        """
        # Извлекаем <a> ссылки
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()

            # Пропускаем пустые ссылки и якоря
            if not href or href.startswith("#"):
                continue

            # Пропускаем javascript: и mailto: ссылки
            if href.startswith(("javascript:", "mailto:", "tel:")):
                continue

            # Преобразуем относительные ссылки в абсолютные
            absolute_url = urljoin(self.base_url, href)

            # Валидация URL
            if not is_valid_url(absolute_url):
                continue

            # Извлекаем anchor text
            anchor_text = clean_text(a_tag.get_text())

            # Извлекаем rel атрибут
            rel = a_tag.get("rel")
            if isinstance(rel, list):
                rel = " ".join(rel)

            # Проверяем nofollow
            is_nofollow = rel and "nofollow" in rel.lower() if rel else False

            # Создаём ParsedLink
            link = ParsedLink(
                url=absolute_url,
                anchor_text=anchor_text or None,
                rel=rel,
                link_type="hyperlink",
                is_nofollow=is_nofollow,
            )

            result.links.append(link)

    def _extract_structured_data(self, soup: BeautifulSoup, result: ParsedPage) -> None:
        """
        Извлечь структурированные данные (Schema.org, Open Graph).

        Args:
            soup: BeautifulSoup объект
            result: Результат для заполнения
        """
        structured_data = {}

        # Schema.org (JSON-LD)
        json_ld_scripts = soup.find_all("script", type="application/ld+json")
        if json_ld_scripts:
            result.has_schema_org = True
            schema_data = []

            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    schema_data.append(data)
                except (json.JSONDecodeError, AttributeError):
                    continue

            if schema_data:
                structured_data["schema_org"] = schema_data

        # Open Graph
        og_tags = soup.find_all("meta", property=lambda x: x and x.startswith("og:"))
        if og_tags:
            result.has_open_graph = True
            og_data = {}

            for tag in og_tags:
                prop = tag.get("property")
                content = tag.get("content")
                if prop and content:
                    # Убираем префикс og:
                    key = prop.replace("og:", "")
                    og_data[key] = content

            if og_data:
                structured_data["open_graph"] = og_data

        # Twitter Cards
        twitter_tags = soup.find_all("meta", attrs={"name": lambda x: x and x.startswith("twitter:")})
        if twitter_tags:
            twitter_data = {}

            for tag in twitter_tags:
                name = tag.get("name")
                content = tag.get("content")
                if name and content:
                    key = name.replace("twitter:", "")
                    twitter_data[key] = content

            if twitter_data:
                structured_data["twitter"] = twitter_data

        result.structured_data = structured_data

    def _extract_headings(self, soup: BeautifulSoup, result: ParsedPage) -> None:
        """
        Извлечь заголовки h1-h6.

        Args:
            soup: BeautifulSoup объект
            result: Результат для заполнения
        """
        # H1 заголовки
        h1_tags = soup.find_all("h1")
        result.h1_tags = [clean_text(tag.get_text()) for tag in h1_tags if tag.get_text().strip()]

        # H2 заголовки
        h2_tags = soup.find_all("h2")
        result.h2_tags = [clean_text(tag.get_text()) for tag in h2_tags if tag.get_text().strip()]

    def _extract_images(self, soup: BeautifulSoup, result: ParsedPage) -> None:
        """
        Извлечь информацию об изображениях.

        Args:
            soup: BeautifulSoup объект
            result: Результат для заполнения
        """
        images = []

        for img_tag in soup.find_all("img"):
            src = img_tag.get("src")
            if not src:
                continue

            # Преобразуем в абсолютный URL
            absolute_src = urljoin(self.base_url, src)

            image_data = {
                "src": absolute_src,
                "alt": img_tag.get("alt", ""),
                "title": img_tag.get("title"),
                "width": img_tag.get("width"),
                "height": img_tag.get("height"),
            }

            images.append(image_data)

        result.images = images
        result.images_count = len(images)

    def _extract_scripts_and_styles(self, soup: BeautifulSoup, result: ParsedPage) -> None:
        """
        Подсчитать количество скриптов и стилей.

        Args:
            soup: BeautifulSoup объект
            result: Результат для заполнения
        """
        result.scripts_count = len(soup.find_all("script"))
        result.stylesheets_count = len(soup.find_all("link", rel="stylesheet"))

    def _extract_special_links(self, soup: BeautifulSoup, result: ParsedPage) -> None:
        """
        Извлечь canonical и alternate URLs.

        Args:
            soup: BeautifulSoup объект
            result: Результат для заполнения
        """
        # Canonical URL
        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            canonical_url = urljoin(self.base_url, canonical["href"])
            result.canonical_url = canonical_url

            # Добавляем в список ссылок
            result.links.append(
                ParsedLink(
                    url=canonical_url,
                    link_type="canonical",
                )
            )

        # Alternate URLs (языковые версии, мобильные версии, etc.)
        alternates = soup.find_all("link", rel="alternate")
        for alt in alternates:
            href = alt.get("href")
            if not href:
                continue

            absolute_href = urljoin(self.base_url, href)

            alternate_data = {
                "url": absolute_href,
                "hreflang": alt.get("hreflang"),
                "media": alt.get("media"),
                "type": alt.get("type"),
            }

            result.alternate_urls.append(alternate_data)

            # Добавляем в список ссылок
            result.links.append(
                ParsedLink(
                    url=absolute_href,
                    link_type="alternate",
                )
            )

    def _categorize_links(self, result: ParsedPage) -> None:
        """
        Категоризировать ссылки на внутренние и внешние.

        Args:
            result: Результат для обновления
        """
        for link in result.links:
            # Определяем, является ли ссылка внешней
            link_domain = urlparse(link.url).netloc

            if link_domain == self.base_domain:
                result.internal_links_count += 1
                link.is_external = False
            else:
                result.external_links_count += 1
                link.is_external = True
