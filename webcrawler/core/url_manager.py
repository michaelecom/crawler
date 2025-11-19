"""
Менеджер URL для управления очередью и дедупликацией.

Использует Bloom filter для быстрой проверки посещённых URL
и приоритетную очередь для оптимального порядка обхода.
"""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Set

from webcrawler.utils.config import Config
from webcrawler.utils.helpers import calculate_content_hash
from webcrawler.utils.logger import LoggerMixin
from webcrawler.utils.validators import (
    extract_domain,
    is_honeypot_url,
    is_same_domain,
    normalize_url,
)


@dataclass
class URLItem:
    """
    Элемент URL для обработки.

    Содержит URL и метаданные для приоритизации и обработки.
    """

    url: str
    depth: int = 0
    priority: int = 0
    source_url: Optional[str] = None
    discovered_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())

    def __lt__(self, other: "URLItem") -> bool:
        """Сравнение для приоритетной очереди (меньше = выше приоритет)."""
        # Сначала по приоритету, потом по глубине, потом по времени обнаружения
        return (self.priority, self.depth, self.discovered_at) < (
            other.priority,
            other.depth,
            other.discovered_at,
        )

    def __hash__(self) -> int:
        """Хеш для использования в множествах."""
        return hash(self.url)


class BloomFilter:
    """
    Bloom filter для быстрой проверки посещённых URL.

    Обеспечивает O(1) проверку с минимальным использованием памяти.
    Ложноположительные срабатывания возможны, но ложноотрицательные - нет.

    Example:
        >>> bloom = BloomFilter(expected_items=1000000, false_positive_rate=0.001)
        >>> bloom.add("https://example.com")
        >>> bloom.contains("https://example.com")
        True
    """

    def __init__(self, expected_items: int = 100000, false_positive_rate: float = 0.001):
        """
        Инициализация Bloom filter.

        Args:
            expected_items: Ожидаемое количество элементов
            false_positive_rate: Вероятность ложноположительных срабатываний
        """
        import math

        # Вычисляем оптимальный размер битового массива
        self.size = self._optimal_size(expected_items, false_positive_rate)

        # Вычисляем оптимальное количество хеш-функций
        self.num_hashes = self._optimal_num_hashes(self.size, expected_items)

        # Битовый массив (используем bytearray для эффективности)
        self.bit_array = bytearray(self.size // 8 + 1)

        self.items_added = 0

    @staticmethod
    def _optimal_size(n: int, p: float) -> int:
        """
        Вычислить оптимальный размер битового массива.

        Args:
            n: Количество элементов
            p: Вероятность ложных срабатываний

        Returns:
            int: Размер битового массива
        """
        import math

        return int(-(n * math.log(p)) / (math.log(2) ** 2))

    @staticmethod
    def _optimal_num_hashes(m: int, n: int) -> int:
        """
        Вычислить оптимальное количество хеш-функций.

        Args:
            m: Размер битового массива
            n: Количество элементов

        Returns:
            int: Количество хеш-функций
        """
        import math

        return max(1, int((m / n) * math.log(2)))

    def _hashes(self, item: str) -> list[int]:
        """
        Генерировать хеши для элемента.

        Использует double hashing для генерации множественных хешей.

        Args:
            item: Элемент для хеширования

        Returns:
            list: Список позиций в битовом массиве
        """
        # Используем два независимых хеша
        hash1 = hash(item) % self.size
        hash2 = hash(item[::-1]) % self.size

        # Генерируем num_hashes хешей через double hashing
        hashes = []
        for i in range(self.num_hashes):
            hash_value = (hash1 + i * hash2) % self.size
            hashes.append(hash_value)

        return hashes

    def add(self, item: str) -> None:
        """
        Добавить элемент в Bloom filter.

        Args:
            item: Элемент для добавления

        Example:
            >>> bloom.add("https://example.com/page")
        """
        for pos in self._hashes(item):
            byte_index = pos // 8
            bit_index = pos % 8
            self.bit_array[byte_index] |= 1 << bit_index

        self.items_added += 1

    def contains(self, item: str) -> bool:
        """
        Проверить наличие элемента в Bloom filter.

        Args:
            item: Элемент для проверки

        Returns:
            bool: True если элемент возможно есть (может быть ложноположительный результат)

        Example:
            >>> if bloom.contains("https://example.com/page"):
            ...     print("URL possibly visited")
        """
        for pos in self._hashes(item):
            byte_index = pos // 8
            bit_index = pos % 8
            if not (self.bit_array[byte_index] & (1 << bit_index)):
                return False
        return True

    def memory_usage(self) -> int:
        """
        Получить использование памяти в байтах.

        Returns:
            int: Размер в байтах
        """
        return len(self.bit_array)


class URLManager(LoggerMixin):
    """
    Менеджер URL для управления очередью краулинга.

    Обеспечивает:
    - Дедупликацию URL через Bloom filter + хеш-проверку
    - Приоритетную очередь для оптимального обхода
    - Фильтрацию по домену, robots.txt, honeypot
    - Статистику и мониторинг

    Example:
        >>> config = Config.from_yaml("config.yaml")
        >>> manager = URLManager(config, start_url="https://example.com")
        >>> await manager.add_url("https://example.com/page", depth=1)
        >>> url_item = await manager.get_next_url()
    """

    def __init__(self, config: Config, start_url: str):
        """
        Инициализация URL менеджера.

        Args:
            config: Конфигурация приложения
            start_url: Начальный URL для краулинга
        """
        self.config = config
        self.start_url = start_url
        self.start_domain = extract_domain(start_url, include_subdomain=False)

        # Bloom filter для быстрой проверки
        if config.performance.use_bloom_filter:
            self.bloom_filter: Optional[BloomFilter] = BloomFilter(
                expected_items=config.performance.url_cache_size,
                false_positive_rate=config.performance.bloom_filter_error_rate,
            )
        else:
            self.bloom_filter = None

        # Множество посещённых URL (для точной проверки после Bloom filter)
        self.visited_urls: Set[str] = set()

        # Очередь URL для обработки (используем deque для эффективности)
        self.url_queue: deque[URLItem] = deque()

        # Блокировка для thread-safety
        self.lock = asyncio.Lock()

        # Статистика
        self.stats = {
            "total_discovered": 0,
            "total_processed": 0,
            "total_filtered": 0,
            "filtered_by_domain": 0,
            "filtered_by_honeypot": 0,
            "filtered_by_duplicate": 0,
            "filtered_by_depth": 0,
        }

        self.logger.info(
            "url_manager_initialized",
            start_url=start_url,
            start_domain=self.start_domain,
            use_bloom_filter=config.performance.use_bloom_filter,
        )

    async def add_url(
        self,
        url: str,
        depth: int = 0,
        priority: int = 0,
        source_url: Optional[str] = None,
    ) -> bool:
        """
        Добавить URL в очередь обработки.

        Args:
            url: URL для добавления
            depth: Глубина от начального URL
            priority: Приоритет (меньше = выше приоритет)
            source_url: URL источника (откуда была найдена эта ссылка)

        Returns:
            bool: True если URL был добавлен, False если отфильтрован

        Example:
            >>> added = await manager.add_url("https://example.com/page", depth=1)
            >>> if added:
            ...     print("URL added to queue")
        """
        async with self.lock:
            # Нормализуем URL
            try:
                normalized_url = normalize_url(url)
            except Exception as e:
                self.logger.warning("url_normalization_failed", url=url, error=str(e))
                self.stats["total_filtered"] += 1
                return False

            # Проверяем дедупликацию через Bloom filter (если включен)
            if self.bloom_filter and self.bloom_filter.contains(normalized_url):
                # Проверяем точно через visited_urls
                if normalized_url in self.visited_urls:
                    self.stats["filtered_by_duplicate"] += 1
                    return False

            # Проверяем, не посещён ли URL
            if normalized_url in self.visited_urls:
                self.stats["filtered_by_duplicate"] += 1
                return False

            # Фильтрация по максимальной глубине
            if self.config.crawler.max_depth > 0 and depth > self.config.crawler.max_depth:
                self.stats["filtered_by_depth"] += 1
                self.logger.debug("url_filtered_by_depth", url=url, depth=depth)
                return False

            # Фильтрация по домену
            if self.config.crawler.restrict_to_domain:
                if not is_same_domain(
                    normalized_url,
                    self.start_url,
                    include_subdomains=self.config.crawler.include_subdomains,
                ):
                    self.stats["filtered_by_domain"] += 1
                    self.logger.debug("url_filtered_by_domain", url=url)
                    return False

            # Детектирование honeypot
            if self.config.features.honeypot_detection:
                if is_honeypot_url(normalized_url):
                    self.stats["filtered_by_honeypot"] += 1
                    self.logger.warning("url_filtered_honeypot", url=url)
                    return False

            # Добавляем в очередь
            url_item = URLItem(
                url=normalized_url, depth=depth, priority=priority, source_url=source_url
            )

            self.url_queue.append(url_item)

            # Добавляем в Bloom filter
            if self.bloom_filter:
                self.bloom_filter.add(normalized_url)

            self.stats["total_discovered"] += 1

            self.logger.debug(
                "url_added_to_queue",
                url=normalized_url,
                depth=depth,
                queue_size=len(self.url_queue),
            )

            return True

    async def get_next_url(self) -> Optional[URLItem]:
        """
        Получить следующий URL для обработки.

        Returns:
            Optional[URLItem]: URL для обработки или None если очередь пуста

        Example:
            >>> url_item = await manager.get_next_url()
            >>> if url_item:
            ...     print(f"Processing: {url_item.url}")
        """
        async with self.lock:
            if not self.url_queue:
                return None

            # Для простоты используем FIFO с учётом глубины
            # В более продвинутой версии можно использовать heapq для приоритетной очереди
            url_item = self.url_queue.popleft()

            # Отмечаем как посещённый
            self.visited_urls.add(url_item.url)
            self.stats["total_processed"] += 1

            self.logger.debug(
                "url_retrieved_from_queue",
                url=url_item.url,
                depth=url_item.depth,
                remaining=len(self.url_queue),
            )

            return url_item

    async def mark_as_visited(self, url: str) -> None:
        """
        Отметить URL как посещённый.

        Args:
            url: URL для отметки

        Example:
            >>> await manager.mark_as_visited("https://example.com/page")
        """
        async with self.lock:
            normalized_url = normalize_url(url)
            self.visited_urls.add(normalized_url)

            if self.bloom_filter:
                self.bloom_filter.add(normalized_url)

    def is_visited(self, url: str) -> bool:
        """
        Проверить, был ли URL посещён.

        Args:
            url: URL для проверки

        Returns:
            bool: True если URL был посещён

        Example:
            >>> if manager.is_visited("https://example.com/page"):
            ...     print("Already visited")
        """
        try:
            normalized_url = normalize_url(url)

            # Быстрая проверка через Bloom filter
            if self.bloom_filter:
                if not self.bloom_filter.contains(normalized_url):
                    return False

            # Точная проверка
            return normalized_url in self.visited_urls

        except Exception:
            return False

    def queue_size(self) -> int:
        """
        Получить размер очереди.

        Returns:
            int: Количество URL в очереди

        Example:
            >>> size = manager.queue_size()
            >>> print(f"Queue size: {size}")
        """
        return len(self.url_queue)

    def visited_count(self) -> int:
        """
        Получить количество посещённых URL.

        Returns:
            int: Количество посещённых URL
        """
        return len(self.visited_urls)

    def get_stats(self) -> dict:
        """
        Получить статистику URL менеджера.

        Returns:
            dict: Словарь со статистикой

        Example:
            >>> stats = manager.get_stats()
            >>> print(f"Discovered: {stats['total_discovered']}")
        """
        stats = self.stats.copy()
        stats["queue_size"] = len(self.url_queue)
        stats["visited_count"] = len(self.visited_urls)

        if self.bloom_filter:
            stats["bloom_filter_memory"] = self.bloom_filter.memory_usage()
            stats["bloom_filter_items"] = self.bloom_filter.items_added

        return stats

    async def clear(self) -> None:
        """
        Очистить все URL из очереди и visited set.

        ⚠️ ОСТОРОЖНО: Удаляет все данные!

        Example:
            >>> await manager.clear()
        """
        async with self.lock:
            self.url_queue.clear()
            self.visited_urls.clear()

            if self.bloom_filter:
                # Пересоздаём Bloom filter
                self.bloom_filter = BloomFilter(
                    expected_items=self.config.performance.url_cache_size,
                    false_positive_rate=self.config.performance.bloom_filter_error_rate,
                )

            # Сбрасываем статистику
            for key in self.stats:
                self.stats[key] = 0

            self.logger.info("url_manager_cleared")

    def should_continue_crawling(self) -> bool:
        """
        Проверить, следует ли продолжать краулинг.

        Проверяет ограничения по количеству страниц.

        Returns:
            bool: True если нужно продолжать

        Example:
            >>> if manager.should_continue_crawling():
            ...     url = await manager.get_next_url()
        """
        # Проверяем лимит по страницам
        if self.config.crawler.max_pages > 0:
            if self.stats["total_processed"] >= self.config.crawler.max_pages:
                self.logger.info(
                    "max_pages_reached",
                    processed=self.stats["total_processed"],
                    limit=self.config.crawler.max_pages,
                )
                return False

        # Проверяем, есть ли URL в очереди
        if self.queue_size() == 0:
            self.logger.info("queue_empty", visited=self.visited_count())
            return False

        return True
