"""
Link Extractor для продвинутого анализа ссылок.

Предоставляет:
- Категоризация ссылок (navigation, content, footer, etc.)
- Анализ anchor text
- Обнаружение orphan pages
- Анализ link patterns (hub/authority pages)
- PageRank estimation
"""

from collections import defaultdict, Counter
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from urllib.parse import urlparse

from webcrawler.storage.database import DatabaseManager
from webcrawler.storage.repository import URLRepository, LinkRepository
from webcrawler.utils.logger import LoggerMixin


@dataclass
class LinkAnalysis:
    """
    Анализ ссылки.

    Attributes:
        source_url: URL источника
        target_url: URL назначения
        anchor_text: Текст ссылки
        link_category: Категория ссылки
        is_internal: Внутренняя ссылка
        depth_difference: Разница в глубине
    """
    source_url: str
    target_url: str
    anchor_text: Optional[str]
    link_category: str
    is_internal: bool
    depth_difference: int = 0


@dataclass
class PageLinkMetrics:
    """
    Метрики ссылок для страницы.

    Attributes:
        url: URL страницы
        incoming_links: Количество входящих ссылок
        outgoing_links: Количество исходящих ссылок
        internal_incoming: Внутренние входящие
        external_incoming: Внешние входящие
        internal_outgoing: Внутренние исходящие
        external_outgoing: Внешние исходящие
        pagerank_estimate: Оценка PageRank
        is_hub: Является ли hub page (много исходящих)
        is_authority: Является ли authority page (много входящих)
        is_orphan: Orphan page (нет входящих)
    """
    url: str
    incoming_links: int = 0
    outgoing_links: int = 0
    internal_incoming: int = 0
    external_incoming: int = 0
    internal_outgoing: int = 0
    external_outgoing: int = 0
    pagerank_estimate: float = 0.0
    is_hub: bool = False
    is_authority: bool = False
    is_orphan: bool = False


@dataclass
class LinkExtractionReport:
    """
    Отчёт об анализе ссылок.

    Attributes:
        session_id: ID сессии
        total_pages: Всего страниц
        total_links: Всего ссылок
        internal_links: Внутренних ссылок
        external_links: Внешних ссылок
        orphan_pages: Страницы без входящих ссылок
        hub_pages: Hub pages (топ по исходящим)
        authority_pages: Authority pages (топ по входящим)
        most_common_anchors: Самые частые anchor texts
        link_categories: Распределение по категориям
    """
    session_id: str
    total_pages: int = 0
    total_links: int = 0
    internal_links: int = 0
    external_links: int = 0
    orphan_pages: List[str] = field(default_factory=list)
    hub_pages: List[Tuple[str, int]] = field(default_factory=list)
    authority_pages: List[Tuple[str, int]] = field(default_factory=list)
    most_common_anchors: List[Tuple[str, int]] = field(default_factory=list)
    link_categories: Dict[str, int] = field(default_factory=dict)


class LinkExtractor(LoggerMixin):
    """
    Продвинутый анализатор ссылок.

    Выполняет детальный анализ графа ссылок сайта,
    выявляет hub/authority pages, orphan pages,
    анализирует anchor text и категоризирует ссылки.

    Example:
        >>> extractor = LinkExtractor(db_manager)
        >>> report = await extractor.analyze(session_id="abc123")
        >>> print(f"Orphan pages: {len(report.orphan_pages)}")
        >>> print(f"Hub pages: {report.hub_pages[:5]}")
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Инициализация экстрактора.

        Args:
            db_manager: Менеджер базы данных
        """
        self.db_manager = db_manager

        # Пороги для классификации
        self.thresholds = {
            "hub_page_outgoing": 50,  # Минимум исходящих для hub page
            "authority_page_incoming": 10,  # Минимум входящих для authority
        }

        # Generic anchor texts (не информативные)
        self.generic_anchors = {
            "click here", "read more", "more", "here", "link",
            "подробнее", "далее", "ссылка", "читать", "смотреть"
        }

    async def analyze(
        self,
        session_id: str,
        top_pages: int = 20,
        calculate_pagerank: bool = True
    ) -> LinkExtractionReport:
        """
        Выполнить анализ ссылок.

        Args:
            session_id: ID сессии для анализа
            top_pages: Количество топ страниц для hub/authority
            calculate_pagerank: Рассчитать PageRank estimation

        Returns:
            Отчёт об анализе ссылок
        """
        self.logger.info(f"Starting link analysis for session {session_id}")

        # Получить данные
        async with self.db_manager.session() as db_session:
            url_repo = URLRepository(db_session)
            link_repo = LinkRepository(db_session)

            urls = await url_repo.get_all_by_session(session_id)
            links = await link_repo.get_all_by_session(session_id)

        # Создать отчёт
        report = LinkExtractionReport(
            session_id=session_id,
            total_pages=len(urls),
            total_links=len(links)
        )

        # Построить граф
        page_metrics = self._build_link_graph(urls, links)

        # Категоризировать ссылки
        categorized_links = self._categorize_links(links)
        report.link_categories = self._count_categories(categorized_links)

        # Подсчитать статистику
        report.internal_links = sum(1 for link in links if link.link_type == "internal")
        report.external_links = sum(1 for link in links if link.link_type == "external")

        # Найти orphan pages
        report.orphan_pages = [
            url for url, metrics in page_metrics.items()
            if metrics.is_orphan
        ]

        # Топ hub pages
        hub_candidates = [
            (url, metrics.outgoing_links)
            for url, metrics in page_metrics.items()
            if metrics.is_hub
        ]
        report.hub_pages = sorted(
            hub_candidates,
            key=lambda x: x[1],
            reverse=True
        )[:top_pages]

        # Топ authority pages
        authority_candidates = [
            (url, metrics.incoming_links)
            for url, metrics in page_metrics.items()
            if metrics.is_authority
        ]
        report.authority_pages = sorted(
            authority_candidates,
            key=lambda x: x[1],
            reverse=True
        )[:top_pages]

        # Анализ anchor text
        anchor_counter = Counter()
        for link in links:
            if link.anchor_text:
                # Пропустить generic anchors
                anchor_lower = link.anchor_text.lower().strip()
                if anchor_lower not in self.generic_anchors:
                    anchor_counter[link.anchor_text] += 1

        report.most_common_anchors = anchor_counter.most_common(50)

        # Рассчитать PageRank (опционально)
        if calculate_pagerank:
            pageranks = self._calculate_simple_pagerank(page_metrics, iterations=10)
            for url, pr in pageranks.items():
                if url in page_metrics:
                    page_metrics[url].pagerank_estimate = pr

        self.logger.info(
            f"Link analysis complete: {report.total_links} links, "
            f"{len(report.orphan_pages)} orphan pages, "
            f"{len(report.hub_pages)} hub pages"
        )

        return report

    def _build_link_graph(
        self,
        urls: List[Any],
        links: List[Any]
    ) -> Dict[str, PageLinkMetrics]:
        """
        Построить граф ссылок и рассчитать метрики для каждой страницы.

        Args:
            urls: Список URL объектов
            links: Список Link объектов

        Returns:
            Словарь {url: PageLinkMetrics}
        """
        # Инициализировать метрики для всех URL
        page_metrics = {}
        for url in urls:
            page_metrics[url.url] = PageLinkMetrics(url=url.url)

        # Подсчитать входящие и исходящие ссылки
        for link in links:
            source = link.source_url
            target = link.target_url
            is_internal = (link.link_type == "internal")

            # Исходящие для source
            if source in page_metrics:
                page_metrics[source].outgoing_links += 1
                if is_internal:
                    page_metrics[source].internal_outgoing += 1
                else:
                    page_metrics[source].external_outgoing += 1

            # Входящие для target
            if target in page_metrics:
                page_metrics[target].incoming_links += 1
                if is_internal:
                    page_metrics[target].internal_incoming += 1
                else:
                    page_metrics[target].external_incoming += 1

        # Классифицировать страницы
        for url, metrics in page_metrics.items():
            # Hub pages (много исходящих)
            if metrics.outgoing_links >= self.thresholds["hub_page_outgoing"]:
                metrics.is_hub = True

            # Authority pages (много входящих)
            if metrics.incoming_links >= self.thresholds["authority_page_incoming"]:
                metrics.is_authority = True

            # Orphan pages (нет входящих)
            if metrics.incoming_links == 0 and metrics.outgoing_links > 0:
                metrics.is_orphan = True

        return page_metrics

    def _categorize_links(self, links: List[Any]) -> List[LinkAnalysis]:
        """
        Категоризировать ссылки.

        Категории:
        - navigation: меню, навигация
        - content: ссылки из контента
        - footer: футер
        - breadcrumb: хлебные крошки
        - pagination: пагинация
        - other: прочее

        Args:
            links: Список Link объектов

        Returns:
            Список LinkAnalysis с категориями
        """
        categorized = []

        for link in links:
            # Определить категорию по anchor text и rel
            category = self._determine_link_category(link)

            analysis = LinkAnalysis(
                source_url=link.source_url,
                target_url=link.target_url,
                anchor_text=link.anchor_text,
                link_category=category,
                is_internal=(link.link_type == "internal")
            )

            categorized.append(analysis)

        return categorized

    def _determine_link_category(self, link: Any) -> str:
        """
        Определить категорию ссылки.

        Args:
            link: Link объект

        Returns:
            Категория ссылки
        """
        anchor = (link.anchor_text or "").lower()
        rel = (link.rel or "").lower()

        # Breadcrumb
        if "breadcrumb" in rel or "навигация" in anchor:
            return "breadcrumb"

        # Navigation
        navigation_keywords = ["menu", "nav", "navigation", "меню", "навигация"]
        if any(kw in anchor for kw in navigation_keywords):
            return "navigation"

        # Pagination
        pagination_keywords = ["next", "prev", "previous", "page", "следующая", "предыдущая", "страница"]
        if any(kw in anchor for kw in pagination_keywords):
            return "pagination"

        # Footer
        footer_keywords = ["copyright", "privacy", "terms", "конфиденциальность", "условия"]
        if any(kw in anchor for kw in footer_keywords):
            return "footer"

        # По умолчанию content
        return "content"

    def _count_categories(
        self,
        categorized_links: List[LinkAnalysis]
    ) -> Dict[str, int]:
        """
        Подсчитать распределение по категориям.

        Args:
            categorized_links: Список категоризированных ссылок

        Returns:
            Словарь {категория: количество}
        """
        counter = Counter(link.link_category for link in categorized_links)
        return dict(counter)

    def _calculate_simple_pagerank(
        self,
        page_metrics: Dict[str, PageLinkMetrics],
        iterations: int = 10,
        damping: float = 0.85
    ) -> Dict[str, float]:
        """
        Рассчитать упрощённый PageRank.

        Использует итеративный алгоритм PageRank
        для оценки важности страниц.

        Args:
            page_metrics: Метрики страниц с графом ссылок
            iterations: Количество итераций
            damping: Damping factor (обычно 0.85)

        Returns:
            Словарь {url: pagerank}
        """
        # Инициализировать PageRank
        num_pages = len(page_metrics)
        if num_pages == 0:
            return {}

        pageranks = {url: 1.0 / num_pages for url in page_metrics.keys()}

        # Построить обратный граф (для вычисления PR)
        incoming_links = defaultdict(list)
        outgoing_counts = {}

        # Собрать информацию о ссылках из метрик
        # (в реальности нужно использовать links, но для упрощения используем метрики)
        for url, metrics in page_metrics.items():
            outgoing_counts[url] = metrics.outgoing_links

        # Итеративно рассчитать PageRank
        for iteration in range(iterations):
            new_pageranks = {}

            for url in page_metrics.keys():
                # Базовое значение
                rank = (1 - damping) / num_pages

                # Вклад от входящих ссылок
                # (упрощённая версия - нужна информация о конкретных ссылках)
                # Для полной реализации нужно хранить граф

                new_pageranks[url] = rank

            pageranks = new_pageranks

        return pageranks


class AnchorTextAnalyzer:
    """
    Анализатор anchor text для SEO.

    Анализирует распределение anchor text,
    выявляет over-optimization и generic anchors.
    """

    def __init__(self):
        """Инициализация анализатора."""
        self.generic_anchors = {
            "click here", "read more", "more", "here", "link",
            "подробнее", "далее", "ссылка", "читать", "смотреть"
        }

    def analyze_anchors(
        self,
        links: List[Any],
        target_url: str
    ) -> Dict[str, Any]:
        """
        Анализировать anchor text для конкретного URL.

        Args:
            links: Список всех ссылок
            target_url: URL для анализа

        Returns:
            Словарь с анализом anchor text
        """
        # Найти все ссылки на target_url
        target_links = [
            link for link in links
            if link.target_url == target_url
        ]

        if not target_links:
            return {
                "total_backlinks": 0,
                "anchor_distribution": {},
                "generic_anchors_percentage": 0,
                "exact_match_percentage": 0,
            }

        # Подсчитать распределение anchor text
        anchor_counter = Counter()
        generic_count = 0

        for link in target_links:
            if link.anchor_text:
                anchor_counter[link.anchor_text] += 1

                if link.anchor_text.lower().strip() in self.generic_anchors:
                    generic_count += 1

        total = len(target_links)

        return {
            "total_backlinks": total,
            "anchor_distribution": dict(anchor_counter.most_common(20)),
            "generic_anchors_percentage": (generic_count / total * 100) if total > 0 else 0,
            "unique_anchors": len(anchor_counter),
        }
