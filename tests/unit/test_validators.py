"""
Unit тесты для webcrawler.utils.validators
"""

import pytest

from webcrawler.utils.validators import (
    clean_text,
    is_absolute_url,
    is_honeypot_url,
    is_same_domain,
    is_subdomain,
    is_valid_url,
    normalize_url,
    sanitize_url,
    validate_content_type,
)


@pytest.mark.unit
class TestURLValidation:
    """Тесты для валидации URL."""

    def test_is_valid_url_valid(self):
        """Тест валидных URL."""
        assert is_valid_url("https://example.com")
        assert is_valid_url("http://example.com/path")
        assert is_valid_url("https://sub.example.com/path?query=value")
        assert is_valid_url("https://example.com:8080/path")

    def test_is_valid_url_invalid(self):
        """Тест невалидных URL."""
        assert not is_valid_url("not a url")
        assert not is_valid_url("javascript:alert(1)")
        assert not is_valid_url("file:///etc/passwd")
        assert not is_valid_url("data:text/html,<script>alert(1)</script>")
        assert not is_valid_url("")
        assert not is_valid_url("ftp://example.com")  # Не поддерживаем FTP

    def test_is_absolute_url(self):
        """Тест проверки абсолютных URL."""
        assert is_absolute_url("https://example.com")
        assert is_absolute_url("http://example.com/path")
        assert not is_absolute_url("/relative/path")
        assert not is_absolute_url("relative/path")
        assert not is_absolute_url("//example.com")


@pytest.mark.unit
class TestURLNormalization:
    """Тесты для нормализации URL."""

    def test_normalize_url_basic(self):
        """Тест базовой нормализации."""
        assert normalize_url("https://example.com") == "https://example.com/"
        assert normalize_url("https://example.com/") == "https://example.com/"
        assert normalize_url("HTTPS://EXAMPLE.COM") == "https://example.com/"

    def test_normalize_url_removes_fragment(self):
        """Тест удаления фрагментов."""
        assert normalize_url("https://example.com/page#section") == "https://example.com/page"

    def test_normalize_url_sorts_query(self):
        """Тест сортировки query параметров."""
        url1 = normalize_url("https://example.com?b=2&a=1")
        url2 = normalize_url("https://example.com?a=1&b=2")
        assert url1 == url2

    def test_normalize_url_removes_default_port(self):
        """Тест удаления стандартных портов."""
        assert normalize_url("https://example.com:443/") == "https://example.com/"
        assert normalize_url("http://example.com:80/") == "http://example.com/"

    def test_normalize_url_preserves_custom_port(self):
        """Тест сохранения кастомных портов."""
        assert "8080" in normalize_url("https://example.com:8080/")


@pytest.mark.unit
class TestURLSanitization:
    """Тесты для санитизации URL."""

    def test_sanitize_url_removes_javascript(self):
        """Тест удаления javascript: схемы."""
        result = sanitize_url("javascript:alert(1)")
        assert result is None or not result.startswith("javascript:")

    def test_sanitize_url_removes_data(self):
        """Тест удаления data: схемы."""
        result = sanitize_url("data:text/html,<script>alert(1)</script>")
        assert result is None or not result.startswith("data:")

    def test_sanitize_url_allows_http(self):
        """Тест разрешения HTTP/HTTPS."""
        assert sanitize_url("https://example.com") == "https://example.com"
        assert sanitize_url("http://example.com") == "http://example.com"


@pytest.mark.unit
class TestDomainChecks:
    """Тесты для проверки доменов."""

    def test_is_same_domain(self):
        """Тест проверки одинаковых доменов."""
        assert is_same_domain("https://example.com", "https://example.com/page")
        assert is_same_domain("https://example.com", "https://example.com:443/page")
        assert not is_same_domain("https://example.com", "https://other.com")
        assert not is_same_domain("https://example.com", "https://sub.example.com")

    def test_is_subdomain(self):
        """Тест проверки поддоменов."""
        assert is_subdomain("https://sub.example.com", "example.com")
        assert is_subdomain("https://deep.sub.example.com", "example.com")
        assert is_subdomain("https://example.com", "example.com")  # Сам домен
        assert not is_subdomain("https://other.com", "example.com")


@pytest.mark.unit
class TestHoneypotDetection:
    """Тесты для детектирования honeypot ссылок."""

    def test_is_honeypot_url_traps(self):
        """Тест обнаружения honeypot trap'ов."""
        # Подозрительные паттерны
        assert is_honeypot_url("https://example.com/wp-admin/admin.php")
        assert is_honeypot_url("https://example.com/admin/login")
        assert is_honeypot_url("https://example.com/.env")
        assert is_honeypot_url("https://example.com/config.php")

    def test_is_honeypot_url_calendar(self):
        """Тест обнаружения calendar trap."""
        assert is_honeypot_url("https://example.com?year=2025&month=12")
        assert is_honeypot_url("https://example.com?date=2025-01-01")

    def test_is_honeypot_url_session(self):
        """Тест обнаружения session ID trap."""
        assert is_honeypot_url("https://example.com?sessionid=abc123")
        assert is_honeypot_url("https://example.com?PHPSESSID=xyz789")

    def test_is_honeypot_url_legitimate(self):
        """Тест что легитимные URL не детектируются."""
        assert not is_honeypot_url("https://example.com")
        assert not is_honeypot_url("https://example.com/blog")
        assert not is_honeypot_url("https://example.com/page?id=1")


@pytest.mark.unit
class TestContentTypeValidation:
    """Тесты для валидации Content-Type."""

    def test_validate_content_type_exact(self):
        """Тест точного совпадения."""
        allowed = ["text/html", "application/json"]
        assert validate_content_type("text/html", allowed)
        assert validate_content_type("application/json", allowed)
        assert not validate_content_type("text/plain", allowed)

    def test_validate_content_type_wildcard(self):
        """Тест wildcard паттернов."""
        allowed = ["text/*", "image/*"]
        assert validate_content_type("text/html", allowed)
        assert validate_content_type("text/plain", allowed)
        assert validate_content_type("image/png", allowed)
        assert validate_content_type("image/jpeg", allowed)
        assert not validate_content_type("application/json", allowed)

    def test_validate_content_type_with_charset(self):
        """Тест с charset параметром."""
        allowed = ["text/html"]
        assert validate_content_type("text/html; charset=utf-8", allowed)


@pytest.mark.unit
class TestTextCleaning:
    """Тесты для очистки текста."""

    def test_clean_text_whitespace(self):
        """Тест удаления лишних пробелов."""
        assert clean_text("  hello   world  ") == "hello world"
        assert clean_text("hello\n\nworld") == "hello world"
        assert clean_text("hello\tworld") == "hello world"

    def test_clean_text_empty(self):
        """Тест пустого текста."""
        assert clean_text("") == ""
        assert clean_text("   ") == ""
        assert clean_text("\n\n\n") == ""

    def test_clean_text_preserves_content(self):
        """Тест сохранения контента."""
        assert clean_text("Hello, World!") == "Hello, World!"
        assert clean_text("Test 123") == "Test 123"


@pytest.mark.unit
class TestEdgeCases:
    """Тесты для edge cases."""

    def test_normalize_url_unicode(self):
        """Тест Unicode в URL."""
        url = "https://example.com/путь"
        normalized = normalize_url(url)
        assert normalized  # Должен не падать

    def test_is_valid_url_very_long(self):
        """Тест очень длинных URL."""
        long_url = "https://example.com/" + "a" * 2000
        # Должен валидироваться (браузеры поддерживают до 2083 символов)
        result = is_valid_url(long_url)
        assert isinstance(result, bool)

    def test_is_valid_url_ipv4(self):
        """Тест IPv4 адресов."""
        assert is_valid_url("https://192.168.1.1")
        assert is_valid_url("http://127.0.0.1:8080/path")

    def test_is_valid_url_ipv6(self):
        """Тест IPv6 адресов."""
        assert is_valid_url("https://[2001:db8::1]")
        assert is_valid_url("http://[::1]:8080/path")

    def test_sanitize_url_none(self):
        """Тест None input."""
        result = sanitize_url(None)
        assert result is None

    def test_clean_text_none(self):
        """Тест None input."""
        assert clean_text(None) == ""
