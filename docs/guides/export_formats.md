# Форматы экспорта

Руководство по экспорту результатов краулинга в различные форматы для анализа и отчётности.

## Обзор

Enterprise Web Crawler поддерживает экспорт данных в следующие форматы:

- **JSON** - структурированные данные для программной обработки
- **CSV** - таблицы для Excel/Google Sheets
- **HTML** - интерактивные отчёты с графиками
- **PDF** - печатные отчёты
- **Excel** - многостраничные таблицы с форматированием
- **GraphML** - графы для Gephi/Cytoscape
- **SQLite** - полная БД для анализа

## JSON экспорт

### Базовый экспорт

```bash
# CLI
crawler export --session-id abc123 --format json --output results.json

# С сжатием
crawler export --session-id abc123 --format json --output results.json.gz --compress
```

```python
# Python API
from webcrawler.export import JSONExporter

exporter = JSONExporter(db_manager)
await exporter.export(
    session_id="abc123",
    output_path="results.json",
    compress=True
)
```

### Структура JSON

```json
{
  "metadata": {
    "session_id": "abc123",
    "start_url": "https://example.com",
    "start_time": "2025-11-18T10:00:00Z",
    "end_time": "2025-11-18T10:30:00Z",
    "duration_seconds": 1800,
    "status": "completed"
  },
  "statistics": {
    "total_urls": 1234,
    "urls_crawled": 1200,
    "urls_failed": 34,
    "avg_response_time": 0.234,
    "total_bytes": 45678900,
    "domains_discovered": 1,
    "status_codes": {
      "200": 1150,
      "301": 30,
      "404": 20,
      "500": 4
    }
  },
  "urls": [
    {
      "url": "https://example.com",
      "url_hash": "abc123...",
      "status": "completed",
      "status_code": 200,
      "depth": 0,
      "content_type": "text/html",
      "size_bytes": 12345,
      "response_time": 0.123,
      "discovered_at": "2025-11-18T10:00:01Z",
      "crawled_at": "2025-11-18T10:00:02Z",
      "title": "Example Domain",
      "meta_description": "Example website",
      "internal_links_count": 10,
      "external_links_count": 2,
      "headers": {
        "server": "nginx",
        "content-type": "text/html; charset=utf-8"
      }
    }
  ],
  "links": [
    {
      "source_url": "https://example.com",
      "target_url": "https://example.com/about",
      "link_type": "hyperlink",
      "anchor_text": "About Us",
      "rel": null,
      "discovered_at": "2025-11-18T10:00:02Z"
    }
  ],
  "errors": [
    {
      "url": "https://example.com/broken",
      "error_type": "http_error",
      "status_code": 404,
      "error_message": "Not Found",
      "occurred_at": "2025-11-18T10:05:00Z"
    }
  ]
}
```

### Конфигурация JSON экспорта

```yaml
export:
  json:
    # Красивое форматирование
    pretty: true

    # Отступы
    indent: 2

    # Включать все поля
    include_all_fields: true

    # Фильтры
    filters:
      # Только успешные URL
      only_success: false

      # Минимальная глубина
      min_depth: 0

      # Максимальная глубина
      max_depth: null

      # Статус коды
      status_codes: []

    # Разделить на части (для больших экспортов)
    split_size: 10000  # URL на файл
```

## CSV экспорт

### Экспорт URL

```bash
crawler export --session-id abc123 --format csv --output urls.csv
```

CSV структура:

```csv
url,status_code,depth,content_type,size_bytes,response_time,title,internal_links,external_links,crawled_at
https://example.com,200,0,text/html,12345,0.123,Example Domain,10,2,2025-11-18T10:00:02Z
https://example.com/about,200,1,text/html,8900,0.089,About Us,5,1,2025-11-18T10:00:05Z
```

### Несколько CSV файлов

```yaml
export:
  csv:
    # Создавать отдельные файлы
    split_by_type: true

    # Файлы для создания
    files:
      urls: true
      links: true
      errors: true
      statistics: true

    # Разделитель
    delimiter: ","

    # Кодировка
    encoding: "utf-8"

    # Включать заголовки
    include_headers: true
```

Результат:

```
exports/
├── abc123_urls.csv
├── abc123_links.csv
├── abc123_errors.csv
└── abc123_statistics.csv
```

## HTML отчёт

### Интерактивный отчёт

```bash
crawler export --session-id abc123 --format html --output report.html
```

Генерируется полноценный HTML отчёт с:

- **Dashboard** - общая статистика
- **Графики** - визуализация данных (Chart.js/Plotly)
- **Таблицы** - интерактивные таблицы (DataTables)
- **Граф ссылок** - визуализация структуры сайта (D3.js)
- **Фильтры** - поиск и фильтрация данных

### Конфигурация HTML

```yaml
export:
  html_report:
    # Тема
    theme: "light"  # light, dark

    # Включить компоненты
    include_dashboard: true
    include_charts: true
    include_tables: true
    include_graph: true
    include_errors: true

    # График настройки
    charts:
      # Типы графиков
      status_codes_pie: true
      response_time_histogram: true
      depth_distribution: true
      crawl_timeline: true
      content_types_bar: true

    # Граф ссылок
    graph:
      enabled: true
      layout: "force"  # force, hierarchical, circular
      max_nodes: 1000
      interactive: true
      zoom: true

    # Таблицы
    tables:
      sortable: true
      searchable: true
      pagination: true
      page_size: 50

    # Экспорт из HTML
    allow_export: true
    export_formats: ["csv", "json"]
```

### Пример секций отчёта

```html
<!DOCTYPE html>
<html>
<head>
    <title>Crawl Report - example.com</title>
    <link rel="stylesheet" href="report.css">
</head>
<body>
    <!-- Dashboard -->
    <section id="dashboard">
        <div class="card">
            <h3>Total URLs</h3>
            <div class="metric">1,234</div>
        </div>
        <div class="card">
            <h3>Success Rate</h3>
            <div class="metric">97.2%</div>
        </div>
        <!-- ... -->
    </section>

    <!-- Charts -->
    <section id="charts">
        <canvas id="statusCodesChart"></canvas>
        <canvas id="responseTimeChart"></canvas>
    </section>

    <!-- Link Graph -->
    <section id="graph">
        <div id="network-graph"></div>
    </section>

    <!-- Tables -->
    <section id="tables">
        <table id="urls-table" class="display">
            <thead>
                <tr>
                    <th>URL</th>
                    <th>Status</th>
                    <th>Size</th>
                    <th>Time</th>
                </tr>
            </thead>
        </table>
    </section>

    <script src="report.js"></script>
</body>
</html>
```

## PDF отчёт

### Генерация PDF

```bash
crawler export --session-id abc123 --format pdf --output report.pdf
```

```python
# Python API
from webcrawler.export import PDFExporter

exporter = PDFExporter(db_manager)
await exporter.export(
    session_id="abc123",
    output_path="report.pdf",
    include_graphs=True,
    include_screenshots=True
)
```

### Конфигурация PDF

```yaml
export:
  pdf_report:
    # Размер страницы
    page_size: "A4"  # A4, Letter, Legal

    # Ориентация
    orientation: "portrait"  # portrait, landscape

    # Поля (мм)
    margins:
      top: 20
      bottom: 20
      left: 20
      right: 20

    # Включить секции
    include_cover: true
    include_toc: true
    include_summary: true
    include_charts: true
    include_url_list: true
    include_errors: true
    include_graph: true

    # Графики
    charts:
      format: "png"
      dpi: 300

    # Таблицы
    tables:
      font_size: 8
      alternate_rows: true

    # Граф
    graph:
      max_nodes: 500
      layout: "hierarchical"
```

### Структура PDF

1. **Обложка**
   - Название сайта
   - Дата краулинга
   - Логотип

2. **Оглавление**
   - Ссылки на секции

3. **Executive Summary**
   - Ключевые метрики
   - Основные находки

4. **Статистика**
   - Таблицы с цифрами
   - Графики

5. **Детали URL**
   - Списки страниц
   - Статус коды

6. **Ошибки**
   - Битые ссылки
   - HTTP ошибки

7. **Визуализация**
   - Граф структуры сайта

## Excel экспорт

### Многостраничный Excel

```bash
crawler export --session-id abc123 --format excel --output report.xlsx
```

Создаётся Excel файл с листами:

- **Summary** - общая статистика
- **URLs** - все URL с метаданными
- **Links** - граф ссылок
- **Errors** - ошибки
- **Status Codes** - группировка по статус кодам
- **Content Types** - группировка по типам
- **Charts** - встроенные графики

### Конфигурация Excel

```yaml
export:
  excel_export:
    # Листы для создания
    sheets:
      - "Summary"
      - "URLs"
      - "Links"
      - "Errors"
      - "Status Codes"
      - "Content Types"

    # Форматирование
    auto_width: true
    freeze_panes: true
    filters: true
    conditional_formatting: true

    # Графики Excel
    include_charts: true

    # Цветовая схема
    color_scheme:
      header: "#4472C4"
      success: "#70AD47"
      warning: "#FFC000"
      error: "#FF0000"

    # Формулы
    add_formulas: true
```

### Пример листа Summary

```
| Metric                  | Value      |
|------------------------|------------|
| Total URLs             | 1,234      |
| URLs Crawled           | 1,200      |
| URLs Failed            | 34         |
| Success Rate           | 97.2%      |
| Avg Response Time      | 234ms      |
| Total Size             | 43.5 MB    |
| Start Time             | 10:00:00   |
| End Time               | 10:30:00   |
| Duration               | 30m 0s     |
```

## GraphML экспорт

### Граф для анализа

GraphML - формат для graph analysis tools (Gephi, Cytoscape, yEd).

```bash
crawler export --session-id abc123 --format graphml --output graph.graphml
```

### Конфигурация GraphML

```yaml
export:
  graphml:
    # Атрибуты узлов
    node_attributes:
      - "url"
      - "status_code"
      - "depth"
      - "size_bytes"
      - "response_time"
      - "title"

    # Атрибуты рёбер
    edge_attributes:
      - "link_type"
      - "anchor_text"
      - "rel"

    # Фильтры
    max_nodes: 10000
    include_external: false
```

### Структура GraphML

```xml
<?xml version="1.0" encoding="UTF-8"?>
<graphml>
  <key id="url" for="node" attr.name="url" attr.type="string"/>
  <key id="status" for="node" attr.name="status_code" attr.type="int"/>
  <key id="depth" for="node" attr.name="depth" attr.type="int"/>

  <graph edgedefault="directed">
    <node id="1">
      <data key="url">https://example.com</data>
      <data key="status">200</data>
      <data key="depth">0</data>
    </node>

    <node id="2">
      <data key="url">https://example.com/about</data>
      <data key="status">200</data>
      <data key="depth">1</data>
    </node>

    <edge source="1" target="2">
      <data key="link_type">hyperlink</data>
      <data key="anchor_text">About Us</data>
    </edge>
  </graph>
</graphml>
```

### Использование в Gephi

1. Открыть Gephi
2. File → Open → выбрать graph.graphml
3. Выбрать layout (ForceAtlas2, Fruchterman Reingold)
4. Настроить размер узлов по depth
5. Настроить цвет по status_code
6. Экспортировать визуализацию

## SQLite экспорт

### Полная база данных

```bash
# Экспорт всей БД
crawler export --session-id abc123 --format sqlite --output export.db

# Копирование одной сессии
crawler export --session-id abc123 --format sqlite --output session.db --single-session
```

Удобно для:
- SQL анализа
- Импорта в другие системы
- Архивирования

### SQL анализ

```sql
-- Top 10 самых больших страниц
SELECT url, size_bytes, title
FROM crawled_urls
WHERE session_id = 'abc123'
ORDER BY size_bytes DESC
LIMIT 10;

-- Распределение статус кодов
SELECT status_code, COUNT(*) as count
FROM crawled_urls
WHERE session_id = 'abc123'
GROUP BY status_code
ORDER BY count DESC;

-- Средняя скорость ответа по глубине
SELECT depth, AVG(response_time) as avg_time, COUNT(*) as count
FROM crawled_urls
WHERE session_id = 'abc123'
GROUP BY depth
ORDER BY depth;

-- Внешние ссылки
SELECT target_url, COUNT(*) as count
FROM crawled_links
WHERE session_id = 'abc123'
  AND link_type = 'external'
GROUP BY target_url
ORDER BY count DESC
LIMIT 20;
```

## Программный экспорт

### Кастомный экспортер

```python
from webcrawler.export.base import BaseExporter
from webcrawler.storage.repository import CrawlSessionRepository, URLRepository

class CustomExporter(BaseExporter):
    """Кастомный экспортер"""

    async def export(
        self,
        session_id: str,
        output_path: str,
        **options
    ) -> None:
        """Экспорт в кастомный формат"""

        async with self.db_manager.session() as db_session:
            # Repositories
            session_repo = CrawlSessionRepository(db_session)
            url_repo = URLRepository(db_session)

            # Получить данные
            session = await session_repo.get_by_session_id(session_id)
            urls = await url_repo.get_all_by_session(session_id)

            # Кастомная обработка
            data = self._process_data(session, urls)

            # Сохранение
            await self._save(output_path, data)

    def _process_data(self, session, urls):
        """Обработка данных"""
        # Ваша логика
        return processed_data

    async def _save(self, path, data):
        """Сохранение"""
        # Ваша логика
        pass


# Использование
exporter = CustomExporter(db_manager)
await exporter.export("abc123", "output.custom")
```

### Streaming экспорт

Для больших экспортов используйте streaming:

```python
from webcrawler.export import StreamingJSONExporter

exporter = StreamingJSONExporter(db_manager)

async with exporter.stream(session_id="abc123") as stream:
    async for batch in stream.batches(batch_size=1000):
        # Обработка батча
        await process_batch(batch)

        # Или запись в файл
        await stream.write_batch(batch, file_handle)
```

## Автоматический экспорт

### После завершения краулинга

```yaml
export:
  # Автоэкспорт по завершению
  auto_export: true

  # Форматы для автоэкспорта
  auto_export_formats:
    - "json"
    - "html"

  # Директория
  output_dir: "exports/"

  # Именование файлов
  filename_template: "{session_id}_{format}_{timestamp}"
```

### Scheduled экспорт

```yaml
export:
  # Планирование экспортов
  scheduled:
    enabled: true

    # Расписание (cron format)
    schedule: "0 2 * * *"  # Каждый день в 2:00

    # Форматы
    formats: ["json", "sqlite"]

    # Retention
    keep_last: 30
```

## Фильтрация при экспорте

### По статусу

```bash
# Только успешные URL
crawler export --session-id abc123 --format json \
  --filter-status completed

# Только ошибки
crawler export --session-id abc123 --format csv \
  --filter-status failed
```

### По глубине

```bash
# Только первые 3 уровня
crawler export --session-id abc123 --format json \
  --max-depth 3
```

### По статус коду

```bash
# Только 404
crawler export --session-id abc123 --format csv \
  --status-codes 404

# Только успешные
crawler export --session-id abc123 --format csv \
  --status-codes 200,201,204
```

### Программная фильтрация

```python
from webcrawler.export import JSONExporter
from webcrawler.export.filters import StatusFilter, DepthFilter

exporter = JSONExporter(db_manager)

# С фильтрами
await exporter.export(
    session_id="abc123",
    output_path="filtered.json",
    filters=[
        StatusFilter(status="completed"),
        DepthFilter(max_depth=3),
    ]
)
```

## Сжатие

### Поддерживаемые форматы

```bash
# Gzip
crawler export --session-id abc123 --format json \
  --output results.json.gz --compress gzip

# Zip
crawler export --session-id abc123 --format json \
  --output results.zip --compress zip

# Bzip2
crawler export --session-id abc123 --format json \
  --output results.json.bz2 --compress bzip2
```

### Автоматическое сжатие

```yaml
export:
  # Сжимать большие экспорты
  auto_compress: true

  # Порог размера для сжатия (MB)
  compress_threshold: 10

  # Формат сжатия
  compression_format: "gzip"

  # Уровень сжатия (1-9)
  compression_level: 6
```

## Best Practices

1. **JSON для программной обработки** - легко парсить
2. **CSV для Excel** - быстрый просмотр данных
3. **HTML для презентаций** - интерактивные отчёты
4. **PDF для архивирования** - неизменяемые отчёты
5. **GraphML для анализа структуры** - визуализация графов
6. **SQLite для больших данных** - SQL анализ

7. **Используйте сжатие** для экспортов >10 MB
8. **Фильтруйте данные** перед экспортом больших сессий
9. **Streaming для огромных экспортов** (>1M URLs)
10. **Автоэкспорт** для регулярных краулингов

## Следующие шаги

- [Конфигурация](configuration.md)
- [Базовое использование](basic_usage.md)
- [Мониторинг](monitoring.md)
