"""
Базовый абстрактный класс для экспортеров.

Определяет общий интерфейс и общую функциональность
для всех типов экспортеров данных краулинга.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional
import gzip
import zipfile
from datetime import datetime

from webcrawler.storage.database import DatabaseManager
from webcrawler.storage.repository import (
    CrawlSessionRepository,
    URLRepository,
    LinkRepository,
    ErrorRepository,
)
from webcrawler.utils.logger import LoggerMixin


class ExportFilter:
    """
    Фильтр для экспорта данных.

    Позволяет фильтровать URL перед экспортом
    по различным критериям.
    """

    def __init__(
        self,
        status: Optional[str] = None,
        min_depth: Optional[int] = None,
        max_depth: Optional[int] = None,
        status_codes: Optional[List[int]] = None,
        content_types: Optional[List[str]] = None,
    ):
        """
        Инициализация фильтра.

        Args:
            status: Статус URL (completed, pending, failed)
            min_depth: Минимальная глубина
            max_depth: Максимальная глубина
            status_codes: Список HTTP статус кодов
            content_types: Список content types
        """
        self.status = status
        self.min_depth = min_depth
        self.max_depth = max_depth
        self.status_codes = status_codes or []
        self.content_types = content_types or []

    def apply(self, url: Any) -> bool:
        """
        Проверить, проходит ли URL через фильтр.

        Args:
            url: Объект URL для проверки

        Returns:
            True если URL проходит фильтр, False иначе
        """
        # Фильтр по статусу
        if self.status and url.status != self.status:
            return False

        # Фильтр по глубине
        if self.min_depth is not None and url.depth < self.min_depth:
            return False

        if self.max_depth is not None and url.depth > self.max_depth:
            return False

        # Фильтр по статус коду
        if self.status_codes and url.status_code not in self.status_codes:
            return False

        # Фильтр по content type
        if self.content_types:
            if not url.content_type:
                return False

            # Проверка wildcard (*) в content types
            matched = False
            for ct in self.content_types:
                if ct.endswith("/*"):
                    # Wildcard matching (например, "image/*")
                    prefix = ct[:-2]
                    if url.content_type.startswith(prefix):
                        matched = True
                        break
                elif url.content_type == ct:
                    matched = True
                    break

            if not matched:
                return False

        return True


class BaseExporter(ABC, LoggerMixin):
    """
    Базовый абстрактный класс для всех экспортеров.

    Предоставляет общую функциональность:
    - Доступ к БД через repositories
    - Сжатие файлов
    - Фильтрация данных
    - Логирование
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Инициализация экспортера.

        Args:
            db_manager: Менеджер базы данных
        """
        self.db_manager = db_manager
        self._filters: List[ExportFilter] = []

    def add_filter(self, filter_obj: ExportFilter) -> None:
        """
        Добавить фильтр для экспорта.

        Args:
            filter_obj: Объект фильтра
        """
        self._filters.append(filter_obj)

    def _apply_filters(self, urls: List[Any]) -> List[Any]:
        """
        Применить все фильтры к списку URL.

        Args:
            urls: Список URL для фильтрации

        Returns:
            Отфильтрованный список URL
        """
        if not self._filters:
            return urls

        filtered = urls
        for filter_obj in self._filters:
            filtered = [url for url in filtered if filter_obj.apply(url)]

        return filtered

    async def _fetch_session_data(
        self, session_id: str
    ) -> Dict[str, Any]:
        """
        Получить все данные сессии из БД.

        Args:
            session_id: ID сессии краулинга

        Returns:
            Словарь с данными сессии

        Raises:
            ValueError: Если сессия не найдена
        """
        async with self.db_manager.session() as db_session:
            # Repositories
            session_repo = CrawlSessionRepository(db_session)
            url_repo = URLRepository(db_session)
            link_repo = LinkRepository(db_session)
            error_repo = ErrorRepository(db_session)

            # Получение данных
            session = await session_repo.get_by_session_id(session_id)
            if not session:
                raise ValueError(f"Session {session_id} not found")

            # Получить все URL
            all_urls = await url_repo.get_all_by_session(session_id)

            # Применить фильтры
            urls = self._apply_filters(all_urls)

            # Получить ссылки и ошибки
            links = await link_repo.get_all_by_session(session_id)
            errors = await error_repo.get_all_by_session(session_id)

            self.logger.info(
                f"Fetched session data: {len(urls)} URLs "
                f"(filtered from {len(all_urls)}), "
                f"{len(links)} links, {len(errors)} errors"
            )

            return {
                "session": session,
                "urls": urls,
                "links": links,
                "errors": errors,
            }

    def _compress_file(
        self,
        file_path: Path,
        compression: str = "gzip"
    ) -> Path:
        """
        Сжать файл.

        Args:
            file_path: Путь к файлу для сжатия
            compression: Тип сжатия (gzip, zip)

        Returns:
            Путь к сжатому файлу
        """
        if compression == "gzip":
            compressed_path = Path(f"{file_path}.gz")

            with open(file_path, "rb") as f_in:
                with gzip.open(compressed_path, "wb") as f_out:
                    f_out.writelines(f_in)

            # Удалить оригинальный файл
            file_path.unlink()

            self.logger.info(f"Compressed to {compressed_path}")
            return compressed_path

        elif compression == "zip":
            compressed_path = Path(f"{file_path}.zip")

            with zipfile.ZipFile(compressed_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(file_path, file_path.name)

            # Удалить оригинальный файл
            file_path.unlink()

            self.logger.info(f"Compressed to {compressed_path}")
            return compressed_path

        else:
            raise ValueError(f"Unknown compression type: {compression}")

    def _prepare_output_path(self, output_path: str) -> Path:
        """
        Подготовить путь для выходного файла.

        Создаёт директории если нужно.

        Args:
            output_path: Путь к выходному файлу

        Returns:
            Path объект
        """
        path = Path(output_path)

        # Создать родительские директории
        path.parent.mkdir(parents=True, exist_ok=True)

        return path

    @abstractmethod
    async def export(
        self,
        session_id: str,
        output_path: str,
        **options
    ) -> None:
        """
        Экспортировать данные сессии.

        Должен быть реализован в подклассах.

        Args:
            session_id: ID сессии для экспорта
            output_path: Путь к выходному файлу
            **options: Дополнительные опции экспорта
        """
        pass

    def _format_timestamp(self, dt: Optional[datetime]) -> str:
        """
        Форматировать timestamp для экспорта.

        Args:
            dt: Datetime объект

        Returns:
            ISO formatted строка или пустая строка
        """
        if dt is None:
            return ""

        return dt.isoformat()

    def _calculate_statistics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Рассчитать статистику для сессии.

        Args:
            data: Данные сессии (session, urls, links, errors)

        Returns:
            Словарь со статистикой
        """
        session = data["session"]
        urls = data["urls"]
        links = data["links"]
        errors = data["errors"]

        # Подсчёт статусов
        status_counts = {}
        for url in urls:
            status = url.status_code or 0
            status_counts[status] = status_counts.get(status, 0) + 1

        # Подсчёт типов контента
        content_type_counts = {}
        for url in urls:
            ct = url.content_type or "unknown"
            # Упростить content type (взять только основную часть)
            ct_main = ct.split(";")[0].strip()
            content_type_counts[ct_main] = content_type_counts.get(ct_main, 0) + 1

        # Подсчёт глубин
        depth_counts = {}
        for url in urls:
            depth = url.depth
            depth_counts[depth] = depth_counts.get(depth, 0) + 1

        # Подсчёт типов ссылок
        link_type_counts = {}
        for link in links:
            lt = link.link_type
            link_type_counts[lt] = link_type_counts.get(lt, 0) + 1

        # Средние значения
        total_urls = len(urls)

        if total_urls > 0:
            avg_response_time = sum(
                url.response_time for url in urls if url.response_time
            ) / total_urls

            total_bytes = sum(
                url.size_bytes for url in urls if url.size_bytes
            )
        else:
            avg_response_time = 0
            total_bytes = 0

        return {
            "total_urls": total_urls,
            "total_links": len(links),
            "total_errors": len(errors),
            "status_codes": status_counts,
            "content_types": content_type_counts,
            "depths": depth_counts,
            "link_types": link_type_counts,
            "avg_response_time": avg_response_time,
            "total_bytes": total_bytes,
            "start_time": self._format_timestamp(session.start_time),
            "end_time": self._format_timestamp(session.end_time),
            "duration_seconds": session.duration_seconds or 0,
        }
