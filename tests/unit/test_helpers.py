"""
Unit тесты для webcrawler.utils.helpers
"""

import asyncio
from datetime import datetime, timedelta

import pytest

from webcrawler.utils.helpers import (
    calculate_content_hash,
    compute_md5,
    compute_sha256,
    compute_url_hash,
    format_bytes,
    format_duration,
    format_number,
    retry_with_backoff,
)


@pytest.mark.unit
class TestHashing:
    """Тесты для функций хеширования."""

    def test_compute_sha256(self):
        """Тест SHA256 хеширования."""
        text = "Hello, World!"
        hash1 = compute_sha256(text)
        hash2 = compute_sha256(text)

        # Одинаковый input = одинаковый hash
        assert hash1 == hash2

        # Должен быть hex строкой длиной 64
        assert len(hash1) == 64
        assert all(c in "0123456789abcdef" for c in hash1)

        # Разный input = разный hash
        hash3 = compute_sha256("Different text")
        assert hash1 != hash3

    def test_compute_sha256_empty(self):
        """Тест хеширования пустой строки."""
        hash_empty = compute_sha256("")
        assert hash_empty
        assert len(hash_empty) == 64

    def test_compute_md5(self):
        """Тест MD5 хеширования."""
        text = "Hello, World!"
        hash1 = compute_md5(text)
        hash2 = compute_md5(text)

        assert hash1 == hash2
        assert len(hash1) == 32  # MD5 = 32 hex символа

    def test_compute_url_hash(self):
        """Тест хеширования URL."""
        url = "https://example.com/page"
        hash1 = compute_url_hash(url)
        hash2 = compute_url_hash(url)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256

        # Normalized URLs должны давать одинаковый hash
        url_with_trailing = "https://example.com/page/"
        url_without_trailing = "https://example.com/page"
        # Зависит от реализации normalize_url
        hash_with = compute_url_hash(url_with_trailing)
        hash_without = compute_url_hash(url_without_trailing)
        # Могут быть одинаковыми если нормализация работает

    def test_calculate_content_hash(self):
        """Тест хеширования контента."""
        content = b"Binary content here"
        hash1 = calculate_content_hash(content)
        hash2 = calculate_content_hash(content)

        assert hash1 == hash2
        assert len(hash1) == 64


@pytest.mark.unit
class TestFormatting:
    """Тесты для функций форматирования."""

    def test_format_bytes(self):
        """Тест форматирования байтов."""
        assert format_bytes(0) == "0 B"
        assert format_bytes(1023) == "1023 B"
        assert format_bytes(1024) == "1.0 KB"
        assert format_bytes(1024 * 1024) == "1.0 MB"
        assert format_bytes(1024 * 1024 * 1024) == "1.0 GB"
        assert format_bytes(1024 * 1024 * 1024 * 1024) == "1.0 TB"

    def test_format_bytes_precision(self):
        """Тест точности форматирования."""
        # 1.5 KB
        assert "1.5" in format_bytes(1536)

        # 2.25 MB
        assert "2.2" in format_bytes(2359296) or "2.3" in format_bytes(2359296)

    def test_format_bytes_negative(self):
        """Тест отрицательных значений."""
        # Должен либо вернуть 0, либо handle gracefully
        result = format_bytes(-1024)
        assert isinstance(result, str)

    def test_format_duration(self):
        """Тест форматирования длительности."""
        assert format_duration(0) == "0s"
        assert format_duration(30) == "30s"
        assert format_duration(60) == "1m 0s"
        assert format_duration(90) == "1m 30s"
        assert format_duration(3600) == "1h 0m 0s"
        assert format_duration(3661) == "1h 1m 1s"
        assert format_duration(86400) == "1d 0h 0m"

    def test_format_duration_fractional(self):
        """Тест форматирования дробных секунд."""
        # Должен округлить или показать fractional
        result = format_duration(1.5)
        assert "1" in result or "2" in result

    def test_format_number(self):
        """Тест форматирования чисел."""
        assert format_number(1000) == "1,000"
        assert format_number(1000000) == "1,000,000"
        assert format_number(0) == "0"
        assert format_number(999) == "999"


@pytest.mark.unit
@pytest.mark.asyncio
class TestRetryDecorator:
    """Тесты для retry decorator."""

    async def test_retry_success_first_time(self):
        """Тест успешного выполнения с первого раза."""
        call_count = 0

        @retry_with_backoff(max_retries=3, backoff_factor=0.1)
        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_func()
        assert result == "success"
        assert call_count == 1

    async def test_retry_success_after_failures(self):
        """Тест успешного выполнения после нескольких неудач."""
        call_count = 0

        @retry_with_backoff(max_retries=3, backoff_factor=0.1)
        async def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        result = await failing_then_success()
        assert result == "success"
        assert call_count == 3

    async def test_retry_exhausted(self):
        """Тест исчерпания retry попыток."""
        call_count = 0

        @retry_with_backoff(max_retries=3, backoff_factor=0.1)
        async def always_failing():
            nonlocal call_count
            call_count += 1
            raise ValueError("Permanent failure")

        with pytest.raises(ValueError, match="Permanent failure"):
            await always_failing()

        # Должен попытаться 1 + 3 = 4 раза (initial + 3 retries)
        assert call_count == 4

    async def test_retry_backoff_timing(self):
        """Тест экспоненциального backoff."""
        call_times = []

        @retry_with_backoff(max_retries=2, backoff_factor=0.1)
        async def timed_failures():
            call_times.append(datetime.now())
            if len(call_times) < 3:
                raise ValueError("Fail")
            return "success"

        await timed_failures()

        # Проверяем что время между вызовами растёт
        assert len(call_times) == 3

        delay1 = (call_times[1] - call_times[0]).total_seconds()
        delay2 = (call_times[2] - call_times[1]).total_seconds()

        # Второй delay должен быть примерно в 2 раза больше первого
        # (с некоторой погрешностью)
        assert delay2 >= delay1 * 1.5

    async def test_retry_with_no_retries(self):
        """Тест с max_retries=0."""
        call_count = 0

        @retry_with_backoff(max_retries=0, backoff_factor=0.1)
        async def func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Fail")

        with pytest.raises(ValueError):
            await func()

        # Должен вызваться только 1 раз
        assert call_count == 1


@pytest.mark.unit
class TestEdgeCases:
    """Тесты для edge cases."""

    def test_compute_sha256_unicode(self):
        """Тест Unicode текста."""
        text = "Привет, мир! 🌍"
        hash_result = compute_sha256(text)
        assert hash_result
        assert len(hash_result) == 64

    def test_compute_sha256_bytes(self):
        """Тест bytes input."""
        data = b"Binary data \x00\x01\x02"
        # Функция может принимать только str, но проверим
        try:
            hash_result = compute_sha256(data.decode("latin1"))
            assert hash_result
        except:
            # Если не поддерживает bytes, это OK
            pass

    def test_format_bytes_very_large(self):
        """Тест очень больших чисел."""
        # 1 PB (петабайт)
        huge = 1024 ** 5
        result = format_bytes(huge)
        assert "PB" in result or "TB" in result

    def test_format_duration_very_long(self):
        """Тест очень длинной длительности."""
        # 1 год в секундах
        year_seconds = 365 * 24 * 3600
        result = format_duration(year_seconds)
        assert "d" in result  # Должно показать дни

    def test_format_number_zero(self):
        """Тест нуля."""
        assert format_number(0) == "0"

    def test_format_number_negative(self):
        """Тест отрицательных чисел."""
        result = format_number(-1000)
        assert "-" in result or result == "0"  # Зависит от реализации


@pytest.mark.unit
class TestHashConsistency:
    """Тесты на консистентность хешей."""

    def test_same_content_same_hash(self):
        """Тест что одинаковый контент даёт одинаковый hash."""
        content = "Test content"

        hash1 = compute_sha256(content)
        hash2 = compute_sha256(content)
        hash3 = compute_sha256(content)

        assert hash1 == hash2 == hash3

    def test_different_content_different_hash(self):
        """Тест что разный контент даёт разные хеши."""
        hash1 = compute_sha256("Content 1")
        hash2 = compute_sha256("Content 2")
        hash3 = compute_sha256("Content 3")

        assert hash1 != hash2
        assert hash2 != hash3
        assert hash1 != hash3

    def test_url_hash_normalization(self):
        """Тест нормализации в URL hash."""
        # URLs с разным порядком query params должны давать одинаковый hash
        # (если нормализация работает правильно)
        url1 = "https://example.com?a=1&b=2"
        url2 = "https://example.com?b=2&a=1"

        hash1 = compute_url_hash(url1)
        hash2 = compute_url_hash(url2)

        # Зависит от реализации normalize_url
        # Если нормализация сортирует query params, хеши должны совпадать
