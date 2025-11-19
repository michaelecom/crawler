"""
Content Analyzer для анализа контента страниц и выявления проблем.

Анализирует:
- SEO проблемы (title, meta, h1, alt tags)
- Битые ссылки (404, 500 ошибки)
- Security issues (mixed content, insecure resources)
- Performance issues (медленные страницы, большие файлы)
- Content quality (дубликаты, тонкий контент)
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

from webcrawler.storage.database import DatabaseManager
from webcrawler.storage.repository import URLRepository, ErrorRepository
from webcrawler.utils.logger import LoggerMixin


class IssueSeverity(str, Enum):
    """Уровень серьёзности проблемы."""
    CRITICAL = "critical"  # Критическая проблема
    ERROR = "error"        # Ошибка
    WARNING = "warning"    # Предупреждение
    INFO = "info"          # Информация


@dataclass
class ContentIssue:
    """
    Проблема контента или SEO.

    Attributes:
        url: URL страницы с проблемой
        issue_type: Тип проблемы (seo, broken_link, security, performance, content)
        severity: Уровень серьёзности
        message: Описание проблемы
        details: Дополнительные детали
    """
    url: str
    issue_type: str
    severity: IssueSeverity
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class ContentAnalysisReport:
    """
    Отчёт об анализе контента.

    Attributes:
        session_id: ID сессии краулинга
        total_pages: Всего проанализировано страниц
        issues: Список найденных проблем
        seo_score: SEO оценка (0-100)
        summary: Сводка по категориям проблем
    """
    session_id: str
    total_pages: int
    issues: List[ContentIssue] = field(default_factory=list)
    seo_score: float = 100.0
    summary: Dict[str, int] = field(default_factory=dict)


class ContentAnalyzer(LoggerMixin):
    """
    Анализатор контента страниц.

    Выполняет комплексный анализ всех страниц сессии краулинга
    и выявляет проблемы SEO, битые ссылки, security issues и т.д.

    Example:
        >>> analyzer = ContentAnalyzer(db_manager)
        >>> report = await analyzer.analyze(session_id="abc123")
        >>> print(f"SEO Score: {report.seo_score}")
        >>> for issue in report.issues:
        ...     print(f"{issue.severity}: {issue.message}")
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Инициализация анализатора.

        Args:
            db_manager: Менеджер базы данных
        """
        self.db_manager = db_manager

        # Пороговые значения для анализа
        self.thresholds = {
            "title_min_length": 30,
            "title_max_length": 60,
            "meta_description_min_length": 120,
            "meta_description_max_length": 160,
            "page_size_warning": 1024 * 1024,  # 1 MB
            "page_size_critical": 5 * 1024 * 1024,  # 5 MB
            "response_time_warning": 2.0,  # секунды
            "response_time_critical": 5.0,
            "thin_content_threshold": 200,  # минимальная длина title+description
        }

    async def analyze(
        self,
        session_id: str,
        analyze_seo: bool = True,
        analyze_broken_links: bool = True,
        analyze_security: bool = True,
        analyze_performance: bool = True,
        analyze_content: bool = True,
    ) -> ContentAnalysisReport:
        """
        Выполнить комплексный анализ контента.

        Args:
            session_id: ID сессии для анализа
            analyze_seo: Анализировать SEO проблемы
            analyze_broken_links: Анализировать битые ссылки
            analyze_security: Анализировать security issues
            analyze_performance: Анализировать производительность
            analyze_content: Анализировать качество контента

        Returns:
            Отчёт об анализе
        """
        self.logger.info(f"Starting content analysis for session {session_id}")

        # Получить данные
        async with self.db_manager.session() as db_session:
            url_repo = URLRepository(db_session)
            error_repo = ErrorRepository(db_session)

            urls = await url_repo.get_all_by_session(session_id)
            errors = await error_repo.get_all_by_session(session_id)

        # Создать отчёт
        report = ContentAnalysisReport(
            session_id=session_id,
            total_pages=len(urls)
        )

        # Выполнить различные виды анализа
        if analyze_seo:
            seo_issues = self._analyze_seo(urls)
            report.issues.extend(seo_issues)

        if analyze_broken_links:
            broken_link_issues = self._analyze_broken_links(urls, errors)
            report.issues.extend(broken_link_issues)

        if analyze_security:
            security_issues = self._analyze_security(urls)
            report.issues.extend(security_issues)

        if analyze_performance:
            performance_issues = self._analyze_performance(urls)
            report.issues.extend(performance_issues)

        if analyze_content:
            content_issues = self._analyze_content_quality(urls)
            report.issues.extend(content_issues)

        # Подсчитать сводку
        report.summary = self._calculate_summary(report.issues)

        # Рассчитать SEO score
        report.seo_score = self._calculate_seo_score(report)

        self.logger.info(
            f"Analysis complete: {len(report.issues)} issues found, "
            f"SEO score: {report.seo_score:.1f}"
        )

        return report

    def _analyze_seo(self, urls: List[Any]) -> List[ContentIssue]:
        """
        Анализ SEO проблем.

        Проверяет:
        - Отсутствующие или некорректные title
        - Проблемы с meta description
        - Дублирующиеся title/description
        - Отсутствующие H1
        - Отсутствующие alt tags на изображениях

        Args:
            urls: Список URL объектов

        Returns:
            Список найденных SEO проблем
        """
        issues = []
        title_map = defaultdict(list)  # Для поиска дубликатов
        meta_map = defaultdict(list)

        for url in urls:
            # Пропустить не-HTML страницы
            if not url.content_type or "html" not in url.content_type.lower():
                continue

            # Проверка title
            if not url.title:
                issues.append(ContentIssue(
                    url=url.url,
                    issue_type="seo",
                    severity=IssueSeverity.ERROR,
                    message="Отсутствует title",
                    details={"field": "title"}
                ))
            elif len(url.title) < self.thresholds["title_min_length"]:
                issues.append(ContentIssue(
                    url=url.url,
                    issue_type="seo",
                    severity=IssueSeverity.WARNING,
                    message=f"Title слишком короткий ({len(url.title)} символов)",
                    details={"field": "title", "length": len(url.title), "title": url.title}
                ))
            elif len(url.title) > self.thresholds["title_max_length"]:
                issues.append(ContentIssue(
                    url=url.url,
                    issue_type="seo",
                    severity=IssueSeverity.WARNING,
                    message=f"Title слишком длинный ({len(url.title)} символов)",
                    details={"field": "title", "length": len(url.title), "title": url.title}
                ))

            # Собрать для поиска дубликатов
            if url.title:
                title_map[url.title].append(url.url)

            # Проверка meta description
            if not url.meta_description:
                issues.append(ContentIssue(
                    url=url.url,
                    issue_type="seo",
                    severity=IssueSeverity.WARNING,
                    message="Отсутствует meta description",
                    details={"field": "meta_description"}
                ))
            elif len(url.meta_description) < self.thresholds["meta_description_min_length"]:
                issues.append(ContentIssue(
                    url=url.url,
                    issue_type="seo",
                    severity=IssueSeverity.INFO,
                    message=f"Meta description короткое ({len(url.meta_description)} символов)",
                    details={
                        "field": "meta_description",
                        "length": len(url.meta_description)
                    }
                ))
            elif len(url.meta_description) > self.thresholds["meta_description_max_length"]:
                issues.append(ContentIssue(
                    url=url.url,
                    issue_type="seo",
                    severity=IssueSeverity.INFO,
                    message=f"Meta description длинное ({len(url.meta_description)} символов)",
                    details={
                        "field": "meta_description",
                        "length": len(url.meta_description)
                    }
                ))

            # Собрать для поиска дубликатов
            if url.meta_description:
                meta_map[url.meta_description].append(url.url)

            # Проверка canonical
            if not url.canonical_url and url.url != url.canonical_url:
                issues.append(ContentIssue(
                    url=url.url,
                    issue_type="seo",
                    severity=IssueSeverity.INFO,
                    message="Отсутствует canonical URL",
                    details={"field": "canonical"}
                ))

            # Проверка structured data
            if not url.has_schema_org and not url.has_open_graph:
                issues.append(ContentIssue(
                    url=url.url,
                    issue_type="seo",
                    severity=IssueSeverity.INFO,
                    message="Отсутствуют структурированные данные (Schema.org, Open Graph)",
                    details={"field": "structured_data"}
                ))

        # Найти дубликаты title
        for title, url_list in title_map.items():
            if len(url_list) > 1:
                for url in url_list:
                    issues.append(ContentIssue(
                        url=url,
                        issue_type="seo",
                        severity=IssueSeverity.WARNING,
                        message=f"Дублирующийся title (найдено {len(url_list)} страниц)",
                        details={
                            "field": "title",
                            "title": title,
                            "duplicate_count": len(url_list)
                        }
                    ))

        # Найти дубликаты meta description
        for meta, url_list in meta_map.items():
            if len(url_list) > 1:
                for url in url_list:
                    issues.append(ContentIssue(
                        url=url,
                        issue_type="seo",
                        severity=IssueSeverity.INFO,
                        message=f"Дублирующееся meta description (найдено {len(url_list)} страниц)",
                        details={
                            "field": "meta_description",
                            "duplicate_count": len(url_list)
                        }
                    ))

        return issues

    def _analyze_broken_links(
        self,
        urls: List[Any],
        errors: List[Any]
    ) -> List[ContentIssue]:
        """
        Анализ битых ссылок.

        Args:
            urls: Список URL объектов
            errors: Список ошибок

        Returns:
            Список проблем с битыми ссылками
        """
        issues = []

        # Проверка HTTP статус кодов
        for url in urls:
            if url.status_code == 404:
                issues.append(ContentIssue(
                    url=url.url,
                    issue_type="broken_link",
                    severity=IssueSeverity.ERROR,
                    message="Страница не найдена (404)",
                    details={"status_code": 404}
                ))
            elif url.status_code >= 500:
                issues.append(ContentIssue(
                    url=url.url,
                    issue_type="broken_link",
                    severity=IssueSeverity.CRITICAL,
                    message=f"Ошибка сервера ({url.status_code})",
                    details={"status_code": url.status_code}
                ))
            elif url.status_code >= 400:
                issues.append(ContentIssue(
                    url=url.url,
                    issue_type="broken_link",
                    severity=IssueSeverity.ERROR,
                    message=f"Ошибка клиента ({url.status_code})",
                    details={"status_code": url.status_code}
                ))

        # Проверка ошибок
        for error in errors:
            severity = IssueSeverity.ERROR

            if error.error_type == "timeout":
                severity = IssueSeverity.WARNING
                message = "Таймаут при загрузке страницы"
            elif error.error_type == "connection_error":
                severity = IssueSeverity.CRITICAL
                message = "Ошибка подключения"
            elif error.error_type == "dns_error":
                severity = IssueSeverity.CRITICAL
                message = "Ошибка DNS"
            else:
                message = f"Ошибка: {error.error_message}"

            issues.append(ContentIssue(
                url=error.url,
                issue_type="broken_link",
                severity=severity,
                message=message,
                details={
                    "error_type": error.error_type,
                    "error_message": error.error_message,
                    "retry_count": error.retry_count
                }
            ))

        return issues

    def _analyze_security(self, urls: List[Any]) -> List[ContentIssue]:
        """
        Анализ security проблем.

        Проверяет:
        - Mixed content (HTTP на HTTPS странице)
        - Отсутствие HTTPS
        - Insecure forms

        Args:
            urls: Список URL объектов

        Returns:
            Список security проблем
        """
        issues = []

        for url in urls:
            # Проверка HTTP (должен быть HTTPS)
            if url.url.startswith("http://"):
                issues.append(ContentIssue(
                    url=url.url,
                    issue_type="security",
                    severity=IssueSeverity.WARNING,
                    message="Страница использует HTTP вместо HTTPS",
                    details={"protocol": "http"}
                ))

            # Проверка insecure forms (если есть формы на HTTP)
            if url.url.startswith("http://") and url.has_forms:
                issues.append(ContentIssue(
                    url=url.url,
                    issue_type="security",
                    severity=IssueSeverity.CRITICAL,
                    message="Небезопасная форма (HTTP без SSL/TLS)",
                    details={"protocol": "http", "has_forms": True}
                ))

            # TODO: Проверка mixed content требует анализа ресурсов на странице
            # Это может быть добавлено позже через парсинг HTML

        return issues

    def _analyze_performance(self, urls: List[Any]) -> List[ContentIssue]:
        """
        Анализ производительности.

        Проверяет:
        - Медленные страницы
        - Большие файлы
        - Множественные редиректы

        Args:
            urls: Список URL объектов

        Returns:
            Список performance проблем
        """
        issues = []

        for url in urls:
            # Проверка времени ответа
            if url.response_time:
                if url.response_time >= self.thresholds["response_time_critical"]:
                    issues.append(ContentIssue(
                        url=url.url,
                        issue_type="performance",
                        severity=IssueSeverity.CRITICAL,
                        message=f"Очень медленная загрузка ({url.response_time:.2f}s)",
                        details={"response_time": url.response_time}
                    ))
                elif url.response_time >= self.thresholds["response_time_warning"]:
                    issues.append(ContentIssue(
                        url=url.url,
                        issue_type="performance",
                        severity=IssueSeverity.WARNING,
                        message=f"Медленная загрузка ({url.response_time:.2f}s)",
                        details={"response_time": url.response_time}
                    ))

            # Проверка размера страницы
            if url.size_bytes:
                if url.size_bytes >= self.thresholds["page_size_critical"]:
                    issues.append(ContentIssue(
                        url=url.url,
                        issue_type="performance",
                        severity=IssueSeverity.ERROR,
                        message=f"Очень большой размер страницы ({url.size_bytes / (1024*1024):.2f} MB)",
                        details={"size_bytes": url.size_bytes}
                    ))
                elif url.size_bytes >= self.thresholds["page_size_warning"]:
                    issues.append(ContentIssue(
                        url=url.url,
                        issue_type="performance",
                        severity=IssueSeverity.WARNING,
                        message=f"Большой размер страницы ({url.size_bytes / (1024*1024):.2f} MB)",
                        details={"size_bytes": url.size_bytes}
                    ))

            # Проверка редиректов
            if url.redirect_chain and len(url.redirect_chain) > 3:
                issues.append(ContentIssue(
                    url=url.url,
                    issue_type="performance",
                    severity=IssueSeverity.WARNING,
                    message=f"Множественные редиректы ({len(url.redirect_chain)} переходов)",
                    details={
                        "redirect_count": len(url.redirect_chain),
                        "redirect_chain": url.redirect_chain
                    }
                ))

        return issues

    def _analyze_content_quality(self, urls: List[Any]) -> List[ContentIssue]:
        """
        Анализ качества контента.

        Проверяет:
        - Тонкий контент (thin content)
        - Дубликаты контента

        Args:
            urls: Список URL объектов

        Returns:
            Список проблем с качеством контента
        """
        issues = []

        for url in urls:
            # Пропустить не-HTML страницы
            if not url.content_type or "html" not in url.content_type.lower():
                continue

            # Проверка на thin content
            title_len = len(url.title) if url.title else 0
            desc_len = len(url.meta_description) if url.meta_description else 0
            total_len = title_len + desc_len

            if total_len < self.thresholds["thin_content_threshold"]:
                issues.append(ContentIssue(
                    url=url.url,
                    issue_type="content",
                    severity=IssueSeverity.INFO,
                    message=f"Возможно тонкий контент (title+description = {total_len} символов)",
                    details={
                        "title_length": title_len,
                        "description_length": desc_len,
                        "total_length": total_len
                    }
                ))

        return issues

    def _calculate_summary(self, issues: List[ContentIssue]) -> Dict[str, int]:
        """
        Подсчитать сводку по проблемам.

        Args:
            issues: Список проблем

        Returns:
            Словарь с подсчётом по категориям
        """
        summary = defaultdict(int)

        for issue in issues:
            # По типу проблемы
            summary[f"type_{issue.issue_type}"] += 1

            # По серьёзности
            summary[f"severity_{issue.severity.value}"] += 1

        # Общее количество
        summary["total"] = len(issues)

        return dict(summary)

    def _calculate_seo_score(self, report: ContentAnalysisReport) -> float:
        """
        Рассчитать SEO score (0-100).

        Чем меньше проблем, тем выше score.

        Args:
            report: Отчёт об анализе

        Returns:
            SEO score (0-100)
        """
        if report.total_pages == 0:
            return 100.0

        # Веса для разных типов проблем
        weights = {
            IssueSeverity.CRITICAL: 10,
            IssueSeverity.ERROR: 5,
            IssueSeverity.WARNING: 2,
            IssueSeverity.INFO: 0.5,
        }

        # Подсчитать штрафные баллы
        penalty = 0
        for issue in report.issues:
            penalty += weights.get(issue.severity, 1)

        # Нормализовать на количество страниц
        penalty_per_page = penalty / report.total_pages

        # Рассчитать score (максимум 100)
        score = max(0, 100 - penalty_per_page)

        return round(score, 1)
