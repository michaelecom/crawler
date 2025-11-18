"""
Вспомогательные функции общего назначения.

Утилиты для работы со строками, датами, хешами и другими часто используемыми операциями.
"""

import hashlib
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse


def calculate_content_hash(content: bytes, algorithm: str = "sha256") -> str:
    """
    Вычислить хеш контента для детектирования дубликатов.

    Args:
        content: Байтовое содержимое для хеширования
        algorithm: Алгоритм хеширования (md5, sha1, sha256, sha512)

    Returns:
        str: Хеш в hex формате

    Example:
        >>> content = b"Hello, World!"
        >>> hash_value = calculate_content_hash(content)
        >>> len(hash_value)
        64
        >>> calculate_content_hash(content, "md5")
        '65a8e27d8879283831b664bd8b7f0ad4'
    """
    hasher = hashlib.new(algorithm)
    hasher.update(content)
    return hasher.hexdigest()


def format_bytes(num_bytes: int) -> str:
    """
    Форматировать размер в байтах в человекочитаемый вид.

    Args:
        num_bytes: Размер в байтах

    Returns:
        str: Отформатированная строка

    Example:
        >>> format_bytes(1024)
        '1.00 KB'
        >>> format_bytes(1048576)
        '1.00 MB'
        >>> format_bytes(1073741824)
        '1.00 GB'
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num_bytes < 1024.0:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.2f} PB"


def format_duration(seconds: float) -> str:
    """
    Форматировать продолжительность в человекочитаемый вид.

    Args:
        seconds: Количество секунд

    Returns:
        str: Отформатированная строка

    Example:
        >>> format_duration(65)
        '1m 5s'
        >>> format_duration(3661)
        '1h 1m 1s'
        >>> format_duration(0.5)
        '500ms'
    """
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"

    parts = []
    remaining = int(seconds)

    hours = remaining // 3600
    if hours:
        parts.append(f"{hours}h")
        remaining %= 3600

    minutes = remaining // 60
    if minutes:
        parts.append(f"{minutes}m")
        remaining %= 60

    if remaining or not parts:
        parts.append(f"{remaining}s")

    return " ".join(parts)


def parse_datetime(date_string: str) -> Optional[datetime]:
    """
    Парсить строку даты в datetime объект.

    Поддерживает различные форматы дат.

    Args:
        date_string: Строка с датой

    Returns:
        Optional[datetime]: Объект datetime или None при ошибке

    Example:
        >>> dt = parse_datetime("2025-01-15 10:30:00")
        >>> dt.year
        2025
    """
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d.%m.%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue

    return None


def join_url(base: str, relative: str) -> str:
    """
    Безопасно объединить базовый URL с относительным путём.

    Args:
        base: Базовый URL
        relative: Относительный путь

    Returns:
        str: Полный URL

    Example:
        >>> join_url("https://example.com/path/", "subpath")
        'https://example.com/path/subpath'
        >>> join_url("https://example.com/path", "../other")
        'https://example.com/other'
    """
    return urljoin(base, relative)


def extract_links_from_text(text: str, base_url: Optional[str] = None) -> list[str]:
    """
    Извлечь все URL из текста (простой парсинг).

    Args:
        text: Текст для поиска URL
        base_url: Базовый URL для преобразования относительных ссылок

    Returns:
        list[str]: Список найденных URL

    Example:
        >>> text = "Visit https://example.com and http://test.com"
        >>> extract_links_from_text(text)
        ['https://example.com', 'http://test.com']
    """
    import re

    # Простая регулярка для поиска URL
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, text)

    if base_url:
        # Преобразуем относительные ссылки
        urls = [join_url(base_url, url) if not url.startswith(("http://", "https://")) else url
                for url in urls]

    return list(set(urls))  # Удаляем дубликаты


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Обрезать строку до максимальной длины.

    Args:
        text: Текст для обрезания
        max_length: Максимальная длина
        suffix: Суффикс для добавления

    Returns:
        str: Обрезанная строка

    Example:
        >>> truncate_string("Very long text here", max_length=10)
        'Very lo...'
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def ensure_directory(path: str | Path) -> Path:
    """
    Убедиться, что директория существует, создать если нет.

    Args:
        path: Путь к директории

    Returns:
        Path: Объект Path для директории

    Example:
        >>> dir_path = ensure_directory("data/cache")
        >>> dir_path.exists()
        True
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def retry_with_backoff(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    initial_delay: float = 1.0
):
    """
    Декоратор для повтора функции с экспоненциальным backoff.

    Args:
        max_retries: Максимальное количество повторов
        backoff_factor: Множитель для задержки
        initial_delay: Начальная задержка в секундах

    Example:
        >>> @retry_with_backoff(max_retries=3, backoff_factor=2)
        ... async def fetch_data():
        ...     # код который может упасть
        ...     pass
    """
    import asyncio
    import functools
    from webcrawler.utils.logger import get_logger

    logger = get_logger(__name__)

    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            delay = initial_delay

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        logger.error(
                            "max_retries_exceeded",
                            function=func.__name__,
                            attempts=attempt + 1,
                            error=str(e)
                        )
                        raise

                    logger.warning(
                        "retry_attempt",
                        function=func.__name__,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay=delay,
                        error=str(e)
                    )

                    await asyncio.sleep(delay)
                    delay *= backoff_factor

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            delay = initial_delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        logger.error(
                            "max_retries_exceeded",
                            function=func.__name__,
                            attempts=attempt + 1,
                            error=str(e)
                        )
                        raise

                    logger.warning(
                        "retry_attempt",
                        function=func.__name__,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay=delay,
                        error=str(e)
                    )

                    time.sleep(delay)
                    delay *= backoff_factor

        # Возвращаем соответствующую обёртку
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def dict_merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    """
    Рекурсивно объединить два словаря.

    Args:
        base: Базовый словарь
        update: Словарь с обновлениями

    Returns:
        dict: Объединённый словарь

    Example:
        >>> base = {"a": 1, "b": {"c": 2}}
        >>> update = {"b": {"d": 3}, "e": 4}
        >>> dict_merge(base, update)
        {'a': 1, 'b': {'c': 2, 'd': 3}, 'e': 4}
    """
    result = base.copy()

    for key, value in update.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = dict_merge(result[key], value)
        else:
            result[key] = value

    return result


def clean_text(text: str) -> str:
    """
    Очистить текст от лишних пробелов и спецсимволов.

    Args:
        text: Текст для очистки

    Returns:
        str: Очищенный текст

    Example:
        >>> clean_text("  Hello   World  \\n\\n  ")
        'Hello World'
    """
    # Удаляем множественные пробелы
    import re
    text = re.sub(r'\s+', ' ', text)
    # Убираем пробелы в начале и конце
    text = text.strip()
    return text


def is_binary_content(content: bytes, sample_size: int = 8192) -> bool:
    """
    Определить, является ли контент бинарным (не текстовым).

    Args:
        content: Содержимое для проверки
        sample_size: Размер выборки для анализа

    Returns:
        bool: True если контент бинарный

    Example:
        >>> is_binary_content(b"Hello, World!")
        False
        >>> is_binary_content(b"\\x00\\x01\\x02\\xFF")
        True
    """
    # Проверяем первые sample_size байт
    sample = content[:sample_size]

    # Если есть null байты, скорее всего бинарный
    if b'\x00' in sample:
        return True

    # Подсчитываем непечатаемые символы
    text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x7F)))
    non_text = sum(1 for byte in sample if byte not in text_chars)

    # Если более 30% непечатаемых символов, считаем бинарным
    if non_text / len(sample) > 0.3:
        return True

    return False
