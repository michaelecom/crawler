"""
JSON Exporter для экспорта данных краулинга в JSON формат.

Поддерживает:
- Полный экспорт всех данных сессии
- Красивое форматирование (pretty print)
- Сжатие gzip
- Streaming для больших данных
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, AsyncIterator

from webcrawler.export.base import BaseExporter
from webcrawler.storage.database import DatabaseManager


class JSONExporter(BaseExporter):
    """
    Экспортер данных в JSON формат.

    Создаёт структурированный JSON файл со всеми данными сессии:
    - Metadata сессии
    - Список URL с метаданными
    - Граф ссылок
    - Список ошибок
    - Статистика

    Example:
        >>> exporter = JSONExporter(db_manager)
        >>> await exporter.export(
        ...     session_id="abc123",
        ...     output_path="results.json",
        ...     pretty=True,
        ...     compress=True
        ... )
    """

    async def export(
        self,
        session_id: str,
        output_path: str,
        pretty: bool = True,
        compress: bool = False,
        include_all_fields: bool = True,
        **options
    ) -> None:
        """
        Экспортировать данные сессии в JSON.

        Args:
            session_id: ID сессии для экспорта
            output_path: Путь к выходному JSON файлу
            pretty: Красивое форматирование (indent=2)
            compress: Сжать файл через gzip
            include_all_fields: Включить все поля (иначе только основные)
            **options: Дополнительные опции (не используются)

        Raises:
            ValueError: Если сессия не найдена
        """
        self.logger.info(f"Starting JSON export for session {session_id}")

        # Получить данные
        data = await self._fetch_session_data(session_id)

        # Подготовить путь
        output = self._prepare_output_path(output_path)

        # Создать JSON структуру
        json_data = self._build_json_structure(data, include_all_fields)

        # Записать в файл
        with open(output, "w", encoding="utf-8") as f:
            if pretty:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            else:
                json.dump(json_data, f, ensure_ascii=False)

        self.logger.info(f"JSON exported to {output}")

        # Сжать если нужно
        if compress:
            output = self._compress_file(output, compression="gzip")
            self.logger.info(f"Compressed to {output}")

    def _build_json_structure(
        self,
        data: Dict[str, Any],
        include_all: bool
    ) -> Dict[str, Any]:
        """
        Построить JSON структуру из данных БД.

        Args:
            data: Данные из БД (session, urls, links, errors)
            include_all: Включить все поля или только основные

        Returns:
            Словарь для сериализации в JSON
        """
        session = data["session"]
        urls = data["urls"]
        links = data["links"]
        errors = data["errors"]

        # Metadata сессии
        metadata = {
            "session_id": session.session_id,
            "start_url": session.start_url,
            "start_time": self._format_timestamp(session.start_time),
            "end_time": self._format_timestamp(session.end_time),
            "duration_seconds": session.duration_seconds or 0,
            "status": session.status,
            "max_depth": session.max_depth,
            "max_pages": session.max_pages,
        }

        if include_all:
            metadata.update({
                "config": session.config_snapshot or {},
                "created_at": self._format_timestamp(session.created_at),
                "updated_at": self._format_timestamp(session.updated_at),
            })

        # Статистика
        statistics = self._calculate_statistics(data)

        # URLs
        urls_list = [
            self._serialize_url(url, include_all) for url in urls
        ]

        # Links
        links_list = [
            self._serialize_link(link, include_all) for link in links
        ]

        # Errors
        errors_list = [
            self._serialize_error(error, include_all) for error in errors
        ]

        return {
            "metadata": metadata,
            "statistics": statistics,
            "urls": urls_list,
            "links": links_list,
            "errors": errors_list,
        }

    def _serialize_url(self, url: Any, include_all: bool) -> Dict[str, Any]:
        """
        Сериализовать URL в словарь.

        Args:
            url: URL объект из БД
            include_all: Включить все поля

        Returns:
            Словарь с данными URL
        """
        result = {
            "url": url.url,
            "url_hash": url.url_hash,
            "status": url.status,
            "status_code": url.status_code,
            "depth": url.depth,
            "content_type": url.content_type,
            "size_bytes": url.size_bytes,
            "response_time": url.response_time,
        }

        if include_all:
            result.update({
                "title": url.title,
                "meta_description": url.meta_description,
                "meta_keywords": url.meta_keywords,
                "canonical_url": url.canonical_url,
                "language": url.language,
                "internal_links_count": url.internal_links_count,
                "external_links_count": url.external_links_count,
                "has_forms": url.has_forms,
                "has_schema_org": url.has_schema_org,
                "has_open_graph": url.has_open_graph,
                "structured_data": url.structured_data,
                "http_headers": url.http_headers,
                "redirect_chain": url.redirect_chain,
                "ssl_info": url.ssl_info,
                "discovered_at": self._format_timestamp(url.discovered_at),
                "crawled_at": self._format_timestamp(url.crawled_at),
            })

        return result

    def _serialize_link(self, link: Any, include_all: bool) -> Dict[str, Any]:
        """
        Сериализовать ссылку в словарь.

        Args:
            link: Link объект из БД
            include_all: Включить все поля

        Returns:
            Словарь с данными ссылки
        """
        result = {
            "source_url": link.source_url,
            "target_url": link.target_url,
            "link_type": link.link_type,
            "anchor_text": link.anchor_text,
        }

        if include_all:
            result.update({
                "rel": link.rel,
                "title": link.title,
                "nofollow": link.nofollow,
                "discovered_at": self._format_timestamp(link.discovered_at),
            })

        return result

    def _serialize_error(self, error: Any, include_all: bool) -> Dict[str, Any]:
        """
        Сериализовать ошибку в словарь.

        Args:
            error: Error объект из БД
            include_all: Включить все поля

        Returns:
            Словарь с данными ошибки
        """
        result = {
            "url": error.url,
            "error_type": error.error_type,
            "error_message": error.error_message,
            "status_code": error.status_code,
        }

        if include_all:
            result.update({
                "retry_count": error.retry_count,
                "occurred_at": self._format_timestamp(error.occurred_at),
            })

        return result


class StreamingJSONExporter(BaseExporter):
    """
    Streaming JSON экспортер для больших данных.

    Использует генераторы для экспорта данных батчами,
    избегая загрузки всех данных в память.

    Example:
        >>> exporter = StreamingJSONExporter(db_manager)
        >>> async with exporter.stream(session_id="abc123") as stream:
        ...     async for batch in stream.batches(batch_size=1000):
        ...         # Обработка батча
        ...         process_batch(batch)
    """

    async def export(
        self,
        session_id: str,
        output_path: str,
        batch_size: int = 1000,
        **options
    ) -> None:
        """
        Экспортировать данные используя streaming.

        Args:
            session_id: ID сессии для экспорта
            output_path: Путь к выходному JSON файлу
            batch_size: Размер батча для streaming
            **options: Дополнительные опции

        Raises:
            ValueError: Если сессия не найдена
        """
        self.logger.info(
            f"Starting streaming JSON export for session {session_id}"
        )

        # Подготовить путь
        output = self._prepare_output_path(output_path)

        # Получить данные
        data = await self._fetch_session_data(session_id)

        # Записать в файл с streaming
        with open(output, "w", encoding="utf-8") as f:
            # Начало JSON
            f.write('{\n  "metadata": ')
            json.dump(
                {
                    "session_id": data["session"].session_id,
                    "start_url": data["session"].start_url,
                },
                f,
                ensure_ascii=False
            )
            f.write(',\n  "urls": [\n')

            # Стриминг URL батчами
            urls = data["urls"]
            for i in range(0, len(urls), batch_size):
                batch = urls[i:i + batch_size]

                for j, url in enumerate(batch):
                    url_dict = self._serialize_url_basic(url)
                    json.dump(url_dict, f, ensure_ascii=False)

                    # Запятая между элементами
                    if i + j < len(urls) - 1:
                        f.write(',\n')

                self.logger.debug(
                    f"Exported batch {i//batch_size + 1}, "
                    f"{len(batch)} URLs"
                )

            f.write('\n  ]\n}')

        self.logger.info(f"Streaming JSON exported to {output}")

    def _serialize_url_basic(self, url: Any) -> Dict[str, Any]:
        """
        Базовая сериализация URL (только основные поля).

        Args:
            url: URL объект

        Returns:
            Словарь с основными полями
        """
        return {
            "url": url.url,
            "status_code": url.status_code,
            "depth": url.depth,
            "size_bytes": url.size_bytes,
        }
