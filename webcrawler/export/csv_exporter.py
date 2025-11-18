"""
CSV Exporter для экспорта данных краулинга в CSV формат.

Поддерживает:
- Экспорт URL в CSV
- Множественные CSV файлы (urls, links, errors, statistics)
- Кастомные разделители
- Опциональные заголовки
"""

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional

from webcrawler.export.base import BaseExporter
from webcrawler.storage.database import DatabaseManager


class CSVExporter(BaseExporter):
    """
    Экспортер данных в CSV формат.

    Создаёт CSV файлы с табличными данными.
    Может создавать отдельные файлы для URLs, ссылок, ошибок.

    Example:
        >>> exporter = CSVExporter(db_manager)
        >>> await exporter.export(
        ...     session_id="abc123",
        ...     output_path="results.csv",
        ...     delimiter=",",
        ...     include_headers=True
        ... )
    """

    async def export(
        self,
        session_id: str,
        output_path: str,
        delimiter: str = ",",
        encoding: str = "utf-8",
        include_headers: bool = True,
        split_by_type: bool = False,
        **options
    ) -> None:
        """
        Экспортировать данные сессии в CSV.

        Args:
            session_id: ID сессии для экспорта
            output_path: Путь к выходному CSV файлу
            delimiter: Разделитель полей (по умолчанию запятая)
            encoding: Кодировка файла
            include_headers: Включить заголовки колонок
            split_by_type: Создать отдельные файлы для URLs/links/errors
            **options: Дополнительные опции

        Raises:
            ValueError: Если сессия не найдена
        """
        self.logger.info(f"Starting CSV export for session {session_id}")

        # Получить данные
        data = await self._fetch_session_data(session_id)

        # Подготовить путь
        output = self._prepare_output_path(output_path)

        if split_by_type:
            # Создать отдельные файлы
            await self._export_split(
                data, output, delimiter, encoding, include_headers
            )
        else:
            # Один файл с URLs
            await self._export_urls(
                data["urls"], output, delimiter, encoding, include_headers
            )

        self.logger.info(f"CSV exported to {output}")

    async def _export_split(
        self,
        data: Dict[str, Any],
        base_path: Path,
        delimiter: str,
        encoding: str,
        include_headers: bool
    ) -> None:
        """
        Экспортировать в множественные CSV файлы.

        Создаёт:
        - {base}_urls.csv
        - {base}_links.csv
        - {base}_errors.csv
        - {base}_statistics.csv

        Args:
            data: Данные сессии
            base_path: Базовый путь для файлов
            delimiter: Разделитель
            encoding: Кодировка
            include_headers: Включить заголовки
        """
        # Определить базовое имя
        if base_path.suffix == ".csv":
            base_name = base_path.stem
            parent = base_path.parent
        else:
            base_name = base_path.name
            parent = base_path

        # URLs
        urls_path = parent / f"{base_name}_urls.csv"
        await self._export_urls(
            data["urls"], urls_path, delimiter, encoding, include_headers
        )
        self.logger.info(f"URLs exported to {urls_path}")

        # Links
        links_path = parent / f"{base_name}_links.csv"
        await self._export_links(
            data["links"], links_path, delimiter, encoding, include_headers
        )
        self.logger.info(f"Links exported to {links_path}")

        # Errors
        errors_path = parent / f"{base_name}_errors.csv"
        await self._export_errors(
            data["errors"], errors_path, delimiter, encoding, include_headers
        )
        self.logger.info(f"Errors exported to {errors_path}")

        # Statistics
        stats_path = parent / f"{base_name}_statistics.csv"
        await self._export_statistics(
            data, stats_path, delimiter, encoding, include_headers
        )
        self.logger.info(f"Statistics exported to {stats_path}")

    async def _export_urls(
        self,
        urls: List[Any],
        output_path: Path,
        delimiter: str,
        encoding: str,
        include_headers: bool
    ) -> None:
        """
        Экспортировать URLs в CSV.

        Args:
            urls: Список URL объектов
            output_path: Путь к файлу
            delimiter: Разделитель
            encoding: Кодировка
            include_headers: Включить заголовки
        """
        # Определить колонки
        fieldnames = [
            "url",
            "status_code",
            "depth",
            "content_type",
            "size_bytes",
            "response_time",
            "title",
            "meta_description",
            "internal_links",
            "external_links",
            "crawled_at",
        ]

        with open(output_path, "w", encoding=encoding, newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=fieldnames, delimiter=delimiter
            )

            if include_headers:
                writer.writeheader()

            # Записать URL
            for url in urls:
                writer.writerow({
                    "url": url.url,
                    "status_code": url.status_code or "",
                    "depth": url.depth,
                    "content_type": url.content_type or "",
                    "size_bytes": url.size_bytes or "",
                    "response_time": url.response_time or "",
                    "title": url.title or "",
                    "meta_description": url.meta_description or "",
                    "internal_links": url.internal_links_count or 0,
                    "external_links": url.external_links_count or 0,
                    "crawled_at": self._format_timestamp(url.crawled_at),
                })

    async def _export_links(
        self,
        links: List[Any],
        output_path: Path,
        delimiter: str,
        encoding: str,
        include_headers: bool
    ) -> None:
        """
        Экспортировать ссылки в CSV.

        Args:
            links: Список Link объектов
            output_path: Путь к файлу
            delimiter: Разделитель
            encoding: Кодировка
            include_headers: Включить заголовки
        """
        fieldnames = [
            "source_url",
            "target_url",
            "link_type",
            "anchor_text",
            "rel",
            "nofollow",
        ]

        with open(output_path, "w", encoding=encoding, newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=fieldnames, delimiter=delimiter
            )

            if include_headers:
                writer.writeheader()

            # Записать ссылки
            for link in links:
                writer.writerow({
                    "source_url": link.source_url,
                    "target_url": link.target_url,
                    "link_type": link.link_type,
                    "anchor_text": link.anchor_text or "",
                    "rel": link.rel or "",
                    "nofollow": link.nofollow or False,
                })

    async def _export_errors(
        self,
        errors: List[Any],
        output_path: Path,
        delimiter: str,
        encoding: str,
        include_headers: bool
    ) -> None:
        """
        Экспортировать ошибки в CSV.

        Args:
            errors: Список Error объектов
            output_path: Путь к файлу
            delimiter: Разделитель
            encoding: Кодировка
            include_headers: Включить заголовки
        """
        fieldnames = [
            "url",
            "error_type",
            "error_message",
            "status_code",
            "retry_count",
            "occurred_at",
        ]

        with open(output_path, "w", encoding=encoding, newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=fieldnames, delimiter=delimiter
            )

            if include_headers:
                writer.writeheader()

            # Записать ошибки
            for error in errors:
                writer.writerow({
                    "url": error.url,
                    "error_type": error.error_type,
                    "error_message": error.error_message or "",
                    "status_code": error.status_code or "",
                    "retry_count": error.retry_count or 0,
                    "occurred_at": self._format_timestamp(error.occurred_at),
                })

    async def _export_statistics(
        self,
        data: Dict[str, Any],
        output_path: Path,
        delimiter: str,
        encoding: str,
        include_headers: bool
    ) -> None:
        """
        Экспортировать статистику в CSV.

        Args:
            data: Данные сессии
            output_path: Путь к файлу
            delimiter: Разделитель
            encoding: Кодировка
            include_headers: Включить заголовки
        """
        stats = self._calculate_statistics(data)

        fieldnames = ["metric", "value"]

        with open(output_path, "w", encoding=encoding, newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=fieldnames, delimiter=delimiter
            )

            if include_headers:
                writer.writeheader()

            # Основная статистика
            writer.writerow({"metric": "Total URLs", "value": stats["total_urls"]})
            writer.writerow({"metric": "Total Links", "value": stats["total_links"]})
            writer.writerow({"metric": "Total Errors", "value": stats["total_errors"]})
            writer.writerow({
                "metric": "Average Response Time (s)",
                "value": f"{stats['avg_response_time']:.3f}"
            })
            writer.writerow({
                "metric": "Total Size (MB)",
                "value": f"{stats['total_bytes'] / (1024*1024):.2f}"
            })
            writer.writerow({
                "metric": "Duration (seconds)",
                "value": stats["duration_seconds"]
            })

            # Пустая строка
            writer.writerow({"metric": "", "value": ""})

            # Статус коды
            writer.writerow({"metric": "Status Codes", "value": ""})
            for code, count in sorted(stats["status_codes"].items()):
                writer.writerow({"metric": f"  {code}", "value": count})

            # Пустая строка
            writer.writerow({"metric": "", "value": ""})

            # Content types
            writer.writerow({"metric": "Content Types", "value": ""})
            for ct, count in sorted(
                stats["content_types"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]:  # Top 10
                writer.writerow({"metric": f"  {ct}", "value": count})

            # Пустая строка
            writer.writerow({"metric": "", "value": ""})

            # Depths
            writer.writerow({"metric": "Depth Distribution", "value": ""})
            for depth, count in sorted(stats["depths"].items()):
                writer.writerow({"metric": f"  Depth {depth}", "value": count})
