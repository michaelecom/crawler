"""
Stats Calculator для расчёта агрегированной статистики краулинга.

Вычисляет:
- Общую статистику (страницы, ссылки, ошибки)
- Распределения (статус коды, content types, глубины)
- Performance метрики (средняя скорость, размеры)
- Временные тренды (краулинг по времени)
- Top страницы (самые большие, медленные, популярные)
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from webcrawler.storage.database import DatabaseManager
from webcrawler.storage.repository import (
    CrawlSessionRepository,
    URLRepository,
    LinkRepository,
    ErrorRepository,
)
from webcrawler.utils.logger import LoggerMixin
from webcrawler.utils.helpers import format_bytes, format_duration


@dataclass
class CrawlStatistics:
    """
    Агрегированная статистика краулинга.

    Attributes:
        session_id: ID сессии
        total_urls: Всего URL обнаружено
        crawled_urls: Обработано URL
        failed_urls: Ошибок
        avg_response_time: Средняя скорость ответа
        median_response_time: Медианная скорость
        total_size_bytes: Общий размер данных
        avg_size_bytes: Средний размер страницы
        crawl_rate: Скорость краулинга (страниц/сек)
        status_distribution: Распределение статус кодов
        content_type_distribution: Распределение типов контента
        depth_distribution: Распределение по глубинам
        error_distribution: Распределение ошибок
        timeline: Временная шкала краулинга
        top_pages: Топ страниц
    """
    session_id: str
    total_urls: int = 0
    crawled_urls: int = 0
    failed_urls: int = 0
    avg_response_time: float = 0.0
    median_response_time: float = 0.0
    total_size_bytes: int = 0
    avg_size_bytes: float = 0.0
    crawl_rate: float = 0.0
    status_distribution: Dict[int, int] = field(default_factory=dict)
    content_type_distribution: Dict[str, int] = field(default_factory=dict)
    depth_distribution: Dict[int, int] = field(default_factory=dict)
    error_distribution: Dict[str, int] = field(default_factory=dict)
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    top_pages: Dict[str, List[Tuple[str, Any]]] = field(default_factory=dict)


class StatsCalculator(LoggerMixin):
    """
    Калькулятор статистики краулинга.

    Вычисляет детальную статистику по сессии краулинга,
    включая распределения, средние значения, топ страницы.

    Example:
        >>> calculator = StatsCalculator(db_manager)
        >>> stats = await calculator.calculate(session_id="abc123")
        >>> print(f"Crawl rate: {stats.crawl_rate:.2f} pages/sec")
        >>> print(f"Avg response time: {stats.avg_response_time:.3f}s")
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Инициализация калькулятора.

        Args:
            db_manager: Менеджер базы данных
        """
        self.db_manager = db_manager

    async def calculate(
        self,
        session_id: str,
        include_timeline: bool = True,
        include_top_pages: bool = True,
        top_n: int = 20
    ) -> CrawlStatistics:
        """
        Рассчитать статистику для сессии.

        Args:
            session_id: ID сессии для анализа
            include_timeline: Включить временную шкалу
            include_top_pages: Включить топ страницы
            top_n: Количество топ страниц

        Returns:
            Объект со статистикой
        """
        self.logger.info(f"Calculating statistics for session {session_id}")

        # Получить данные
        async with self.db_manager.session() as db_session:
            session_repo = CrawlSessionRepository(db_session)
            url_repo = URLRepository(db_session)
            link_repo = LinkRepository(db_session)
            error_repo = ErrorRepository(db_session)

            session = await session_repo.get_by_session_id(session_id)
            if not session:
                raise ValueError(f"Session {session_id} not found")

            urls = await url_repo.get_all_by_session(session_id)
            links = await link_repo.get_all_by_session(session_id)
            errors = await error_repo.get_all_by_session(session_id)

        # Создать объект статистики
        stats = CrawlStatistics(session_id=session_id)

        # Базовая статистика
        stats.total_urls = len(urls)
        stats.crawled_urls = sum(1 for url in urls if url.status == "completed")
        stats.failed_urls = len(errors)

        # Рассчитать метрики
        self._calculate_response_times(urls, stats)
        self._calculate_sizes(urls, stats)
        self._calculate_crawl_rate(session, urls, stats)

        # Распределения
        stats.status_distribution = self._calculate_status_distribution(urls)
        stats.content_type_distribution = self._calculate_content_type_distribution(urls)
        stats.depth_distribution = self._calculate_depth_distribution(urls)
        stats.error_distribution = self._calculate_error_distribution(errors)

        # Временная шкала (опционально)
        if include_timeline:
            stats.timeline = self._calculate_timeline(urls)

        # Топ страницы (опционально)
        if include_top_pages:
            stats.top_pages = self._calculate_top_pages(urls, links, top_n)

        self.logger.info(
            f"Statistics calculated: {stats.crawled_urls} pages crawled, "
            f"{stats.crawl_rate:.2f} pages/sec"
        )

        return stats

    def _calculate_response_times(
        self,
        urls: List[Any],
        stats: CrawlStatistics
    ) -> None:
        """
        Рассчитать метрики времени ответа.

        Args:
            urls: Список URL
            stats: Объект статистики (модифицируется)
        """
        response_times = [
            url.response_time for url in urls
            if url.response_time is not None
        ]

        if response_times:
            stats.avg_response_time = sum(response_times) / len(response_times)

            # Медиана
            sorted_times = sorted(response_times)
            mid = len(sorted_times) // 2
            if len(sorted_times) % 2 == 0:
                stats.median_response_time = (
                    sorted_times[mid - 1] + sorted_times[mid]
                ) / 2
            else:
                stats.median_response_time = sorted_times[mid]

    def _calculate_sizes(
        self,
        urls: List[Any],
        stats: CrawlStatistics
    ) -> None:
        """
        Рассчитать метрики размеров страниц.

        Args:
            urls: Список URL
            stats: Объект статистики (модифицируется)
        """
        sizes = [
            url.size_bytes for url in urls
            if url.size_bytes is not None
        ]

        if sizes:
            stats.total_size_bytes = sum(sizes)
            stats.avg_size_bytes = stats.total_size_bytes / len(sizes)

    def _calculate_crawl_rate(
        self,
        session: Any,
        urls: List[Any],
        stats: CrawlStatistics
    ) -> None:
        """
        Рассчитать скорость краулинга.

        Args:
            session: Объект сессии
            urls: Список URL
            stats: Объект статистики (модифицируется)
        """
        if session.duration_seconds and session.duration_seconds > 0:
            stats.crawl_rate = stats.crawled_urls / session.duration_seconds

    def _calculate_status_distribution(
        self,
        urls: List[Any]
    ) -> Dict[int, int]:
        """
        Рассчитать распределение статус кодов.

        Args:
            urls: Список URL

        Returns:
            Словарь {статус код: количество}
        """
        status_codes = [
            url.status_code for url in urls
            if url.status_code is not None
        ]

        return dict(Counter(status_codes))

    def _calculate_content_type_distribution(
        self,
        urls: List[Any]
    ) -> Dict[str, int]:
        """
        Рассчитать распределение типов контента.

        Args:
            urls: Список URL

        Returns:
            Словарь {content type: количество}
        """
        content_types = []

        for url in urls:
            if url.content_type:
                # Упростить content type (взять основную часть)
                ct = url.content_type.split(";")[0].strip()
                content_types.append(ct)

        return dict(Counter(content_types))

    def _calculate_depth_distribution(
        self,
        urls: List[Any]
    ) -> Dict[int, int]:
        """
        Рассчитать распределение по глубине.

        Args:
            urls: Список URL

        Returns:
            Словарь {глубина: количество}
        """
        depths = [url.depth for url in urls]
        return dict(Counter(depths))

    def _calculate_error_distribution(
        self,
        errors: List[Any]
    ) -> Dict[str, int]:
        """
        Рассчитать распределение ошибок.

        Args:
            errors: Список ошибок

        Returns:
            Словарь {тип ошибки: количество}
        """
        error_types = [error.error_type for error in errors]
        return dict(Counter(error_types))

    def _calculate_timeline(
        self,
        urls: List[Any],
        interval_minutes: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Рассчитать временную шкалу краулинга.

        Группирует URL по временным интервалам.

        Args:
            urls: Список URL
            interval_minutes: Интервал в минутах

        Returns:
            Список точек на временной шкале
        """
        # Собрать timestamps
        timestamps = [
            url.crawled_at for url in urls
            if url.crawled_at is not None
        ]

        if not timestamps:
            return []

        # Найти min/max время
        min_time = min(timestamps)
        max_time = max(timestamps)

        # Разбить на интервалы
        timeline = []
        current_time = min_time
        interval = timedelta(minutes=interval_minutes)

        while current_time <= max_time:
            next_time = current_time + interval

            # Подсчитать URL в этом интервале
            count = sum(
                1 for ts in timestamps
                if current_time <= ts < next_time
            )

            timeline.append({
                "timestamp": current_time.isoformat(),
                "count": count,
                "interval_start": current_time.isoformat(),
                "interval_end": next_time.isoformat(),
            })

            current_time = next_time

        return timeline

    def _calculate_top_pages(
        self,
        urls: List[Any],
        links: List[Any],
        top_n: int
    ) -> Dict[str, List[Tuple[str, Any]]]:
        """
        Рассчитать топ страницы по различным метрикам.

        Args:
            urls: Список URL
            links: Список ссылок
            top_n: Количество топ страниц

        Returns:
            Словарь с топ страницами по разным метрикам
        """
        top_pages = {}

        # Топ по размеру
        urls_with_size = [
            (url.url, url.size_bytes)
            for url in urls
            if url.size_bytes is not None
        ]
        top_pages["largest"] = sorted(
            urls_with_size,
            key=lambda x: x[1],
            reverse=True
        )[:top_n]

        # Топ по времени ответа (самые медленные)
        urls_with_time = [
            (url.url, url.response_time)
            for url in urls
            if url.response_time is not None
        ]
        top_pages["slowest"] = sorted(
            urls_with_time,
            key=lambda x: x[1],
            reverse=True
        )[:top_n]

        # Топ по количеству входящих ссылок
        incoming_count = Counter()
        for link in links:
            if link.link_type == "internal":
                incoming_count[link.target_url] += 1

        top_pages["most_linked"] = incoming_count.most_common(top_n)

        # Топ по количеству исходящих ссылок
        outgoing_count = Counter()
        for link in links:
            if link.link_type == "internal":
                outgoing_count[link.source_url] += 1

        top_pages["most_links_out"] = outgoing_count.most_common(top_n)

        return top_pages

    def get_summary(self, stats: CrawlStatistics) -> str:
        """
        Получить текстовую сводку статистики.

        Args:
            stats: Объект статистики

        Returns:
            Форматированная строка со сводкой
        """
        lines = [
            f"Session: {stats.session_id}",
            f"",
            f"Pages:",
            f"  Total discovered: {stats.total_urls}",
            f"  Successfully crawled: {stats.crawled_urls}",
            f"  Failed: {stats.failed_urls}",
            f"",
            f"Performance:",
            f"  Crawl rate: {stats.crawl_rate:.2f} pages/sec",
            f"  Avg response time: {stats.avg_response_time:.3f}s",
            f"  Median response time: {stats.median_response_time:.3f}s",
            f"",
            f"Data:",
            f"  Total size: {format_bytes(stats.total_size_bytes)}",
            f"  Avg page size: {format_bytes(int(stats.avg_size_bytes))}",
            f"",
            f"Status codes:",
        ]

        # Добавить статус коды
        for code in sorted(stats.status_distribution.keys()):
            count = stats.status_distribution[code]
            lines.append(f"  {code}: {count}")

        # Добавить топ content types
        lines.append("")
        lines.append("Top content types:")
        sorted_cts = sorted(
            stats.content_type_distribution.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        for ct, count in sorted_cts:
            lines.append(f"  {ct}: {count}")

        return "\n".join(lines)
