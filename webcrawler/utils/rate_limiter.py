"""
Модуль для контроля частоты запросов (rate limiting).

Реализует per-domain rate limiting с адаптивным управлением
для защиты от блокировки и перегрузки серверов.
"""

import asyncio
import time
from collections import defaultdict
from typing import DefaultDict, Optional

from webcrawler.utils.logger import get_logger
from webcrawler.utils.validators import extract_domain

logger = get_logger(__name__)


class RateLimiter:
    """
    Асинхронный rate limiter с поддержкой per-domain ограничений.

    Обеспечивает контроль частоты запросов к доменам для предотвращения
    блокировки и соблюдения этических норм краулинга.

    Example:
        >>> limiter = RateLimiter(requests_per_second=5.0, max_concurrent=100)
        >>> async with limiter.acquire("https://example.com"):
        ...     # выполнить запрос
        ...     pass
    """

    def __init__(
        self,
        requests_per_second: float = 5.0,
        max_concurrent_requests: int = 100,
        delay_between_requests: float = 0.2,
        adaptive: bool = True,
    ):
        """
        Инициализация rate limiter.

        Args:
            requests_per_second: Максимум запросов в секунду (per domain)
            max_concurrent_requests: Максимум конкурентных запросов (глобально)
            delay_between_requests: Минимальная задержка между запросами (секунды)
            adaptive: Включить адаптивное управление rate limiting
        """
        self.requests_per_second = requests_per_second
        self.max_concurrent_requests = max_concurrent_requests
        self.delay_between_requests = delay_between_requests
        self.adaptive = adaptive

        # Семафор для глобального ограничения конкурентности
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)

        # Per-domain состояние
        self.last_request_time: DefaultDict[str, float] = defaultdict(float)
        self.domain_delays: DefaultDict[str, float] = defaultdict(
            lambda: delay_between_requests
        )
        self.domain_locks: DefaultDict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Статистика
        self.total_requests = 0
        self.blocked_count = 0
        self.slowdown_count = 0

        logger.info(
            "rate_limiter_initialized",
            requests_per_second=requests_per_second,
            max_concurrent=max_concurrent_requests,
            adaptive=adaptive
        )

    async def acquire(self, url: str) -> "RateLimiterContext":
        """
        Получить разрешение на выполнение запроса к URL.

        Args:
            url: URL для запроса

        Returns:
            RateLimiterContext: Контекстный менеджер для rate limiting

        Example:
            >>> async with limiter.acquire("https://example.com/page"):
            ...     response = await fetch(url)
        """
        domain = extract_domain(url, include_subdomain=False)
        return RateLimiterContext(self, domain, url)

    async def _wait_for_domain(self, domain: str) -> None:
        """
        Ожидание согласно rate limiting для домена.

        Args:
            domain: Доменное имя

        Реализует:
        - Per-domain задержки
        - Адаптивное управление
        - Защиту от race conditions через locks
        """
        async with self.domain_locks[domain]:
            current_time = time.time()
            last_request = self.last_request_time[domain]
            delay = self.domain_delays[domain]

            # Минимальный интервал между запросами для этого домена
            min_interval = 1.0 / self.requests_per_second

            # Вычисляем необходимую задержку
            if last_request > 0:
                elapsed = current_time - last_request
                required_delay = max(min_interval, delay)

                if elapsed < required_delay:
                    wait_time = required_delay - elapsed
                    logger.debug(
                        "rate_limiting_wait",
                        domain=domain,
                        wait_seconds=round(wait_time, 3)
                    )
                    await asyncio.sleep(wait_time)

            # Обновляем время последнего запроса
            self.last_request_time[domain] = time.time()
            self.total_requests += 1

    def adjust_delay(self, domain: str, increase: bool = False) -> None:
        """
        Адаптивная настройка задержки для домена.

        Args:
            domain: Доменное имя
            increase: True для увеличения задержки, False для уменьшения

        Example:
            >>> # При получении 429 Too Many Requests
            >>> limiter.adjust_delay("example.com", increase=True)
            >>> # При успешном запросе
            >>> limiter.adjust_delay("example.com", increase=False)
        """
        if not self.adaptive:
            return

        current_delay = self.domain_delays[domain]

        if increase:
            # Увеличиваем задержку при ошибках (экспоненциально)
            new_delay = min(current_delay * 2.0, 10.0)  # максимум 10 секунд
            self.slowdown_count += 1
            logger.warning(
                "rate_limit_increased",
                domain=domain,
                old_delay=round(current_delay, 3),
                new_delay=round(new_delay, 3)
            )
        else:
            # Постепенно уменьшаем задержку при успешных запросах
            new_delay = max(current_delay * 0.9, self.delay_between_requests)
            logger.debug(
                "rate_limit_decreased",
                domain=domain,
                old_delay=round(current_delay, 3),
                new_delay=round(new_delay, 3)
            )

        self.domain_delays[domain] = new_delay

    def report_blocked(self, domain: str) -> None:
        """
        Сообщить о блокировке со стороны домена.

        Значительно увеличивает задержку для защиты.

        Args:
            domain: Доменное имя

        Example:
            >>> # При получении HTTP 429 или блокировке
            >>> limiter.report_blocked("example.com")
        """
        self.blocked_count += 1
        current_delay = self.domain_delays[domain]
        new_delay = min(current_delay * 5.0, 60.0)  # максимум 1 минута

        self.domain_delays[domain] = new_delay

        logger.error(
            "domain_blocked",
            domain=domain,
            new_delay=round(new_delay, 3),
            total_blocks=self.blocked_count
        )

    def get_stats(self) -> dict:
        """
        Получить статистику rate limiter.

        Returns:
            dict: Словарь со статистикой

        Example:
            >>> stats = limiter.get_stats()
            >>> print(stats["total_requests"])
            1234
        """
        return {
            "total_requests": self.total_requests,
            "blocked_count": self.blocked_count,
            "slowdown_count": self.slowdown_count,
            "tracked_domains": len(self.last_request_time),
            "requests_per_second": self.requests_per_second,
            "max_concurrent": self.max_concurrent_requests,
        }

    def reset_domain(self, domain: str) -> None:
        """
        Сбросить статистику для домена.

        Args:
            domain: Доменное имя

        Example:
            >>> limiter.reset_domain("example.com")
        """
        if domain in self.last_request_time:
            del self.last_request_time[domain]
        if domain in self.domain_delays:
            del self.domain_delays[domain]

        logger.info("rate_limiter_domain_reset", domain=domain)


class RateLimiterContext:
    """
    Контекстный менеджер для rate limiting запроса.

    Автоматически управляет семафором и per-domain задержками.
    """

    def __init__(self, limiter: RateLimiter, domain: str, url: str):
        """
        Инициализация контекста.

        Args:
            limiter: Экземпляр RateLimiter
            domain: Доменное имя
            url: Полный URL
        """
        self.limiter = limiter
        self.domain = domain
        self.url = url
        self.start_time: Optional[float] = None

    async def __aenter__(self):
        """Вход в контекст - ожидание разрешения."""
        # Глобальное ограничение конкурентности
        await self.limiter.semaphore.acquire()

        # Per-domain rate limiting
        await self.limiter._wait_for_domain(self.domain)

        self.start_time = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Выход из контекста - освобождение ресурсов."""
        # Освобождаем семафор
        self.limiter.semaphore.release()

        # Адаптивная настройка задержки
        if self.limiter.adaptive:
            if exc_type is None:
                # Успешный запрос - можно немного уменьшить задержку
                self.limiter.adjust_delay(self.domain, increase=False)
            elif exc_type.__name__ in ["HTTPError", "TooManyRequests"]:
                # Ошибка rate limiting - увеличиваем задержку
                self.limiter.adjust_delay(self.domain, increase=True)

        # Логируем продолжительность
        if self.start_time:
            duration = time.time() - self.start_time
            logger.debug(
                "request_completed",
                url=self.url,
                domain=self.domain,
                duration=round(duration, 3),
                error=exc_type.__name__ if exc_type else None
            )

        return False  # Не подавляем исключения


class TokenBucketRateLimiter:
    """
    Rate limiter на основе алгоритма Token Bucket.

    Более гибкий, чем простой rate limiter, позволяет "всплески" трафика.

    Example:
        >>> limiter = TokenBucketRateLimiter(rate=10, capacity=20)
        >>> async with limiter.acquire():
        ...     # выполнить запрос
        ...     pass
    """

    def __init__(self, rate: float, capacity: int):
        """
        Инициализация Token Bucket rate limiter.

        Args:
            rate: Скорость пополнения токенов (токенов в секунду)
            capacity: Максимальная вместимость bucket
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_update = time.time()
        self.lock = asyncio.Lock()

        logger.info(
            "token_bucket_initialized",
            rate=rate,
            capacity=capacity
        )

    async def acquire(self, tokens: int = 1):
        """
        Получить токены из bucket.

        Args:
            tokens: Количество токенов

        Returns:
            TokenBucketContext: Контекстный менеджер

        Example:
            >>> async with limiter.acquire(tokens=2):
            ...     # выполнить более "тяжёлый" запрос
            ...     pass
        """
        async with self.lock:
            current_time = time.time()
            elapsed = current_time - self.last_update

            # Пополняем токены
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.rate
            )
            self.last_update = current_time

            # Если недостаточно токенов, ждём
            if self.tokens < tokens:
                wait_time = (tokens - self.tokens) / self.rate
                logger.debug(
                    "token_bucket_wait",
                    required_tokens=tokens,
                    available=round(self.tokens, 2),
                    wait_seconds=round(wait_time, 3)
                )
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= tokens

        return TokenBucketContext(self, tokens)


class TokenBucketContext:
    """Контекстный менеджер для Token Bucket."""

    def __init__(self, limiter: TokenBucketRateLimiter, tokens: int):
        """Инициализация контекста."""
        self.limiter = limiter
        self.tokens = tokens

    async def __aenter__(self):
        """Вход в контекст."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Выход из контекста."""
        # При ошибке можем вернуть токены (опционально)
        return False
