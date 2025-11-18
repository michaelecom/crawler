"""
Repository pattern для доступа к данным.

Инкапсулирует всю логику работы с БД и предоставляет
чистый API для других модулей.
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from webcrawler.storage.models import (
    ContentHash,
    CrawlSession,
    Error,
    Link,
    Statistics,
    URL,
)
from webcrawler.utils.helpers import calculate_content_hash
from webcrawler.utils.logger import get_logger
from webcrawler.utils.validators import normalize_url

logger = get_logger(__name__)


class BaseRepository:
    """
    Базовый класс для всех репозиториев.

    Предоставляет общие CRUD операции.
    """

    def __init__(self, session: AsyncSession):
        """
        Инициализация репозитория.

        Args:
            session: Async database сессия
        """
        self.session = session


class CrawlSessionRepository(BaseRepository):
    """
    Репозиторий для работы с сессиями краулинга.

    Example:
        >>> repo = CrawlSessionRepository(session)
        >>> session = await repo.create(session_id="abc123", start_url="https://example.com")
    """

    async def create(
        self,
        session_id: str,
        start_url: str,
        max_depth: int = 0,
        max_pages: int = 0,
        config: Optional[dict] = None,
        **kwargs,
    ) -> CrawlSession:
        """
        Создать новую сессию краулинга.

        Args:
            session_id: Уникальный ID сессии
            start_url: Начальный URL
            max_depth: Максимальная глубина
            max_pages: Максимум страниц
            config: Конфигурация сессии
            **kwargs: Дополнительные параметры

        Returns:
            CrawlSession: Созданная сессия
        """
        crawl_session = CrawlSession(
            session_id=session_id,
            start_url=start_url,
            max_depth=max_depth,
            max_pages=max_pages,
            config=config,
            status="pending",
            **kwargs
        )

        self.session.add(crawl_session)
        await self.session.flush()

        logger.info("crawl_session_created", session_id=session_id, start_url=start_url)
        return crawl_session

    async def get_by_id(self, session_id: int) -> Optional[CrawlSession]:
        """Получить сессию по ID."""
        result = await self.session.execute(
            select(CrawlSession).where(CrawlSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_by_session_id(self, session_id: str) -> Optional[CrawlSession]:
        """Получить сессию по session_id."""
        result = await self.session.execute(
            select(CrawlSession).where(CrawlSession.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        session_id: int,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """
        Обновить статус сессии.

        Args:
            session_id: ID сессии
            status: Новый статус (pending, running, paused, completed, failed)
            error_message: Сообщение об ошибке (если есть)
        """
        update_data = {"status": status, "updated_at": datetime.utcnow()}

        if status == "running" and not await self._get_started_at(session_id):
            update_data["started_at"] = datetime.utcnow()
        elif status in ["completed", "failed"]:
            update_data["completed_at"] = datetime.utcnow()

        if error_message:
            update_data["error_message"] = error_message

        await self.session.execute(
            update(CrawlSession)
            .where(CrawlSession.id == session_id)
            .values(**update_data)
        )

        logger.info("crawl_session_status_updated", session_id=session_id, status=status)

    async def _get_started_at(self, session_id: int) -> Optional[datetime]:
        """Получить started_at для сессии."""
        result = await self.session.execute(
            select(CrawlSession.started_at).where(CrawlSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def update_stats(
        self,
        session_id: int,
        urls_discovered: Optional[int] = None,
        urls_crawled: Optional[int] = None,
        urls_failed: Optional[int] = None,
        bytes_downloaded: Optional[int] = None,
    ) -> None:
        """
        Обновить статистику сессии.

        Args:
            session_id: ID сессии
            urls_discovered: Количество обнаруженных URL
            urls_crawled: Количество обработанных URL
            urls_failed: Количество failed URL
            bytes_downloaded: Скачано байт
        """
        update_data = {"updated_at": datetime.utcnow()}

        if urls_discovered is not None:
            update_data["total_urls_discovered"] = urls_discovered
        if urls_crawled is not None:
            update_data["total_urls_crawled"] = urls_crawled
        if urls_failed is not None:
            update_data["total_urls_failed"] = urls_failed
        if bytes_downloaded is not None:
            update_data["total_bytes_downloaded"] = bytes_downloaded

        await self.session.execute(
            update(CrawlSession)
            .where(CrawlSession.id == session_id)
            .values(**update_data)
        )

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[CrawlSession]:
        """
        Получить все сессии.

        Args:
            limit: Максимум записей
            offset: Смещение

        Returns:
            list: Список сессий
        """
        result = await self.session.execute(
            select(CrawlSession)
            .order_by(CrawlSession.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def delete(self, session_id: int) -> None:
        """
        Удалить сессию и все связанные данные.

        Args:
            session_id: ID сессии
        """
        await self.session.execute(
            delete(CrawlSession).where(CrawlSession.id == session_id)
        )
        logger.info("crawl_session_deleted", session_id=session_id)

    async def get_all_sessions(
        self, limit: int = 100, offset: int = 0
    ) -> list[CrawlSession]:
        """
        Alias для get_all для совместимости с CLI.

        Args:
            limit: Максимум записей
            offset: Смещение

        Returns:
            list[CrawlSession]: Список сессий
        """
        return await self.get_all(limit=limit, offset=offset)

    async def delete_old_sessions(
        self, older_than: datetime, status: Optional[str] = None
    ) -> int:
        """
        Удалить старые сессии.

        Args:
            older_than: Дата отсечки
            status: Фильтр по статусу (опционально)

        Returns:
            int: Количество удалённых сессий
        """
        from sqlalchemy import and_

        conditions = [CrawlSession.created_at < older_than]

        if status:
            conditions.append(CrawlSession.status == status)

        # Подсчёт перед удалением
        count_result = await self.session.execute(
            select(func.count(CrawlSession.id)).where(and_(*conditions))
        )
        count = count_result.scalar() or 0

        # Удаление
        await self.session.execute(delete(CrawlSession).where(and_(*conditions)))

        logger.info(
            "old_sessions_deleted",
            count=count,
            older_than=older_than,
            status=status,
        )

        return count


class URLRepository(BaseRepository):
    """
    Репозиторий для работы с URL.

    Example:
        >>> repo = URLRepository(session)
        >>> url = await repo.create(session_id=1, url="https://example.com/page")
    """

    async def create(
        self,
        session_id: int,
        url: str,
        depth: int = 0,
        **kwargs,
    ) -> URL:
        """
        Создать новую запись URL.

        Args:
            session_id: ID сессии краулинга
            url: URL страницы
            depth: Глубина от стартового URL
            **kwargs: Дополнительные параметры

        Returns:
            URL: Созданная запись
        """
        from webcrawler.utils.validators import extract_domain

        # Нормализуем URL и вычисляем хеш
        normalized = normalize_url(url)
        url_hash = calculate_content_hash(normalized.encode(), algorithm="sha256")
        domain = extract_domain(url, include_subdomain=False)

        url_obj = URL(
            session_id=session_id,
            url=url,
            url_hash=url_hash,
            normalized_url=normalized,
            domain=domain,
            depth=depth,
            status="pending",
            **kwargs
        )

        self.session.add(url_obj)
        await self.session.flush()

        return url_obj

    async def get_by_url_hash(
        self,
        session_id: int,
        url_hash: str
    ) -> Optional[URL]:
        """
        Получить URL по хешу (для дедупликации).

        Args:
            session_id: ID сессии
            url_hash: Хеш URL

        Returns:
            Optional[URL]: URL запись или None
        """
        result = await self.session.execute(
            select(URL).where(
                URL.session_id == session_id,
                URL.url_hash == url_hash
            )
        )
        return result.scalar_one_or_none()

    async def exists(self, session_id: int, url_hash: str) -> bool:
        """
        Проверить существование URL.

        Args:
            session_id: ID сессии
            url_hash: Хеш URL

        Returns:
            bool: True если URL существует
        """
        result = await self.session.execute(
            select(func.count(URL.id)).where(
                URL.session_id == session_id,
                URL.url_hash == url_hash
            )
        )
        count = result.scalar()
        return count > 0

    async def update_status(
        self,
        url_id: int,
        status: str,
        **kwargs
    ) -> None:
        """
        Обновить статус URL.

        Args:
            url_id: ID URL
            status: Новый статус
            **kwargs: Дополнительные поля для обновления
        """
        update_data = {"status": status}
        update_data.update(kwargs)

        if status == "completed":
            update_data["crawled_at"] = datetime.utcnow()

        await self.session.execute(
            update(URL)
            .where(URL.id == url_id)
            .values(**update_data)
        )

    async def increment_visit_count(self, url_id: int) -> None:
        """
        Увеличить счётчик посещений URL.

        Args:
            url_id: ID URL
        """
        await self.session.execute(
            update(URL)
            .where(URL.id == url_id)
            .values(visit_count=URL.visit_count + 1)
        )

    async def get_pending_urls(
        self,
        session_id: int,
        limit: int = 100
    ) -> list[URL]:
        """
        Получить pending URL для обработки.

        Args:
            session_id: ID сессии
            limit: Максимум URL

        Returns:
            list: Список pending URL
        """
        result = await self.session.execute(
            select(URL)
            .where(
                URL.session_id == session_id,
                URL.status == "pending"
            )
            .order_by(URL.depth.asc(), URL.discovered_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_domain(
        self,
        session_id: int,
        domain: str,
        limit: int = 100
    ) -> list[URL]:
        """
        Получить URL по домену.

        Args:
            session_id: ID сессии
            domain: Доменное имя
            limit: Максимум URL

        Returns:
            list: Список URL
        """
        result = await self.session.execute(
            select(URL)
            .where(
                URL.session_id == session_id,
                URL.domain == domain
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_by_status(
        self,
        session_id: int,
        status: str
    ) -> int:
        """
        Подсчитать URL по статусу.

        Args:
            session_id: ID сессии
            status: Статус URL

        Returns:
            int: Количество URL
        """
        result = await self.session.execute(
            select(func.count(URL.id)).where(
                URL.session_id == session_id,
                URL.status == status
            )
        )
        return result.scalar() or 0

    async def update_metadata(
        self,
        url_id: int,
        title: Optional[str] = None,
        meta_description: Optional[str] = None,
        meta_keywords: Optional[str] = None,
        meta_robots: Optional[str] = None,
        language: Optional[str] = None,
        has_schema_org: Optional[bool] = None,
        has_open_graph: Optional[bool] = None,
        structured_data: Optional[dict] = None,
        internal_links_count: Optional[int] = None,
        external_links_count: Optional[int] = None,
        content_hash: Optional[str] = None,
        canonical_url: Optional[str] = None,
    ) -> None:
        """
        Обновить метаданные URL после парсинга.

        Args:
            url_id: ID URL
            **kwargs: Метаданные для обновления
        """
        update_data = {}

        if title is not None:
            update_data["title"] = title
        if meta_description is not None:
            update_data["meta_description"] = meta_description
        if meta_keywords is not None:
            update_data["meta_keywords"] = meta_keywords
        if meta_robots is not None:
            update_data["meta_robots"] = meta_robots
        if language is not None:
            update_data["language"] = language
        if has_schema_org is not None:
            update_data["has_schema_org"] = has_schema_org
        if has_open_graph is not None:
            update_data["has_open_graph"] = has_open_graph
        if structured_data is not None:
            update_data["structured_data"] = structured_data
        if internal_links_count is not None:
            update_data["internal_links_count"] = internal_links_count
        if external_links_count is not None:
            update_data["external_links_count"] = external_links_count
        if content_hash is not None:
            update_data["content_hash"] = content_hash
        if canonical_url is not None:
            update_data["canonical_url"] = canonical_url

        if update_data:
            await self.session.execute(
                update(URL).where(URL.id == url_id).values(**update_data)
            )


class LinkRepository(BaseRepository):
    """
    Репозиторий для работы с графом ссылок.

    Example:
        >>> repo = LinkRepository(session)
        >>> link = await repo.create(session_id=1, source_url_id=1, target_url_id=2)
    """

    async def create(
        self,
        session_id: int,
        source_url_id: int,
        target_url_id: int,
        link_type: str = "hyperlink",
        **kwargs
    ) -> Link:
        """
        Создать связь между URL.

        Args:
            session_id: ID сессии
            source_url_id: ID источника
            target_url_id: ID цели
            link_type: Тип ссылки
            **kwargs: Дополнительные параметры

        Returns:
            Link: Созданная связь
        """
        link = Link(
            session_id=session_id,
            source_url_id=source_url_id,
            target_url_id=target_url_id,
            link_type=link_type,
            **kwargs
        )

        self.session.add(link)
        await self.session.flush()

        return link

    async def get_outgoing_links(
        self,
        source_url_id: int
    ) -> list[Link]:
        """
        Получить исходящие ссылки для URL.

        Args:
            source_url_id: ID URL источника

        Returns:
            list: Список ссылок
        """
        result = await self.session.execute(
            select(Link).where(Link.source_url_id == source_url_id)
        )
        return list(result.scalars().all())

    async def get_incoming_links(
        self,
        target_url_id: int
    ) -> list[Link]:
        """
        Получить входящие ссылки для URL.

        Args:
            target_url_id: ID URL цели

        Returns:
            list: Список ссылок
        """
        result = await self.session.execute(
            select(Link).where(Link.target_url_id == target_url_id)
        )
        return list(result.scalars().all())


class ErrorRepository(BaseRepository):
    """
    Репозиторий для работы с ошибками.

    Example:
        >>> repo = ErrorRepository(session)
        >>> error = await repo.create(session_id=1, url="https://example.com", error_type="timeout")
    """

    async def create(
        self,
        session_id: int,
        url: str,
        error_type: str,
        error_message: str,
        **kwargs
    ) -> Error:
        """
        Создать запись об ошибке.

        Args:
            session_id: ID сессии
            url: URL с ошибкой
            error_type: Тип ошибки
            error_message: Сообщение об ошибке
            **kwargs: Дополнительные параметры

        Returns:
            Error: Созданная запись
        """
        error = Error(
            session_id=session_id,
            url=url,
            error_type=error_type,
            error_message=error_message,
            **kwargs
        )

        self.session.add(error)
        await self.session.flush()

        logger.error(
            "error_logged",
            session_id=session_id,
            url=url,
            error_type=error_type,
            message=error_message
        )

        return error

    async def get_by_type(
        self,
        session_id: int,
        error_type: str,
        limit: int = 100
    ) -> list[Error]:
        """
        Получить ошибки по типу.

        Args:
            session_id: ID сессии
            error_type: Тип ошибки
            limit: Максимум записей

        Returns:
            list: Список ошибок
        """
        result = await self.session.execute(
            select(Error)
            .where(
                Error.session_id == session_id,
                Error.error_type == error_type
            )
            .order_by(Error.occurred_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent(
        self,
        session_id: int,
        limit: int = 100
    ) -> list[Error]:
        """
        Получить недавние ошибки.

        Args:
            session_id: ID сессии
            limit: Максимум записей

        Returns:
            list: Список ошибок
        """
        result = await self.session.execute(
            select(Error)
            .where(Error.session_id == session_id)
            .order_by(Error.occurred_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class StatisticsRepository(BaseRepository):
    """
    Репозиторий для работы со статистикой.

    Example:
        >>> repo = StatisticsRepository(session)
        >>> stats = await repo.get_or_create(session_id=1)
    """

    async def get_or_create(self, session_id: int) -> Statistics:
        """
        Получить или создать статистику для сессии.

        Args:
            session_id: ID сессии

        Returns:
            Statistics: Объект статистики
        """
        result = await self.session.execute(
            select(Statistics).where(Statistics.session_id == session_id)
        )
        stats = result.scalar_one_or_none()

        if not stats:
            stats = Statistics(session_id=session_id)
            self.session.add(stats)
            await self.session.flush()

        return stats

    async def update(
        self,
        session_id: int,
        **kwargs
    ) -> None:
        """
        Обновить статистику.

        Args:
            session_id: ID сессии
            **kwargs: Поля для обновления
        """
        kwargs["updated_at"] = datetime.utcnow()

        await self.session.execute(
            update(Statistics)
            .where(Statistics.session_id == session_id)
            .values(**kwargs)
        )

    async def update_statistics(
        self,
        session_id: int,
        total_urls: Optional[int] = None,
        total_pages_crawled: Optional[int] = None,
        total_errors: Optional[int] = None,
        total_duplicates: Optional[int] = None,
        status_2xx_count: Optional[int] = None,
        status_3xx_count: Optional[int] = None,
        status_4xx_count: Optional[int] = None,
        status_5xx_count: Optional[int] = None,
        avg_response_time: Optional[float] = None,
        total_bytes_downloaded: Optional[int] = None,
        pages_per_second: Optional[float] = None,
        top_domains: Optional[dict] = None,
        top_error_types: Optional[dict] = None,
        top_content_types: Optional[dict] = None,
    ) -> None:
        """
        Обновить статистику с конкретными параметрами.

        Args:
            session_id: ID сессии
            **kwargs: Поля для обновления
        """
        update_data = {}

        if total_urls is not None:
            update_data["total_urls"] = total_urls
        if total_pages_crawled is not None:
            update_data["total_pages_crawled"] = total_pages_crawled
        if total_errors is not None:
            update_data["total_errors"] = total_errors
        if total_duplicates is not None:
            update_data["total_duplicates"] = total_duplicates
        if status_2xx_count is not None:
            update_data["status_2xx_count"] = status_2xx_count
        if status_3xx_count is not None:
            update_data["status_3xx_count"] = status_3xx_count
        if status_4xx_count is not None:
            update_data["status_4xx_count"] = status_4xx_count
        if status_5xx_count is not None:
            update_data["status_5xx_count"] = status_5xx_count
        if avg_response_time is not None:
            update_data["avg_response_time"] = avg_response_time
        if total_bytes_downloaded is not None:
            update_data["total_bytes_downloaded"] = total_bytes_downloaded
        if pages_per_second is not None:
            update_data["pages_per_second"] = pages_per_second
        if top_domains is not None:
            update_data["top_domains"] = top_domains
        if top_error_types is not None:
            update_data["top_error_types"] = top_error_types
        if top_content_types is not None:
            update_data["top_content_types"] = top_content_types

        if update_data:
            await self.update(session_id, **update_data)
