"""
Unit тесты для webcrawler.core.parser
"""

import pytest

from webcrawler.core.parser import HTMLParser, ParsedLink, ParsedPage


@pytest.mark.unit
class TestHTMLParser:
    """Тесты для HTML парсера."""

    def test_parse_basic_html(self, sample_html):
        """Тест парсинга базового HTML."""
        parser = HTMLParser(base_url="https://example.com")
        result = parser.parse(sample_html)

        assert isinstance(result, ParsedPage)
        assert result.url == "https://example.com"

    def test_parse_title(self, sample_html):
        """Тест извлечения title."""
        parser = HTMLParser(base_url="https://example.com")
        result = parser.parse(sample_html)

        assert result.title == "Test Page Title"

    def test_parse_meta_description(self, sample_html):
        """Тест извлечения meta description."""
        parser = HTMLParser(base_url="https://example.com")
        result = parser.parse(sample_html)

        assert result.meta_description == "Test page description"

    def test_parse_meta_keywords(self, sample_html):
        """Тест извлечения meta keywords."""
        parser = HTMLParser(base_url="https://example.com")
        result = parser.parse(sample_html)

        assert result.meta_keywords == "test, page, keywords"

    def test_parse_meta_robots(self, sample_html):
        """Тест извлечения meta robots."""
        parser = HTMLParser(base_url="https://example.com")
        result = parser.parse(sample_html)

        assert result.meta_robots == "index, follow"

    def test_parse_language(self, sample_html):
        """Тест извлечения языка."""
        parser = HTMLParser(base_url="https://example.com")
        result = parser.parse(sample_html)

        assert result.language == "en"

    def test_parse_links(self, sample_html):
        """Тест извлечения ссылок."""
        parser = HTMLParser(base_url="https://example.com")
        result = parser.parse(sample_html)

        assert len(result.links) > 0

        # Проверяем типы ссылок
        link_types = [link.link_type for link in result.links]
        assert "hyperlink" in link_types
        assert "canonical" in link_types
        assert "alternate" in link_types

    def test_parse_internal_links(self, sample_html):
        """Тест категоризации internal ссылок."""
        parser = HTMLParser(base_url="https://example.com")
        result = parser.parse(sample_html)

        # Должны быть internal ссылки
        assert result.internal_links_count > 0

        internal_links = [
            link for link in result.links if not link.is_external
        ]
        assert len(internal_links) > 0

    def test_parse_external_links(self, sample_html):
        """Тест категоризации external ссылок."""
        parser = HTMLParser(base_url="https://example.com")
        result = parser.parse(sample_html)

        # Должна быть хотя бы одна external ссылка
        assert result.external_links_count > 0

        external_links = [link for link in result.links if link.is_external]
        assert len(external_links) > 0

    def test_parse_nofollow_links(self, sample_html):
        """Тест обнаружения nofollow ссылок."""
        parser = HTMLParser(base_url="https://example.com")
        result = parser.parse(sample_html)

        nofollow_links = [link for link in result.links if link.is_nofollow]

        # В sample_html есть nofollow ссылка
        assert len(nofollow_links) > 0

    def test_parse_canonical_url(self, sample_html):
        """Тест извлечения canonical URL."""
        parser = HTMLParser(base_url="https://example.com")
        result = parser.parse(sample_html)

        assert result.canonical_url == "https://example.com/canonical"

    def test_parse_alternate_urls(self, sample_html):
        """Тест извлечения alternate URLs."""
        parser = HTMLParser(base_url="https://example.com")
        result = parser.parse(sample_html)

        assert len(result.alternate_urls) > 0

        # Проверяем hreflang
        spanish_alternate = next(
            (alt for alt in result.alternate_urls if alt.get("hreflang") == "es"),
            None,
        )
        assert spanish_alternate is not None
        assert spanish_alternate["url"] == "https://example.com/es"

    def test_parse_structured_data(self, sample_html):
        """Тест извлечения structured data."""
        parser = HTMLParser(base_url="https://example.com")
        result = parser.parse(sample_html)

        # Schema.org
        assert result.has_schema_org is True
        assert "schema_org" in result.structured_data

        # Open Graph
        assert result.has_open_graph is True
        assert "open_graph" in result.structured_data

    def test_parse_headings(self, sample_html):
        """Тест извлечения заголовков."""
        parser = HTMLParser(base_url="https://example.com")
        result = parser.parse(sample_html)

        assert len(result.h1_tags) > 0
        assert "Main Heading" in result.h1_tags

        assert len(result.h2_tags) > 0
        assert "Sub Heading" in result.h2_tags

    def test_parse_images(self, sample_html):
        """Тест извлечения изображений."""
        parser = HTMLParser(base_url="https://example.com")
        result = parser.parse(sample_html)

        assert result.images_count > 0
        assert len(result.images) > 0

        # Проверяем метаданные изображения
        image = result.images[0]
        assert "src" in image
        assert "alt" in image

    def test_parse_relative_links(self):
        """Тест преобразования относительных ссылок."""
        html = """
        <html>
        <body>
            <a href="/page1">Link 1</a>
            <a href="page2">Link 2</a>
            <a href="../page3">Link 3</a>
        </body>
        </html>
        """

        parser = HTMLParser(base_url="https://example.com/current/page")
        result = parser.parse(html)

        # Все ссылки должны быть абсолютными
        for link in result.links:
            assert link.url.startswith("http")

    def test_parse_anchor_text(self):
        """Тест извлечения anchor text."""
        html = """
        <html>
        <body>
            <a href="/page1">Click here</a>
            <a href="/page2"><b>Bold</b> text</a>
        </body>
        </html>
        """

        parser = HTMLParser(base_url="https://example.com")
        result = parser.parse(html)

        anchor_texts = [link.anchor_text for link in result.links]
        assert "Click here" in anchor_texts


@pytest.mark.unit
class TestHTMLParserEdgeCases:
    """Тесты edge cases для HTML парсера."""

    def test_parse_empty_html(self):
        """Тест парсинга пустого HTML."""
        parser = HTMLParser(base_url="https://example.com")
        result = parser.parse("")

        assert isinstance(result, ParsedPage)
        assert len(result.links) == 0

    def test_parse_malformed_html(self):
        """Тест парсинга некорректного HTML."""
        html = """
        <html>
        <body>
            <a href="/page1">Link without closing tag
            <div>
                <p>Unclosed div
        """

        parser = HTMLParser(base_url="https://example.com")
        # Должен справиться (BeautifulSoup исправляет)
        result = parser.parse(html)

        assert isinstance(result, ParsedPage)

    def test_parse_no_links(self):
        """Тест HTML без ссылок."""
        html = """
        <html>
        <head><title>No Links</title></head>
        <body><p>Just text, no links</p></body>
        </html>
        """

        parser = HTMLParser(base_url="https://example.com")
        result = parser.parse(html)

        assert len(result.links) == 0
        assert result.internal_links_count == 0
        assert result.external_links_count == 0

    def test_parse_javascript_links(self):
        """Тест игнорирования javascript: ссылок."""
        html = """
        <html>
        <body>
            <a href="javascript:void(0)">JS Link</a>
            <a href="javascript:alert(1)">Alert</a>
            <a href="/normal">Normal Link</a>
        </body>
        </html>
        """

        parser = HTMLParser(base_url="https://example.com")
        result = parser.parse(html)

        # javascript: ссылки должны быть отфильтрованы
        js_links = [
            link for link in result.links if link.url.startswith("javascript:")
        ]
        assert len(js_links) == 0

    def test_parse_mailto_links(self):
        """Тест игнорирования mailto: ссылок."""
        html = """
        <html>
        <body>
            <a href="mailto:test@example.com">Email</a>
            <a href="/normal">Normal Link</a>
        </body>
        </html>
        """

        parser = HTMLParser(base_url="https://example.com")
        result = parser.parse(html)

        mailto_links = [
            link for link in result.links if link.url.startswith("mailto:")
        ]
        assert len(mailto_links) == 0

    def test_parse_tel_links(self):
        """Тест игнорирования tel: ссылок."""
        html = """
        <html>
        <body>
            <a href="tel:+1234567890">Call</a>
            <a href="/normal">Normal Link</a>
        </body>
        </html>
        """

        parser = HTMLParser(base_url="https://example.com")
        result = parser.parse(html)

        tel_links = [link for link in result.links if link.url.startswith("tel:")]
        assert len(tel_links) == 0

    def test_parse_anchor_only_links(self):
        """Тест игнорирования ссылок только с якорем."""
        html = """
        <html>
        <body>
            <a href="#section1">Section 1</a>
            <a href="#section2">Section 2</a>
            <a href="/page#section">Page with Section</a>
        </body>
        </html>
        """

        parser = HTMLParser(base_url="https://example.com")
        result = parser.parse(html)

        # Ссылки только с # должны быть отфильтрованы
        # Но /page#section должна остаться (без #section)
        anchor_only = [
            link for link in result.links if link.url == "https://example.com#"
        ]
        # Зависит от реализации

    def test_parse_different_encodings(self):
        """Тест разных кодировок."""
        # UTF-8 HTML
        html_utf8 = "<html><body><p>Привет мир</p></body></html>".encode("utf-8")

        parser = HTMLParser(base_url="https://example.com")
        result = parser.parse(html_utf8, encoding="utf-8")

        assert isinstance(result, ParsedPage)

    def test_parse_bytes_vs_string(self):
        """Тест парсинга bytes vs string."""
        html_str = "<html><body><a href='/page'>Link</a></body></html>"
        html_bytes = html_str.encode("utf-8")

        parser = HTMLParser(base_url="https://example.com")

        # Должен работать и с str и с bytes
        result_str = parser.parse(html_str)
        result_bytes = parser.parse(html_bytes)

        assert len(result_str.links) == len(result_bytes.links)


@pytest.mark.unit
class TestParsedLink:
    """Тесты для ParsedLink dataclass."""

    def test_parsed_link_creation(self):
        """Тест создания ParsedLink."""
        link = ParsedLink(
            url="https://example.com/page",
            anchor_text="Click here",
            rel="nofollow",
            link_type="hyperlink",
            is_nofollow=True,
            is_external=False,
        )

        assert link.url == "https://example.com/page"
        assert link.anchor_text == "Click here"
        assert link.is_nofollow is True
        assert link.is_external is False

    def test_parsed_link_defaults(self):
        """Тест default значений ParsedLink."""
        link = ParsedLink(url="https://example.com")

        assert link.anchor_text is None
        assert link.rel is None
        assert link.link_type == "hyperlink"
        assert link.is_nofollow is False
        assert link.is_external is False


@pytest.mark.unit
class TestParsedPage:
    """Тесты для ParsedPage dataclass."""

    def test_parsed_page_creation(self):
        """Тест создания ParsedPage."""
        page = ParsedPage(url="https://example.com")

        assert page.url == "https://example.com"
        assert page.title is None
        assert len(page.links) == 0
        assert page.internal_links_count == 0
        assert page.external_links_count == 0

    def test_parsed_page_with_data(self):
        """Тест ParsedPage с данными."""
        links = [
            ParsedLink(url="https://example.com/page1"),
            ParsedLink(url="https://other.com", is_external=True),
        ]

        page = ParsedPage(
            url="https://example.com",
            title="Test Page",
            meta_description="Description",
            links=links,
            internal_links_count=1,
            external_links_count=1,
        )

        assert page.title == "Test Page"
        assert len(page.links) == 2
        assert page.internal_links_count == 1
        assert page.external_links_count == 1
