"""
HTML Exporter для создания интерактивных HTML отчётов.

Генерирует:
- Dashboard с ключевыми метриками
- Графики статистики (через Chart.js)
- Интерактивные таблицы
- Опциональный граф ссылок
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import json
from datetime import datetime

from webcrawler.export.base import BaseExporter
from webcrawler.storage.database import DatabaseManager


class HTMLExporter(BaseExporter):
    """
    Экспортер данных в HTML формат.

    Создаёт самодостаточный HTML файл с:
    - Встроенными стилями CSS
    - Встроенным JavaScript
    - Графиками (Chart.js через CDN)
    - Интерактивными таблицами

    Example:
        >>> exporter = HTMLExporter(db_manager)
        >>> await exporter.export(
        ...     session_id="abc123",
        ...     output_path="report.html",
        ...     include_charts=True,
        ...     theme="light"
        ... )
    """

    async def export(
        self,
        session_id: str,
        output_path: str,
        theme: str = "light",
        include_charts: bool = True,
        include_tables: bool = True,
        max_table_rows: int = 1000,
        **options
    ) -> None:
        """
        Экспортировать данные в HTML отчёт.

        Args:
            session_id: ID сессии для экспорта
            output_path: Путь к выходному HTML файлу
            theme: Тема оформления (light, dark)
            include_charts: Включить графики
            include_tables: Включить таблицы
            max_table_rows: Максимум строк в таблице
            **options: Дополнительные опции

        Raises:
            ValueError: Если сессия не найдена
        """
        self.logger.info(f"Starting HTML export for session {session_id}")

        # Получить данные
        data = await self._fetch_session_data(session_id)

        # Подготовить путь
        output = self._prepare_output_path(output_path)

        # Рассчитать статистику
        statistics = self._calculate_statistics(data)

        # Генерировать HTML
        html_content = self._generate_html(
            data,
            statistics,
            theme=theme,
            include_charts=include_charts,
            include_tables=include_tables,
            max_table_rows=max_table_rows
        )

        # Записать в файл
        with open(output, "w", encoding="utf-8") as f:
            f.write(html_content)

        self.logger.info(f"HTML report exported to {output}")

    def _generate_html(
        self,
        data: Dict[str, Any],
        statistics: Dict[str, Any],
        theme: str,
        include_charts: bool,
        include_tables: bool,
        max_table_rows: int
    ) -> str:
        """
        Генерировать HTML контент.

        Args:
            data: Данные сессии
            statistics: Статистика
            theme: Тема
            include_charts: Включить графики
            include_tables: Включить таблицы
            max_table_rows: Максимум строк

        Returns:
            HTML строка
        """
        session = data["session"]
        urls = data["urls"][:max_table_rows]  # Ограничить количество

        # Подготовить данные для графиков
        chart_data = self._prepare_chart_data(statistics) if include_charts else {}

        # Генерировать секции
        head = self._generate_head(theme, include_charts)
        header = self._generate_header(session)
        dashboard = self._generate_dashboard(statistics)
        charts = self._generate_charts(chart_data) if include_charts else ""
        tables = self._generate_tables(urls) if include_tables else ""
        footer = self._generate_footer()

        # Собрать HTML
        html = f"""<!DOCTYPE html>
<html lang="ru">
{head}
<body>
    <div class="container">
        {header}
        {dashboard}
        {charts}
        {tables}
        {footer}
    </div>
</body>
</html>"""

        return html

    def _generate_head(self, theme: str, include_charts: bool) -> str:
        """
        Генерировать <head> секцию.

        Args:
            theme: Тема оформления
            include_charts: Включить Chart.js

        Returns:
            HTML для head
        """
        chart_js = ""
        if include_charts:
            chart_js = '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>'

        css = self._generate_css(theme)

        return f"""<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crawl Report</title>
    {chart_js}
    <style>
{css}
    </style>
</head>"""

    def _generate_css(self, theme: str) -> str:
        """
        Генерировать CSS стили.

        Args:
            theme: Тема (light/dark)

        Returns:
            CSS строка
        """
        if theme == "dark":
            bg_color = "#1a1a1a"
            text_color = "#e0e0e0"
            card_bg = "#2d2d2d"
            border_color = "#404040"
        else:
            bg_color = "#f5f5f5"
            text_color = "#333"
            card_bg = "#ffffff"
            border_color = "#ddd"

        return f"""
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background-color: {bg_color};
            color: {text_color};
            line-height: 1.6;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .header h1 {{ margin-bottom: 10px; font-size: 2em; }}
        .header p {{ opacity: 0.9; }}
        .dashboard {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            background: {card_bg};
            padding: 25px;
            border-radius: 10px;
            border: 1px solid {border_color};
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .card h3 {{
            font-size: 0.9em;
            text-transform: uppercase;
            color: #888;
            margin-bottom: 10px;
        }}
        .card .metric {{
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
        }}
        .section {{
            background: {card_bg};
            padding: 25px;
            border-radius: 10px;
            border: 1px solid {border_color};
            margin-bottom: 30px;
        }}
        .section h2 {{
            margin-bottom: 20px;
            color: #667eea;
        }}
        .chart-container {{
            position: relative;
            height: 300px;
            margin-bottom: 30px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9em;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid {border_color};
        }}
        th {{
            background-color: {card_bg};
            font-weight: 600;
            position: sticky;
            top: 0;
        }}
        tr:hover {{
            background-color: {border_color};
        }}
        .status-200 {{ color: #10b981; font-weight: bold; }}
        .status-300 {{ color: #f59e0b; font-weight: bold; }}
        .status-400 {{ color: #ef4444; font-weight: bold; }}
        .status-500 {{ color: #dc2626; font-weight: bold; }}
        .url-cell {{
            max-width: 400px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #888;
            font-size: 0.9em;
        }}
        """

    def _generate_header(self, session: Any) -> str:
        """
        Генерировать header секцию.

        Args:
            session: Объект сессии

        Returns:
            HTML для header
        """
        return f"""
        <div class="header">
            <h1>📊 Crawl Report</h1>
            <p><strong>URL:</strong> {session.start_url}</p>
            <p><strong>Session ID:</strong> {session.session_id}</p>
            <p><strong>Started:</strong> {self._format_timestamp(session.start_time)}</p>
        </div>
        """

    def _generate_dashboard(self, statistics: Dict[str, Any]) -> str:
        """
        Генерировать dashboard с метриками.

        Args:
            statistics: Статистика

        Returns:
            HTML для dashboard
        """
        return f"""
        <div class="dashboard">
            <div class="card">
                <h3>Total URLs</h3>
                <div class="metric">{statistics['total_urls']:,}</div>
            </div>
            <div class="card">
                <h3>Total Links</h3>
                <div class="metric">{statistics['total_links']:,}</div>
            </div>
            <div class="card">
                <h3>Total Errors</h3>
                <div class="metric">{statistics['total_errors']:,}</div>
            </div>
            <div class="card">
                <h3>Avg Response Time</h3>
                <div class="metric">{statistics['avg_response_time']:.3f}s</div>
            </div>
            <div class="card">
                <h3>Total Size</h3>
                <div class="metric">{statistics['total_bytes'] / (1024*1024):.1f} MB</div>
            </div>
            <div class="card">
                <h3>Duration</h3>
                <div class="metric">{statistics['duration_seconds']:.0f}s</div>
            </div>
        </div>
        """

    def _prepare_chart_data(self, statistics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Подготовить данные для графиков.

        Args:
            statistics: Статистика

        Returns:
            Словарь с данными для Chart.js
        """
        return {
            "status_codes": {
                "labels": [str(code) for code in sorted(statistics["status_codes"].keys())],
                "data": [statistics["status_codes"][code] for code in sorted(statistics["status_codes"].keys())]
            },
            "content_types": {
                "labels": list(statistics["content_types"].keys())[:10],
                "data": list(statistics["content_types"].values())[:10]
            },
            "depths": {
                "labels": [f"Depth {d}" for d in sorted(statistics["depths"].keys())],
                "data": [statistics["depths"][d] for d in sorted(statistics["depths"].keys())]
            }
        }

    def _generate_charts(self, chart_data: Dict[str, Any]) -> str:
        """
        Генерировать секцию с графиками.

        Args:
            chart_data: Данные для графиков

        Returns:
            HTML для графиков
        """
        status_codes_json = json.dumps(chart_data["status_codes"])
        content_types_json = json.dumps(chart_data["content_types"])
        depths_json = json.dumps(chart_data["depths"])

        return f"""
        <div class="section">
            <h2>📈 Statistics</h2>

            <h3>Status Codes Distribution</h3>
            <div class="chart-container">
                <canvas id="statusCodesChart"></canvas>
            </div>

            <h3>Content Types Distribution</h3>
            <div class="chart-container">
                <canvas id="contentTypesChart"></canvas>
            </div>

            <h3>Depth Distribution</h3>
            <div class="chart-container">
                <canvas id="depthsChart"></canvas>
            </div>
        </div>

        <script>
            // Status Codes Chart
            const statusData = {status_codes_json};
            new Chart(document.getElementById('statusCodesChart'), {{
                type: 'bar',
                data: {{
                    labels: statusData.labels,
                    datasets: [{{
                        label: 'Count',
                        data: statusData.data,
                        backgroundColor: 'rgba(102, 126, 234, 0.6)',
                        borderColor: 'rgba(102, 126, 234, 1)',
                        borderWidth: 1
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: false }}
                    }}
                }}
            }});

            // Content Types Chart
            const contentData = {content_types_json};
            new Chart(document.getElementById('contentTypesChart'), {{
                type: 'pie',
                data: {{
                    labels: contentData.labels,
                    datasets: [{{
                        data: contentData.data,
                        backgroundColor: [
                            '#667eea', '#764ba2', '#f093fb', '#4facfe',
                            '#43e97b', '#fa709a', '#fee140', '#30cfd0',
                            '#a8edea', '#fed6e3'
                        ]
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false
                }}
            }});

            // Depth Chart
            const depthData = {depths_json};
            new Chart(document.getElementById('depthsChart'), {{
                type: 'line',
                data: {{
                    labels: depthData.labels,
                    datasets: [{{
                        label: 'Pages',
                        data: depthData.data,
                        fill: true,
                        backgroundColor: 'rgba(102, 126, 234, 0.2)',
                        borderColor: 'rgba(102, 126, 234, 1)',
                        tension: 0.4
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: false }}
                    }}
                }}
            }});
        </script>
        """

    def _generate_tables(self, urls: List[Any]) -> str:
        """
        Генерировать секцию с таблицами.

        Args:
            urls: Список URL для таблицы

        Returns:
            HTML для таблиц
        """
        rows = []
        for url in urls:
            status_class = ""
            if url.status_code:
                if 200 <= url.status_code < 300:
                    status_class = "status-200"
                elif 300 <= url.status_code < 400:
                    status_class = "status-300"
                elif 400 <= url.status_code < 500:
                    status_class = "status-400"
                elif url.status_code >= 500:
                    status_class = "status-500"

            row = f"""
                <tr>
                    <td class="url-cell" title="{url.url}">{url.url}</td>
                    <td class="{status_class}">{url.status_code or '-'}</td>
                    <td>{url.depth}</td>
                    <td>{(url.size_bytes / 1024):.1f} KB</td>
                    <td>{url.response_time:.3f}s</td>
                    <td>{url.title[:50] if url.title else '-'}</td>
                </tr>
            """
            rows.append(row)

        rows_html = "\n".join(rows)

        return f"""
        <div class="section">
            <h2>📄 URLs ({len(urls)} shown)</h2>
            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>URL</th>
                            <th>Status</th>
                            <th>Depth</th>
                            <th>Size</th>
                            <th>Time</th>
                            <th>Title</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </div>
        """

    def _generate_footer(self) -> str:
        """
        Генерировать footer.

        Returns:
            HTML для footer
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"""
        <div class="footer">
            <p>Generated by Enterprise Web Crawler on {now}</p>
        </div>
        """
