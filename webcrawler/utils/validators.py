"""
Модуль для валидации URL, доменов и других данных.

Обеспечивает безопасность и корректность обрабатываемых данных.
"""

import ipaddress
import re
from typing import Optional
from urllib.parse import urlparse, urlunparse

from webcrawler.utils.logger import get_logger

logger = get_logger(__name__)


class ValidationError(Exception):
    """Исключение для ошибок валидации."""

    pass


def is_valid_url(url: str, allow_fragments: bool = True) -> bool:
    """
    Проверить, является ли строка валидным URL.

    Args:
        url: URL для проверки
        allow_fragments: Разрешить фрагменты (#section)

    Returns:
        bool: True если URL валиден

    Example:
        >>> is_valid_url("https://example.com/page")
        True
        >>> is_valid_url("not-a-url")
        False
        >>> is_valid_url("https://example.com#section", allow_fragments=False)
        False
    """
    try:
        result = urlparse(url)

        # Проверяем наличие схемы и сетевого адреса
        if not all([result.scheme, result.netloc]):
            return False

        # Проверяем схему
        if result.scheme not in ["http", "https", "ftp", "ftps"]:
            return False

        # Проверяем фрагменты, если запрещены
        if not allow_fragments and result.fragment:
            return False

        return True

    except (ValueError, AttributeError):
        return False


def normalize_url(url: str, remove_fragment: bool = True, remove_query: bool = False) -> str:
    """
    Нормализовать URL для дедупликации.

    Выполняет каноникализацию URL:
    - Приводит схему и домен к lowercase
    - Удаляет trailing slash
    - Опционально удаляет фрагменты и query параметры
    - Удаляет дефолтные порты (80, 443)

    Args:
        url: URL для нормализации
        remove_fragment: Удалить фрагмент (#section)
        remove_query: Удалить query параметры (?key=value)

    Returns:
        str: Нормализованный URL

    Raises:
        ValidationError: Если URL невалиден

    Example:
        >>> normalize_url("HTTPS://Example.com:443/Path/?query=1#fragment")
        'https://example.com/path'
        >>> normalize_url("http://example.com:8080/path/")
        'http://example.com:8080/path'
    """
    if not is_valid_url(url):
        raise ValidationError(f"Невалидный URL: {url}")

    parsed = urlparse(url)

    # Нормализация схемы и хоста
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Удаление дефолтных портов
    if (scheme == "http" and netloc.endswith(":80")) or \
       (scheme == "https" and netloc.endswith(":443")):
        netloc = netloc.rsplit(":", 1)[0]

    # Нормализация пути
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # Обработка query и fragment
    query = "" if remove_query else parsed.query
    fragment = "" if remove_fragment else parsed.fragment

    # Собираем обратно
    normalized = urlunparse((scheme, netloc, path, parsed.params, query, fragment))

    logger.debug("url_normalized", original=url, normalized=normalized)
    return normalized


def is_same_domain(url1: str, url2: str, include_subdomains: bool = True) -> bool:
    """
    Проверить, принадлежат ли два URL одному домену.

    Args:
        url1: Первый URL
        url2: Второй URL
        include_subdomains: Считать поддомены тем же доменом

    Returns:
        bool: True если домены совпадают

    Example:
        >>> is_same_domain("https://example.com/page1", "https://example.com/page2")
        True
        >>> is_same_domain("https://sub.example.com", "https://example.com", include_subdomains=True)
        True
        >>> is_same_domain("https://sub.example.com", "https://example.com", include_subdomains=False)
        False
    """
    try:
        domain1 = extract_domain(url1, include_subdomain=not include_subdomains)
        domain2 = extract_domain(url2, include_subdomain=not include_subdomains)
        return domain1 == domain2
    except ValidationError:
        return False


def extract_domain(url: str, include_subdomain: bool = True) -> str:
    """
    Извлечь домен из URL.

    Args:
        url: URL для обработки
        include_subdomain: Включать поддомен в результат

    Returns:
        str: Доменное имя

    Raises:
        ValidationError: Если URL невалиден

    Example:
        >>> extract_domain("https://blog.example.com/page", include_subdomain=True)
        'blog.example.com'
        >>> extract_domain("https://blog.example.com/page", include_subdomain=False)
        'example.com'
    """
    if not is_valid_url(url):
        raise ValidationError(f"Невалидный URL: {url}")

    parsed = urlparse(url)
    hostname = parsed.netloc.split(":")[0]  # Удаляем порт, если есть

    if not include_subdomain:
        # Извлекаем только основной домен (example.com из blog.example.com)
        parts = hostname.split(".")
        if len(parts) >= 2:
            hostname = ".".join(parts[-2:])

    return hostname


def is_ip_address(value: str) -> bool:
    """
    Проверить, является ли строка IP адресом.

    Args:
        value: Строка для проверки

    Returns:
        bool: True если это IP адрес (IPv4 или IPv6)

    Example:
        >>> is_ip_address("192.168.1.1")
        True
        >>> is_ip_address("2001:db8::1")
        True
        >>> is_ip_address("example.com")
        False
    """
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def is_valid_email(email: str) -> bool:
    """
    Проверить, является ли строка валидным email адресом.

    Args:
        email: Email для проверки

    Returns:
        bool: True если email валиден

    Example:
        >>> is_valid_email("user@example.com")
        True
        >>> is_valid_email("invalid-email")
        False
    """
    # Простая регулярка для базовой валидации email
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def is_absolute_url(url: str) -> bool:
    """
    Проверить, является ли URL абсолютным.

    Args:
        url: URL для проверки

    Returns:
        bool: True если URL абсолютный

    Example:
        >>> is_absolute_url("https://example.com/page")
        True
        >>> is_absolute_url("/relative/path")
        False
        >>> is_absolute_url("//example.com/path")
        False
    """
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme and parsed.netloc)
    except (ValueError, AttributeError):
        return False


def is_honeypot_url(url: str) -> bool:
    """
    Детектировать потенциальные honeypot ловушки.

    Honeypot - это URL-ловушки для выявления ботов.
    Обычно они спрятаны через CSS или содержат подозрительные паттерны.

    Args:
        url: URL для проверки

    Returns:
        bool: True если URL похож на honeypot

    Example:
        >>> is_honeypot_url("https://example.com/admin/delete_all")
        True
        >>> is_honeypot_url("https://example.com/trap")
        True
    """
    # Паттерны подозрительных URL
    suspicious_patterns = [
        r'/trap',
        r'/honeypot',
        r'/admin/(delete|remove|destroy)',
        r'/wp-admin',
        r'/phpmyadmin',
        r'/\.env',
        r'/\.git',
        r'/backup',
        r'/temp',
        r'/test',
    ]

    url_lower = url.lower()

    for pattern in suspicious_patterns:
        if re.search(pattern, url_lower):
            logger.warning("honeypot_detected", url=url, pattern=pattern)
            return True

    return False


def sanitize_url(url: str) -> str:
    """
    Санитизировать URL для безопасности.

    Удаляет потенциально опасные элементы:
    - JavaScript в URL
    - Data URIs
    - Странные схемы

    Args:
        url: URL для санитизации

    Returns:
        str: Безопасный URL

    Raises:
        ValidationError: Если URL содержит опасные элементы

    Example:
        >>> sanitize_url("https://example.com/page")
        'https://example.com/page'
        >>> sanitize_url("javascript:alert(1)")
        Traceback (most recent call last):
        ...
        ValidationError: URL содержит опасную схему: javascript
    """
    if not url:
        raise ValidationError("URL не может быть пустым")

    parsed = urlparse(url)

    # Проверка схемы
    dangerous_schemes = ["javascript", "data", "file", "vbscript"]
    if parsed.scheme.lower() in dangerous_schemes:
        raise ValidationError(f"URL содержит опасную схему: {parsed.scheme}")

    # Разрешённые схемы
    allowed_schemes = ["http", "https", "ftp", "ftps"]
    if parsed.scheme and parsed.scheme.lower() not in allowed_schemes:
        raise ValidationError(f"Недопустимая схема URL: {parsed.scheme}")

    return url


def is_file_extension_allowed(url: str, allowed_extensions: list[str]) -> bool:
    """
    Проверить, соответствует ли расширение файла разрешённым.

    Args:
        url: URL для проверки
        allowed_extensions: Список разрешённых расширений (без точки)

    Returns:
        bool: True если расширение разрешено или отсутствует

    Example:
        >>> is_file_extension_allowed("https://example.com/file.pdf", ["pdf", "html"])
        True
        >>> is_file_extension_allowed("https://example.com/file.exe", ["pdf", "html"])
        False
        >>> is_file_extension_allowed("https://example.com/page", ["html"])
        True
    """
    parsed = urlparse(url)
    path = parsed.path.lower()

    # Если нет расширения, считаем что это HTML страница
    if "." not in path.split("/")[-1]:
        return True

    # Извлекаем расширение
    extension = path.split(".")[-1]

    # Убираем query параметры из расширения, если есть
    extension = extension.split("?")[0]

    return extension in [ext.lower() for ext in allowed_extensions]


def validate_content_type(content_type: str, allowed_types: list[str]) -> bool:
    """
    Проверить, соответствует ли Content-Type разрешённым типам.

    Поддерживает wildcards (например, "image/*").

    Args:
        content_type: Content-Type для проверки
        allowed_types: Список разрешённых типов (может содержать *)

    Returns:
        bool: True если тип разрешён

    Example:
        >>> validate_content_type("text/html; charset=utf-8", ["text/html"])
        True
        >>> validate_content_type("image/png", ["image/*"])
        True
        >>> validate_content_type("application/pdf", ["text/*"])
        False
    """
    # Убираем параметры из content-type
    content_type = content_type.split(";")[0].strip().lower()

    for allowed_type in allowed_types:
        allowed_type = allowed_type.lower()

        # Точное совпадение
        if content_type == allowed_type:
            return True

        # Wildcard совпадение
        if allowed_type.endswith("/*"):
            category = allowed_type.split("/")[0]
            if content_type.startswith(f"{category}/"):
                return True

    return False


def is_safe_path(path: str) -> bool:
    """
    Проверить путь на path traversal атаки.

    Детектирует попытки выхода за пределы разрешённой директории
    через ../ и подобные конструкции.

    Args:
        path: Путь для проверки

    Returns:
        bool: True если путь безопасен

    Example:
        >>> is_safe_path("/normal/path/file.txt")
        True
        >>> is_safe_path("../../../etc/passwd")
        False
        >>> is_safe_path("/path/../other/file.txt")
        False
    """
    # Проверка на path traversal
    if ".." in path:
        logger.warning("path_traversal_detected", path=path)
        return False

    # Проверка на абсолютные пути за пределами разрешённой области
    # (зависит от контекста использования)
    return True
