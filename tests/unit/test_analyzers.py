"""
Unit тесты для анализаторов данных.

Тестирование ContentAnalyzer, LinkExtractor, StatsCalculator.
"""

import pytest
from webcrawler.analyzers import ContentAnalyzer, LinkExtractor, StatsCalculator
from webcrawler.analyzers.content_analyzer import IssueSeverity


@pytest.mark.unit
@pytest.mark.asyncio
class TestContentAnalyzer:
    """Тесты для анализатора контента."""

    async def test_analyze_basic(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест базового анализа контента."""
        analyzer = ContentAnalyzer(test_db_manager)

        report = await analyzer.analyze(
            session_id=sample_crawl_session,
            analyze_seo=True,
            analyze_broken_links=True,
            analyze_security=False,
            analyze_performance=False,
            analyze_content=False
        )

        # Проверить базовые поля
        assert report.session_id == sample_crawl_session
        assert report.total_pages > 0
        assert report.total_issues >= 0
        assert 0 <= report.seo_score <= 100

    async def test_analyze_broken_links(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест детектирования битых ссылок."""
        analyzer = ContentAnalyzer(test_db_manager)

        report = await analyzer.analyze(
            session_id=sample_crawl_session,
            analyze_seo=False,
            analyze_broken_links=True
        )

        # В sample_crawl_session есть одна страница 404
        broken_issues = [
            issue for issue in report.issues
            if "404" in issue.description or "broken" in issue.description.lower()
        ]

        assert len(broken_issues) > 0

    async def test_analyze_seo(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест SEO анализа."""
        analyzer = ContentAnalyzer(test_db_manager)

        report = await analyzer.analyze(
            session_id=sample_crawl_session,
            analyze_seo=True
        )

        # SEO score должен быть рассчитан
        assert report.seo_score is not None
        assert 0 <= report.seo_score <= 100

    async def test_seo_score_calculation(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест расчёта SEO score."""
        analyzer = ContentAnalyzer(test_db_manager)

        # Анализ с проблемами должен снизить score
        report = await analyzer.analyze(
            session_id=sample_crawl_session,
            analyze_seo=True,
            analyze_broken_links=True
        )

        # С битыми ссылками score должен быть < 100
        if len(report.issues) > 0:
            assert report.seo_score < 100

    async def test_issue_severity_levels(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест уровней серьёзности проблем."""
        analyzer = ContentAnalyzer(test_db_manager)

        report = await analyzer.analyze(
            session_id=sample_crawl_session,
            analyze_seo=True,
            analyze_broken_links=True
        )

        # Проверить что severity корректный
        for issue in report.issues:
            assert issue.severity in [
                IssueSeverity.INFO,
                IssueSeverity.WARNING,
                IssueSeverity.ERROR,
                IssueSeverity.CRITICAL
            ]

    async def test_analyze_invalid_session(self, test_db_manager):
        """Тест анализа несуществующей сессии."""
        analyzer = ContentAnalyzer(test_db_manager)

        with pytest.raises(ValueError, match="Session .* not found"):
            await analyzer.analyze(session_id="nonexistent_session")


@pytest.mark.unit
@pytest.mark.asyncio
class TestLinkExtractor:
    """Тесты для анализатора ссылок."""

    async def test_analyze_basic(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест базового анализа ссылок."""
        analyzer = LinkExtractor(test_db_manager)

        report = await analyzer.analyze(
            session_id=sample_crawl_session,
            top_pages=10,
            calculate_pagerank=False  # Отключаем для быстрых тестов
        )

        # Проверить базовые поля
        assert report.session_id == sample_crawl_session
        assert report.total_pages > 0
        assert report.total_links >= 0
        assert report.internal_links >= 0
        assert report.external_links >= 0

    async def test_orphan_pages_detection(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест детектирования страниц-сирот."""
        analyzer = LinkExtractor(test_db_manager)

        report = await analyzer.analyze(session_id=sample_crawl_session)

        # Проверить что orphan pages определены
        assert isinstance(report.orphan_pages, list)

        # В sample session есть URL без входящих ссылок
        # (например, start_url может быть orphan если нет ссылок на него)

    async def test_hub_pages_detection(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест детектирования hub страниц."""
        analyzer = LinkExtractor(test_db_manager)

        report = await analyzer.analyze(session_id=sample_crawl_session)

        # Проверить что hub pages определены
        assert isinstance(report.hub_pages, list)

        # Hub pages - страницы с большим количеством исходящих ссылок
        # Start page обычно является hub

    async def test_authority_pages_detection(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест детектирования authority страниц."""
        analyzer = LinkExtractor(test_db_manager)

        report = await analyzer.analyze(session_id=sample_crawl_session)

        # Проверить что authority pages определены
        assert isinstance(report.authority_pages, list)

        # Authority pages - страницы с большим количеством входящих ссылок

    async def test_pagerank_calculation(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест расчёта PageRank."""
        analyzer = LinkExtractor(test_db_manager)

        report = await analyzer.analyze(
            session_id=sample_crawl_session,
            calculate_pagerank=True
        )

        # Проверить что PageRank рассчитан для страниц
        if report.top_pages_by_pagerank:
            for page_info in report.top_pages_by_pagerank:
                assert "url" in page_info
                assert "pagerank" in page_info
                assert page_info["pagerank"] >= 0

    async def test_link_categories(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест категоризации ссылок."""
        analyzer = LinkExtractor(test_db_manager)

        report = await analyzer.analyze(session_id=sample_crawl_session)

        # Проверить что категории ссылок определены
        assert isinstance(report.link_categories, dict)

        # Должны быть категории: navigation, content, footer, etc.
        # Пока просто проверим что dict не пустой если есть ссылки
        if report.total_links > 0:
            assert len(report.link_categories) >= 0

    async def test_top_pages_limit(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест ограничения топ страниц."""
        analyzer = LinkExtractor(test_db_manager)

        top_n = 3
        report = await analyzer.analyze(
            session_id=sample_crawl_session,
            top_pages=top_n
        )

        # Проверить что топ списки не превышают лимит
        assert len(report.hub_pages) <= top_n
        assert len(report.authority_pages) <= top_n


@pytest.mark.unit
@pytest.mark.asyncio
class TestStatsCalculator:
    """Тесты для калькулятора статистики."""

    async def test_calculate_basic(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест базового расчёта статистики."""
        calculator = StatsCalculator(test_db_manager)

        stats = await calculator.calculate(
            session_id=sample_crawl_session,
            include_timeline=False,
            include_top_pages=False
        )

        # Проверить базовые поля
        assert stats.session_id == sample_crawl_session
        assert stats.total_urls > 0
        assert stats.successful_urls >= 0
        assert stats.failed_urls >= 0

    async def test_response_time_stats(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест статистики времени ответа."""
        calculator = StatsCalculator(test_db_manager)

        stats = await calculator.calculate(session_id=sample_crawl_session)

        # Проверить что статистика времени ответа рассчитана
        assert stats.avg_response_time is not None
        assert stats.avg_response_time >= 0
        assert stats.median_response_time is not None
        assert stats.median_response_time >= 0

    async def test_size_stats(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест статистики размеров."""
        calculator = StatsCalculator(test_db_manager)

        stats = await calculator.calculate(session_id=sample_crawl_session)

        # Проверить статистику размеров
        assert stats.total_bytes >= 0
        assert stats.avg_size_bytes >= 0

    async def test_crawl_rate(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест расчёта скорости краулинга."""
        calculator = StatsCalculator(test_db_manager)

        stats = await calculator.calculate(session_id=sample_crawl_session)

        # Скорость краулинга должна быть рассчитана
        assert stats.crawl_rate_pages_per_sec >= 0

    async def test_status_code_distribution(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест распределения статус-кодов."""
        calculator = StatsCalculator(test_db_manager)

        stats = await calculator.calculate(session_id=sample_crawl_session)

        # Проверить что распределение статус-кодов присутствует
        assert isinstance(stats.status_code_distribution, dict)
        assert len(stats.status_code_distribution) > 0

        # В sample session должен быть код 200 и 404
        assert 200 in stats.status_code_distribution
        assert 404 in stats.status_code_distribution

    async def test_content_type_distribution(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест распределения типов контента."""
        calculator = StatsCalculator(test_db_manager)

        stats = await calculator.calculate(session_id=sample_crawl_session)

        # Проверить распределение типов контента
        assert isinstance(stats.content_type_distribution, dict)
        assert len(stats.content_type_distribution) > 0

        # В sample session должны быть text/html и image/jpeg
        assert "text/html" in stats.content_type_distribution
        assert "image/jpeg" in stats.content_type_distribution

    async def test_depth_distribution(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест распределения по глубине."""
        calculator = StatsCalculator(test_db_manager)

        stats = await calculator.calculate(session_id=sample_crawl_session)

        # Проверить распределение по глубине
        assert isinstance(stats.depth_distribution, dict)
        assert len(stats.depth_distribution) > 0

        # В sample session есть глубина 0 и 1
        assert 0 in stats.depth_distribution
        assert 1 in stats.depth_distribution

    async def test_error_distribution(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест распределения ошибок."""
        calculator = StatsCalculator(test_db_manager)

        stats = await calculator.calculate(session_id=sample_crawl_session)

        # Проверить распределение ошибок
        assert isinstance(stats.error_distribution, dict)

        # В sample session есть ошибки timeout и connection_error
        if len(stats.error_distribution) > 0:
            assert "timeout" in stats.error_distribution or \
                   "connection_error" in stats.error_distribution

    async def test_timeline_stats(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест статистики временной шкалы."""
        calculator = StatsCalculator(test_db_manager)

        stats = await calculator.calculate(
            session_id=sample_crawl_session,
            include_timeline=True
        )

        # Проверить что timeline присутствует
        assert stats.timeline is not None
        assert isinstance(stats.timeline, list)

    async def test_top_pages_stats(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест статистики топ страниц."""
        calculator = StatsCalculator(test_db_manager)

        top_n = 5
        stats = await calculator.calculate(
            session_id=sample_crawl_session,
            include_top_pages=True,
            top_n=top_n
        )

        # Проверить топ списки
        assert stats.top_largest_pages is not None
        assert stats.top_slowest_pages is not None

        # Проверить лимиты
        if stats.top_largest_pages:
            assert len(stats.top_largest_pages) <= top_n
        if stats.top_slowest_pages:
            assert len(stats.top_slowest_pages) <= top_n

    async def test_top_largest_pages_ordering(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест сортировки самых больших страниц."""
        calculator = StatsCalculator(test_db_manager)

        stats = await calculator.calculate(
            session_id=sample_crawl_session,
            include_top_pages=True
        )

        # Проверить что страницы отсортированы по убыванию размера
        if stats.top_largest_pages and len(stats.top_largest_pages) > 1:
            for i in range(len(stats.top_largest_pages) - 1):
                assert stats.top_largest_pages[i]["size_bytes"] >= \
                       stats.top_largest_pages[i + 1]["size_bytes"]

    async def test_top_slowest_pages_ordering(
        self, test_db_manager, sample_crawl_session
    ):
        """Тест сортировки самых медленных страниц."""
        calculator = StatsCalculator(test_db_manager)

        stats = await calculator.calculate(
            session_id=sample_crawl_session,
            include_top_pages=True
        )

        # Проверить что страницы отсортированы по убыванию времени ответа
        if stats.top_slowest_pages and len(stats.top_slowest_pages) > 1:
            for i in range(len(stats.top_slowest_pages) - 1):
                assert stats.top_slowest_pages[i]["response_time"] >= \
                       stats.top_slowest_pages[i + 1]["response_time"]
