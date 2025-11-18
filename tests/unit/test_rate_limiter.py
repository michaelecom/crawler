"""
Unit тесты для webcrawler.utils.rate_limiter
"""

import asyncio
from datetime import datetime

import pytest

from webcrawler.utils.rate_limiter import RateLimiter, TokenBucketRateLimiter


@pytest.mark.unit
@pytest.mark.asyncio
class TestRateLimiter:
    """Тесты для RateLimiter."""

    async def test_rate_limiter_basic(self):
        """Тест базовой функциональности rate limiting."""
        limiter = RateLimiter(requests_per_second=10.0, max_concurrent_requests=5)

        # Должны пройти несколько запросов
        async with limiter.acquire("https://example.com"):
            pass

        async with limiter.acquire("https://example.com"):
            pass

    async def test_rate_limiter_per_domain(self):
        """Тест per-domain rate limiting."""
        limiter = RateLimiter(requests_per_second=2.0)

        domain1 = "https://example1.com"
        domain2 = "https://example2.com"

        # Запросы к разным доменам не должны влиять друг на друга
        start = datetime.now()

        async with limiter.acquire(domain1):
            pass

        async with limiter.acquire(domain2):
            pass

        elapsed = (datetime.now() - start).total_seconds()

        # Должно быть быстро (parallel)
        assert elapsed < 1.0

    async def test_rate_limiter_delay(self):
        """Тест задержки между запросами."""
        limiter = RateLimiter(requests_per_second=2.0, adaptive=False)

        url = "https://example.com"
        start = datetime.now()

        # 3 запроса с rate 2 req/sec
        for _ in range(3):
            async with limiter.acquire(url):
                pass

        elapsed = (datetime.now() - start).total_seconds()

        # Должно занять ~1 секунду (2 запроса без задержки + 1 с задержкой)
        # Даём погрешность
        assert elapsed >= 0.4  # Минимум half-second delay
        assert elapsed < 2.0  # Не должно быть слишком долго

    async def test_rate_limiter_concurrent_limit(self):
        """Тест ограничения конкурентных запросов."""
        max_concurrent = 3
        limiter = RateLimiter(
            requests_per_second=100.0,  # Высокий rate чтобы не мешал
            max_concurrent_requests=max_concurrent,
        )

        url = "https://example.com"
        active_count = 0
        max_active = 0

        async def task():
            nonlocal active_count, max_active
            async with limiter.acquire(url):
                active_count += 1
                max_active = max(max_active, active_count)
                await asyncio.sleep(0.1)
                active_count -= 1

        # Запускаем 10 concurrent tasks
        tasks = [task() for _ in range(10)]
        await asyncio.gather(*tasks)

        # Максимум concurrent должен быть <= max_concurrent
        assert max_active <= max_concurrent

    async def test_rate_limiter_adaptive_increase(self):
        """Тест увеличения задержки при ошибках."""
        limiter = RateLimiter(requests_per_second=10.0, adaptive=True)

        url = "https://example.com"

        # Получаем начальную задержку
        initial_delay = limiter.get_delay(url)

        # Увеличиваем задержку (simulate 429 error)
        limiter.adjust_delay(url, increase=True)

        # Задержка должна увеличиться
        new_delay = limiter.get_delay(url)
        assert new_delay > initial_delay

    async def test_rate_limiter_adaptive_decrease(self):
        """Тест уменьшения задержки при успехе."""
        limiter = RateLimiter(requests_per_second=1.0, adaptive=True)

        url = "https://example.com"

        # Увеличиваем задержку
        limiter.adjust_delay(url, increase=True)
        increased_delay = limiter.get_delay(url)

        # Уменьшаем задержку (successful request)
        limiter.adjust_delay(url, increase=False)

        decreased_delay = limiter.get_delay(url)
        assert decreased_delay < increased_delay

    async def test_rate_limiter_context_manager(self):
        """Тест использования как context manager."""
        limiter = RateLimiter(requests_per_second=10.0)

        url = "https://example.com"

        # Должен работать как async context manager
        async with limiter.acquire(url) as ctx:
            assert ctx is not None

    async def test_rate_limiter_multiple_domains(self):
        """Тест rate limiting для множественных доменов."""
        limiter = RateLimiter(requests_per_second=5.0)

        domains = [f"https://example{i}.com" for i in range(5)]

        # Запросы к разным доменам должны быть быстрыми
        start = datetime.now()

        tasks = [limiter.acquire(domain).__aenter__() for domain in domains]
        await asyncio.gather(*tasks)

        # Cleanup
        for task in tasks:
            await task.__aexit__(None, None, None)

        elapsed = (datetime.now() - start).total_seconds()

        # Должно быть быстро так как разные домены
        assert elapsed < 1.0


@pytest.mark.unit
@pytest.mark.asyncio
class TestTokenBucketRateLimiter:
    """Тесты для TokenBucketRateLimiter."""

    async def test_token_bucket_basic(self):
        """Тест базовой функциональности token bucket."""
        limiter = TokenBucketRateLimiter(
            rate=10.0,  # 10 tokens per second
            capacity=10,
        )

        # Должны пройти несколько запросов
        async with limiter.acquire():
            pass

        async with limiter.acquire():
            pass

    async def test_token_bucket_capacity(self):
        """Тест ограничения capacity."""
        capacity = 3
        limiter = TokenBucketRateLimiter(
            rate=1.0,  # 1 token per second
            capacity=capacity,
        )

        # Первые capacity запросов должны пройти быстро
        start = datetime.now()

        for _ in range(capacity):
            async with limiter.acquire():
                pass

        elapsed = (datetime.now() - start).total_seconds()

        # Должно быть быстро (использовали накопленные tokens)
        assert elapsed < 0.5

    async def test_token_bucket_refill(self):
        """Тест пополнения tokens."""
        limiter = TokenBucketRateLimiter(
            rate=5.0,  # 5 tokens per second
            capacity=5,
        )

        # Исчерпываем tokens
        for _ in range(5):
            async with limiter.acquire():
                pass

        # Ждём пополнения
        await asyncio.sleep(0.5)  # Должно добавить ~2.5 tokens

        # Следующий запрос должен пройти
        start = datetime.now()
        async with limiter.acquire():
            pass
        elapsed = (datetime.now() - start).total_seconds()

        # Должно быть быстро (есть tokens)
        assert elapsed < 0.2

    async def test_token_bucket_wait_for_token(self):
        """Тест ожидания tokens."""
        limiter = TokenBucketRateLimiter(
            rate=2.0,  # 2 tokens per second
            capacity=2,
        )

        # Исчерпываем tokens
        for _ in range(2):
            async with limiter.acquire():
                pass

        # Следующий запрос должен ждать
        start = datetime.now()
        async with limiter.acquire():
            pass
        elapsed = (datetime.now() - start).total_seconds()

        # Должно ждать ~0.5 секунды (для 1 token при rate 2/sec)
        assert elapsed >= 0.4


@pytest.mark.unit
@pytest.mark.asyncio
class TestRateLimiterEdgeCases:
    """Тесты edge cases для rate limiters."""

    async def test_rate_limiter_zero_delay(self):
        """Тест с нулевой задержкой."""
        limiter = RateLimiter(requests_per_second=1000.0)

        start = datetime.now()
        for _ in range(10):
            async with limiter.acquire("https://example.com"):
                pass
        elapsed = (datetime.now() - start).total_seconds()

        # Должно быть очень быстро
        assert elapsed < 0.5

    async def test_rate_limiter_very_slow(self):
        """Тест с очень медленным rate."""
        limiter = RateLimiter(requests_per_second=0.5, adaptive=False)

        url = "https://example.com"

        start = datetime.now()

        # 2 запроса
        async with limiter.acquire(url):
            pass

        async with limiter.acquire(url):
            pass

        elapsed = (datetime.now() - start).total_seconds()

        # Должно занять ~2 секунды (0.5 req/sec = 2 sec per req)
        # Первый запрос instant, второй ждёт 2 секунды
        assert elapsed >= 1.5

    async def test_rate_limiter_invalid_url(self):
        """Тест с невалидным URL."""
        limiter = RateLimiter()

        # Должен handle gracefully
        try:
            async with limiter.acquire("not a url"):
                pass
        except:
            # Может выбросить исключение или обработать
            pass

    async def test_token_bucket_negative_rate(self):
        """Тест создания с негативным rate."""
        # Должен либо raise ValueError, либо использовать default
        try:
            limiter = TokenBucketRateLimiter(rate=-1.0)
            # Если создался, rate должен быть позитивным
            assert limiter.rate > 0
        except ValueError:
            # Это тоже OK
            pass

    async def test_token_bucket_zero_capacity(self):
        """Тест с нулевым capacity."""
        try:
            limiter = TokenBucketRateLimiter(capacity=0)
            # Если создался, capacity должен быть > 0
            assert limiter.capacity > 0
        except ValueError:
            pass


@pytest.mark.unit
@pytest.mark.asyncio
class TestRateLimiterConcurrency:
    """Тесты конкурентности rate limiters."""

    async def test_concurrent_acquires_same_domain(self):
        """Тест concurrent acquires для одного домена."""
        limiter = RateLimiter(
            requests_per_second=5.0, max_concurrent_requests=10
        )

        url = "https://example.com"

        async def task():
            async with limiter.acquire(url):
                await asyncio.sleep(0.01)

        # Запускаем 20 concurrent tasks
        start = datetime.now()
        tasks = [task() for _ in range(20)]
        await asyncio.gather(*tasks)
        elapsed = (datetime.now() - start).total_seconds()

        # С rate 5 req/sec, 20 запросов должны занять ~4 секунды
        # (с некоторой погрешностью)
        assert elapsed >= 2.0  # Минимум
        assert elapsed < 6.0  # Максимум

    async def test_concurrent_acquires_different_domains(self):
        """Тест concurrent acquires для разных доменов."""
        limiter = RateLimiter(requests_per_second=5.0)

        async def task(domain_id):
            url = f"https://example{domain_id}.com"
            async with limiter.acquire(url):
                await asyncio.sleep(0.01)

        # 20 tasks для 20 разных доменов
        start = datetime.now()
        tasks = [task(i) for i in range(20)]
        await asyncio.gather(*tasks)
        elapsed = (datetime.now() - start).total_seconds()

        # Разные домены = параллельно, должно быть быстро
        assert elapsed < 1.0
