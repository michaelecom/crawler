"""
Excel Exporter для создания подробных Excel отчётов.

Требует: openpyxl
Установка: pip install openpyxl

Генерирует:
- Множественные листы (Summary, URLs, Links, Errors, etc.)
- Форматирование (цвета, шрифты, границы)
- Встроенные диаграммы
- Условное форматирование
- Формулы
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
from collections import Counter

from webcrawler.export.base import BaseExporter
from webcrawler.storage.database import DatabaseManager


class ExcelExporter(BaseExporter):
    """
    Экспортер данных в Excel формат.

    Создаёт профессиональный Excel файл с множественными
    листами, графиками и форматированием.
    Требует установленную библиотеку openpyxl.

    Example:
        >>> exporter = ExcelExporter(db_manager)
        >>> await exporter.export(
        ...     session_id="abc123",
        ...     output_path="report.xlsx",
        ...     include_charts=True
        ... )
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Инициализация экспортера.

        Args:
            db_manager: Менеджер базы данных

        Raises:
            ImportError: Если openpyxl не установлен
        """
        super().__init__(db_manager)

        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
            from openpyxl.utils import get_column_letter
            from openpyxl.chart import BarChart, PieChart, Reference

            self.openpyxl_available = True
        except ImportError:
            self.openpyxl_available = False

    async def export(
        self,
        session_id: str,
        output_path: str,
        include_charts: bool = True,
        include_links: bool = True,
        include_errors: bool = True,
        max_rows_per_sheet: int = 100000,
        **options
    ) -> None:
        """
        Экспортировать данные в Excel файл.

        Args:
            session_id: ID сессии для экспорта
            output_path: Путь к выходному Excel файлу
            include_charts: Включить диаграммы
            include_links: Включить лист с ссылками
            include_errors: Включить лист с ошибками
            max_rows_per_sheet: Максимум строк на лист
            **options: Дополнительные опции

        Raises:
            ImportError: Если openpyxl не установлен
            ValueError: Если сессия не найдена
        """
        if not self.openpyxl_available:
            raise ImportError(
                "openpyxl is required for Excel export. "
                "Install it with: pip install openpyxl"
            )

        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter
        from openpyxl.chart import BarChart, PieChart, Reference

        self.logger.info(f"Starting Excel export for session {session_id}")

        # Получить данные
        data = await self._fetch_session_data(session_id)

        # Подготовить путь
        output = self._prepare_output_path(output_path)

        # Рассчитать статистику
        statistics = self._calculate_statistics(data)

        # Создать workbook
        wb = Workbook()

        # Удалить default лист
        if "Sheet" in wb.sheetnames:
            wb.remove(wb["Sheet"])

        # Создать листы
        self._create_summary_sheet(wb, data["session"], statistics)
        self._create_urls_sheet(wb, data["urls"][:max_rows_per_sheet])

        if include_links and data["links"]:
            self._create_links_sheet(wb, data["links"][:max_rows_per_sheet])

        if include_errors and data["errors"]:
            self._create_errors_sheet(wb, data["errors"][:max_rows_per_sheet])

        self._create_status_codes_sheet(wb, statistics)
        self._create_content_types_sheet(wb, statistics)

        # Добавить диаграммы
        if include_charts:
            self._add_status_codes_chart(wb)
            self._add_content_types_chart(wb)

        # Сохранить
        wb.save(str(output))

        self.logger.info(f"Excel report exported to {output}")

    def _create_summary_sheet(
        self,
        wb: Any,
        session: Any,
        statistics: Dict[str, Any]
    ) -> None:
        """
        Создать лист Summary с общей информацией.

        Args:
            wb: Workbook объект
            session: Объект сессии
            statistics: Статистика
        """
        from openpyxl.styles import Font, Alignment, PatternFill

        ws = wb.create_sheet("Summary", 0)

        # Заголовок
        ws["A1"] = "Crawl Session Report"
        ws["A1"].font = Font(size=16, bold=True, color="667eea")
        ws.merge_cells("A1:B1")

        # Информация о сессии
        row = 3
        session_info = [
            ("Session ID", session.session_id),
            ("Start URL", session.start_url),
            ("Started", self._format_timestamp(session.start_time)),
            ("Status", session.status),
            ("", ""),  # Пустая строка
            ("Total URLs", f"{statistics['total_urls']:,}"),
            ("Total Links", f"{statistics['total_links']:,}"),
            ("Total Errors", f"{statistics['total_errors']:,}"),
            ("", ""),
            ("Average Response Time", f"{statistics['avg_response_time']:.3f}s"),
            ("Total Size", f"{statistics['total_bytes'] / (1024*1024):.2f} MB"),
            ("Duration", f"{statistics['duration_seconds']:.0f}s"),
            ("Crawl Rate", f"{statistics['crawl_rate']:.2f} pages/sec"),
        ]

        for label, value in session_info:
            if not label:
                row += 1
                continue

            ws[f"A{row}"] = label
            ws[f"B{row}"] = value

            # Форматирование заголовков
            ws[f"A{row}"].font = Font(bold=True)
            ws[f"A{row}"].fill = PatternFill(
                start_color="E8EAF6",
                end_color="E8EAF6",
                fill_type="solid"
            )

            row += 1

        # Автоширина колонок
        ws.column_dimensions["A"].width = 25
        ws.column_dimensions["B"].width = 50

    def _create_urls_sheet(
        self,
        wb: Any,
        urls: List[Any]
    ) -> None:
        """
        Создать лист URLs с таблицей URL.

        Args:
            wb: Workbook объект
            urls: Список URL объектов
        """
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter

        ws = wb.create_sheet("URLs")

        # Заголовки
        headers = [
            "URL", "Status Code", "Content Type", "Depth",
            "Size (KB)", "Response Time (s)", "Title",
            "Crawled At"
        ]

        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(
                start_color="667eea",
                end_color="667eea",
                fill_type="solid"
            )
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # Данные
        for row_idx, url in enumerate(urls, start=2):
            ws.cell(row=row_idx, column=1, value=url.url)
            ws.cell(row=row_idx, column=2, value=url.status_code or "-")
            ws.cell(row=row_idx, column=3, value=url.content_type or "-")
            ws.cell(row=row_idx, column=4, value=url.depth)
            ws.cell(row=row_idx, column=5, value=f"{url.size_bytes / 1024:.1f}" if url.size_bytes else "-")
            ws.cell(row=row_idx, column=6, value=f"{url.response_time:.3f}" if url.response_time else "-")
            ws.cell(row=row_idx, column=7, value=url.title or "-")
            ws.cell(row=row_idx, column=8, value=self._format_timestamp(url.crawled_at) if url.crawled_at else "-")

            # Цветовое кодирование по статус-коду
            if url.status_code:
                status_cell = ws.cell(row=row_idx, column=2)
                if 200 <= url.status_code < 300:
                    status_cell.fill = PatternFill(
                        start_color="C8E6C9",
                        end_color="C8E6C9",
                        fill_type="solid"
                    )
                elif 300 <= url.status_code < 400:
                    status_cell.fill = PatternFill(
                        start_color="FFF9C4",
                        end_color="FFF9C4",
                        fill_type="solid"
                    )
                elif 400 <= url.status_code < 500:
                    status_cell.fill = PatternFill(
                        start_color="FFCCBC",
                        end_color="FFCCBC",
                        fill_type="solid"
                    )
                elif url.status_code >= 500:
                    status_cell.fill = PatternFill(
                        start_color="FFCDD2",
                        end_color="FFCDD2",
                        fill_type="solid"
                    )

        # Автоширина колонок
        column_widths = [50, 12, 25, 8, 12, 18, 40, 20]
        for idx, width in enumerate(column_widths, start=1):
            ws.column_dimensions[get_column_letter(idx)].width = width

        # Freeze первой строки
        ws.freeze_panes = "A2"

    def _create_links_sheet(
        self,
        wb: Any,
        links: List[Any]
    ) -> None:
        """
        Создать лист Links с таблицей ссылок.

        Args:
            wb: Workbook объект
            links: Список Link объектов
        """
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter

        ws = wb.create_sheet("Links")

        # Заголовки
        headers = ["Source URL", "Target URL", "Anchor Text", "Link Type", "Rel"]

        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(
                start_color="667eea",
                end_color="667eea",
                fill_type="solid"
            )
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # Данные
        for row_idx, link in enumerate(links, start=2):
            ws.cell(row=row_idx, column=1, value=link.source_url)
            ws.cell(row=row_idx, column=2, value=link.target_url)
            ws.cell(row=row_idx, column=3, value=link.anchor_text or "-")
            ws.cell(row=row_idx, column=4, value=link.link_type or "-")
            ws.cell(row=row_idx, column=5, value=link.rel or "-")

            # Цветовое кодирование по типу
            type_cell = ws.cell(row=row_idx, column=4)
            if link.link_type == "internal":
                type_cell.fill = PatternFill(
                    start_color="C8E6C9",
                    end_color="C8E6C9",
                    fill_type="solid"
                )
            elif link.link_type == "external":
                type_cell.fill = PatternFill(
                    start_color="BBDEFB",
                    end_color="BBDEFB",
                    fill_type="solid"
                )

        # Автоширина
        column_widths = [50, 50, 30, 12, 20]
        for idx, width in enumerate(column_widths, start=1):
            ws.column_dimensions[get_column_letter(idx)].width = width

        ws.freeze_panes = "A2"

    def _create_errors_sheet(
        self,
        wb: Any,
        errors: List[Any]
    ) -> None:
        """
        Создать лист Errors с таблицей ошибок.

        Args:
            wb: Workbook объект
            errors: Список Error объектов
        """
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter

        ws = wb.create_sheet("Errors")

        # Заголовки
        headers = ["URL", "Error Type", "Error Message", "Occurred At"]

        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(
                start_color="EF5350",
                end_color="EF5350",
                fill_type="solid"
            )
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # Данные
        for row_idx, error in enumerate(errors, start=2):
            ws.cell(row=row_idx, column=1, value=error.url)
            ws.cell(row=row_idx, column=2, value=error.error_type or "-")
            ws.cell(row=row_idx, column=3, value=error.error_message or "-")
            ws.cell(row=row_idx, column=4, value=self._format_timestamp(error.occurred_at) if error.occurred_at else "-")

        # Автоширина
        column_widths = [50, 20, 60, 20]
        for idx, width in enumerate(column_widths, start=1):
            ws.column_dimensions[get_column_letter(idx)].width = width

        ws.freeze_panes = "A2"

    def _create_status_codes_sheet(
        self,
        wb: Any,
        statistics: Dict[str, Any]
    ) -> None:
        """
        Создать лист Status Codes с распределением статус-кодов.

        Args:
            wb: Workbook объект
            statistics: Статистика
        """
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter

        ws = wb.create_sheet("Status Codes")

        # Заголовки
        headers = ["Status Code", "Count", "Percentage"]

        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(
                start_color="667eea",
                end_color="667eea",
                fill_type="solid"
            )
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # Данные
        total = sum(statistics["status_codes"].values())
        row_idx = 2

        for code in sorted(statistics["status_codes"].keys()):
            count = statistics["status_codes"][code]
            percentage = (count / total * 100) if total > 0 else 0

            ws.cell(row=row_idx, column=1, value=str(code))
            ws.cell(row=row_idx, column=2, value=count)
            ws.cell(row=row_idx, column=3, value=f"{percentage:.1f}%")

            # Цветовое кодирование
            code_cell = ws.cell(row=row_idx, column=1)
            if 200 <= code < 300:
                code_cell.fill = PatternFill(start_color="C8E6C9", end_color="C8E6C9", fill_type="solid")
            elif 300 <= code < 400:
                code_cell.fill = PatternFill(start_color="FFF9C4", end_color="FFF9C4", fill_type="solid")
            elif 400 <= code < 500:
                code_cell.fill = PatternFill(start_color="FFCCBC", end_color="FFCCBC", fill_type="solid")
            elif code >= 500:
                code_cell.fill = PatternFill(start_color="FFCDD2", end_color="FFCDD2", fill_type="solid")

            row_idx += 1

        # Автоширина
        for idx in range(1, 4):
            ws.column_dimensions[get_column_letter(idx)].width = 15

    def _create_content_types_sheet(
        self,
        wb: Any,
        statistics: Dict[str, Any]
    ) -> None:
        """
        Создать лист Content Types с распределением типов контента.

        Args:
            wb: Workbook объект
            statistics: Статистика
        """
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter

        ws = wb.create_sheet("Content Types")

        # Заголовки
        headers = ["Content Type", "Count", "Percentage"]

        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(
                start_color="667eea",
                end_color="667eea",
                fill_type="solid"
            )
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # Данные
        total = sum(statistics["content_types"].values())
        row_idx = 2

        # Сортировать по количеству (по убыванию)
        sorted_cts = sorted(
            statistics["content_types"].items(),
            key=lambda x: x[1],
            reverse=True
        )

        for content_type, count in sorted_cts:
            percentage = (count / total * 100) if total > 0 else 0

            ws.cell(row=row_idx, column=1, value=content_type)
            ws.cell(row=row_idx, column=2, value=count)
            ws.cell(row=row_idx, column=3, value=f"{percentage:.1f}%")

            row_idx += 1

        # Автоширина
        ws.column_dimensions["A"].width = 40
        ws.column_dimensions["B"].width = 12
        ws.column_dimensions["C"].width = 15

    def _add_status_codes_chart(self, wb: Any) -> None:
        """
        Добавить диаграмму статус-кодов на лист Status Codes.

        Args:
            wb: Workbook объект
        """
        try:
            from openpyxl.chart import BarChart, Reference

            ws = wb["Status Codes"]

            # Создать диаграмму
            chart = BarChart()
            chart.title = "Status Codes Distribution"
            chart.x_axis.title = "Status Code"
            chart.y_axis.title = "Count"

            # Данные (пропускаем заголовок)
            max_row = ws.max_row
            data = Reference(ws, min_col=2, min_row=1, max_row=max_row)
            categories = Reference(ws, min_col=1, min_row=2, max_row=max_row)

            chart.add_data(data, titles_from_data=True)
            chart.set_categories(categories)

            # Стиль
            chart.height = 10
            chart.width = 20

            # Добавить на лист
            ws.add_chart(chart, "E2")

        except Exception as e:
            self.logger.warning(f"Could not add status codes chart: {e}")

    def _add_content_types_chart(self, wb: Any) -> None:
        """
        Добавить диаграмму типов контента на лист Content Types.

        Args:
            wb: Workbook объект
        """
        try:
            from openpyxl.chart import PieChart, Reference

            ws = wb["Content Types"]

            # Создать диаграмму
            chart = PieChart()
            chart.title = "Content Types Distribution"

            # Данные (ограничить топ-10 для читаемости)
            max_row = min(ws.max_row, 11)  # Заголовок + топ 10
            data = Reference(ws, min_col=2, min_row=1, max_row=max_row)
            categories = Reference(ws, min_col=1, min_row=2, max_row=max_row)

            chart.add_data(data, titles_from_data=True)
            chart.set_categories(categories)

            # Стиль
            chart.height = 12
            chart.width = 20

            # Добавить на лист
            ws.add_chart(chart, "E2")

        except Exception as e:
            self.logger.warning(f"Could not add content types chart: {e}")
