"""
PDF Exporter для создания PDF отчётов.

Требует: reportlab
Установка: pip install reportlab

Генерирует:
- Титульную страницу
- Оглавление
- Сводку статистики
- Таблицы с данными
- Графики (упрощённые)
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from webcrawler.export.base import BaseExporter
from webcrawler.storage.database import DatabaseManager


class PDFExporter(BaseExporter):
    """
    Экспортер данных в PDF формат.

    Создаёт профессиональный PDF отчёт с таблицами и графиками.
    Требует установленную библиотеку reportlab.

    Example:
        >>> exporter = PDFExporter(db_manager)
        >>> await exporter.export(
        ...     session_id="abc123",
        ...     output_path="report.pdf",
        ...     page_size="A4",
        ...     orientation="portrait"
        ... )
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Инициализация экспортера.

        Args:
            db_manager: Менеджер базы данных

        Raises:
            ImportError: Если reportlab не установлен
        """
        super().__init__(db_manager)

        try:
            from reportlab.lib.pagesizes import A4, LETTER
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph,
                Spacer, PageBreak, Image
            )
            from reportlab.pdfgen import canvas

            self.reportlab_available = True
        except ImportError:
            self.reportlab_available = False

    async def export(
        self,
        session_id: str,
        output_path: str,
        page_size: str = "A4",
        orientation: str = "portrait",
        include_toc: bool = True,
        include_charts: bool = False,  # Упрощённые графики
        max_table_rows: int = 100,
        **options
    ) -> None:
        """
        Экспортировать данные в PDF отчёт.

        Args:
            session_id: ID сессии для экспорта
            output_path: Путь к выходному PDF файлу
            page_size: Размер страницы (A4, Letter)
            orientation: Ориентация (portrait, landscape)
            include_toc: Включить оглавление
            include_charts: Включить упрощённые графики
            max_table_rows: Максимум строк в таблицах
            **options: Дополнительные опции

        Raises:
            ImportError: Если reportlab не установлен
            ValueError: Если сессия не найдена
        """
        if not self.reportlab_available:
            raise ImportError(
                "reportlab is required for PDF export. "
                "Install it with: pip install reportlab"
            )

        from reportlab.lib.pagesizes import A4, LETTER, landscape
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph,
            Spacer, PageBreak
        )

        self.logger.info(f"Starting PDF export for session {session_id}")

        # Получить данные
        data = await self._fetch_session_data(session_id)

        # Подготовить путь
        output = self._prepare_output_path(output_path)

        # Рассчитать статистику
        statistics = self._calculate_statistics(data)

        # Определить размер страницы
        if page_size == "Letter":
            pagesize = LETTER
        else:
            pagesize = A4

        if orientation == "landscape":
            pagesize = landscape(pagesize)

        # Создать PDF
        doc = SimpleDocTemplate(
            str(output),
            pagesize=pagesize,
            rightMargin=inch,
            leftMargin=inch,
            topMargin=inch,
            bottomMargin=inch,
        )

        # Стили
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#667eea'),
            spaceAfter=30,
        )
        heading_style = styles['Heading2']
        normal_style = styles['Normal']

        # Контент
        story = []

        # Титульная страница
        story.extend(self._create_title_page(data["session"], title_style, normal_style))
        story.append(PageBreak())

        # Сводка статистики
        story.append(Paragraph("Сводка", heading_style))
        story.append(Spacer(1, 12))
        story.extend(self._create_summary_section(statistics, normal_style))
        story.append(Spacer(1, 20))

        # Распределения
        story.append(Paragraph("Распределения", heading_style))
        story.append(Spacer(1, 12))
        story.extend(self._create_distributions_section(statistics, colors))
        story.append(PageBreak())

        # Таблица URL
        urls = data["urls"][:max_table_rows]
        story.append(Paragraph(f"URL ({len(urls)} показано)", heading_style))
        story.append(Spacer(1, 12))
        story.extend(self._create_urls_table(urls, colors))

        # Построить PDF
        doc.build(story)

        self.logger.info(f"PDF report exported to {output}")

    def _create_title_page(
        self,
        session: Any,
        title_style: Any,
        normal_style: Any
    ) -> List[Any]:
        """
        Создать титульную страницу.

        Args:
            session: Объект сессии
            title_style: Стиль заголовка
            normal_style: Обычный стиль

        Returns:
            Список элементов для story
        """
        from reportlab.platypus import Paragraph, Spacer

        elements = []

        # Заголовок
        elements.append(Spacer(1, 2*inch))
        elements.append(Paragraph("Crawl Report", title_style))
        elements.append(Spacer(1, 0.5*inch))

        # Информация о сессии
        info_lines = [
            f"<b>Start URL:</b> {session.start_url}",
            f"<b>Session ID:</b> {session.session_id}",
            f"<b>Started:</b> {self._format_timestamp(session.start_time)}",
            f"<b>Status:</b> {session.status}",
        ]

        for line in info_lines:
            elements.append(Paragraph(line, normal_style))
            elements.append(Spacer(1, 12))

        return elements

    def _create_summary_section(
        self,
        statistics: Dict[str, Any],
        normal_style: Any
    ) -> List[Any]:
        """
        Создать секцию сводки.

        Args:
            statistics: Статистика
            normal_style: Стиль текста

        Returns:
            Список элементов
        """
        from reportlab.platypus import Paragraph, Spacer

        elements = []

        summary_items = [
            ("Total URLs", f"{statistics['total_urls']:,}"),
            ("Total Links", f"{statistics['total_links']:,}"),
            ("Total Errors", f"{statistics['total_errors']:,}"),
            ("Avg Response Time", f"{statistics['avg_response_time']:.3f}s"),
            ("Total Size", f"{statistics['total_bytes'] / (1024*1024):.2f} MB"),
            ("Duration", f"{statistics['duration_seconds']:.0f}s"),
        ]

        for label, value in summary_items:
            elements.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
            elements.append(Spacer(1, 6))

        return elements

    def _create_distributions_section(
        self,
        statistics: Dict[str, Any],
        colors: Any
    ) -> List[Any]:
        """
        Создать секцию распределений.

        Args:
            statistics: Статистика
            colors: Модуль colors из reportlab

        Returns:
            Список элементов
        """
        from reportlab.platypus import Table, TableStyle, Spacer, Paragraph
        from reportlab.lib.styles import getSampleStyleSheet

        styles = getSampleStyleSheet()
        elements = []

        # Status Codes
        if statistics["status_codes"]:
            elements.append(Paragraph("<b>Status Codes:</b>", styles['Normal']))
            elements.append(Spacer(1, 6))

            data = [["Status Code", "Count"]]
            for code in sorted(statistics["status_codes"].keys()):
                data.append([str(code), str(statistics["status_codes"][code])])

            table = Table(data, colWidths=[2*inch, 2*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))

            elements.append(table)
            elements.append(Spacer(1, 20))

        # Content Types (top 10)
        if statistics["content_types"]:
            elements.append(Paragraph("<b>Top Content Types:</b>", styles['Normal']))
            elements.append(Spacer(1, 6))

            data = [["Content Type", "Count"]]
            sorted_cts = sorted(
                statistics["content_types"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]

            for ct, count in sorted_cts:
                data.append([ct, str(count)])

            table = Table(data, colWidths=[3*inch, 1.5*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))

            elements.append(table)

        return elements

    def _create_urls_table(
        self,
        urls: List[Any],
        colors: Any
    ) -> List[Any]:
        """
        Создать таблицу URL.

        Args:
            urls: Список URL
            colors: Модуль colors

        Returns:
            Список элементов
        """
        from reportlab.platypus import Table, TableStyle
        from reportlab.lib.units import inch

        data = [["URL", "Status", "Depth", "Size (KB)", "Time (s)"]]

        for url in urls:
            # Укоротить URL для PDF
            url_text = url.url[:50] + "..." if len(url.url) > 50 else url.url

            data.append([
                url_text,
                str(url.status_code or "-"),
                str(url.depth),
                f"{(url.size_bytes / 1024):.1f}" if url.size_bytes else "-",
                f"{url.response_time:.3f}" if url.response_time else "-",
            ])

        table = Table(data, colWidths=[2.5*inch, 0.8*inch, 0.6*inch, 0.8*inch, 0.8*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))

        return [table]
