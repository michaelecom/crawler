# Примеры использования Enterprise Web Crawler

Коллекция готовых примеров для различных сценариев использования краулера.

## Структура

```
examples/
├── basic_crawl.py           # Базовый краулинг сайта
├── events_monitoring.py     # Мониторинг событий в реальном времени
├── javascript_spa.py        # Краулинг SPA с JavaScript
├── pause_resume.py          # Pause/Resume функциональность
├── resume_session.py        # Возобновление сессии
├── data_analysis.py         # Анализ результатов
└── README.md                # Этот файл
```

## Примеры

### 1. basic_crawl.py - Базовый краулинг

Минимальный пример для быстрого старта.

```bash
python examples/basic_crawl.py
```

**Что демонстрирует:**
- Инициализация конфигурации и БД
- Запуск краулинга
- Получение статистики
- Graceful shutdown

**Подходит для:**
- Знакомство с API
- Простой краулинг статических сайтов
- Обучение

---

### 2. events_monitoring.py - Мониторинг событий

Отслеживание прогресса краулинга в реальном времени.

```bash
python examples/events_monitoring.py
```

**Что демонстрирует:**
- Подписка на события (page_crawled, error, progress)
- Real-time мониторинг
- Обработка различных типов событий
- Детальная статистика

**Подходит для:**
- Мониторинг больших краулингов
- Debugging
- Логирование прогресса

---

### 3. javascript_spa.py - SPA приложения

Краулинг современных веб-приложений с JavaScript.

```bash
python examples/javascript_spa.py
```

**Что демонстрирует:**
- JavaScript рендеринг (Playwright)
- Конфигурация браузера
- Блокировка ресурсов для ускорения
- Stealth mode
- Автопрокрутка для lazy loading
- Экспорт результатов (JSON, HTML)

**Подходит для:**
- React/Vue/Angular приложения
- SPA сайты
- Динамический контент
- Infinite scroll

---

### 4. pause_resume.py - Приостановка краулинга

Демонстрация pause/resume функциональности.

```bash
python examples/pause_resume.py
```

**Что демонстрирует:**
- Graceful pause по Ctrl+C
- Сохранение состояния
- Signal handling
- Checkpoint механизм

**Подходит для:**
- Длительные краулинги
- Управление ресурсами
- Безопасная остановка

---

### 5. resume_session.py - Возобновление сессии

Продолжение приостановленного краулинга.

```bash
python examples/resume_session.py <session-id>
```

**Что демонстрирует:**
- Загрузка сохранённого состояния
- Продолжение с того же места
- Проверка статуса сессии

**Подходит для:**
- Продолжение после сбоя
- Поэтапный краулинг
- Восстановление после перезапуска

---

### 6. data_analysis.py - Анализ результатов

Детальный анализ данных краулинга.

```bash
python examples/data_analysis.py <session-id>
```

**Что демонстрирует:**
- Использование repositories
- SQL запросы через ORM
- Статистический анализ
- Группировка и агрегация данных

**Показывает:**
- Распределение по глубине
- Статус коды
- Типы контента
- Самые большие/медленные страницы
- Граф ссылок
- Статистика ошибок

**Подходит для:**
- Анализ результатов
- Генерация отчётов
- Поиск проблем
- SEO аудит

---

## Использование

### Подготовка

1. **Установка зависимостей:**

```bash
uv pip install -e ".[dev]"
playwright install chromium
```

2. **Инициализация БД:**

```bash
crawler init-db
```

3. **Настройка конфигурации:**

```bash
cp config/default.yaml config.yaml
# Отредактируйте config.yaml под свои нужды
```

### Запуск примеров

```bash
# Базовый краулинг
python examples/basic_crawl.py

# С мониторингом
python examples/events_monitoring.py

# JavaScript SPA
python examples/javascript_spa.py

# Pause/Resume
python examples/pause_resume.py
# (Нажмите Ctrl+C для паузы)

# Возобновление
crawler sessions  # Получить session-id
python examples/resume_session.py <session-id>

# Анализ
python examples/data_analysis.py <session-id>
```

## Модификация примеров

Все примеры можно легко адаптировать под свои нужды:

### Изменение URL

```python
session = await crawler.start_crawl(
    url="https://your-site.com",  # Ваш URL
    max_depth=3,
    max_pages=1000
)
```

### Настройка конфигурации

```python
config = Config(**{
    "crawler": {
        "max_depth": 5,           # Ваша глубина
        "max_pages": 10000,       # Ваш лимит
        "enable_javascript": True,
    },
    "rate_limiting": {
        "requests_per_second": 10.0,  # Ваша скорость
    },
    # ... другие настройки
})
```

### Добавление event handlers

```python
@session.on_event
def custom_handler(event):
    if event.event_type == "page_crawled":
        # Ваша логика
        process_page(event.url, event.data)
```

## Комбинирование функций

Можно комбинировать функции из разных примеров:

```python
# JavaScript + Events + Pause/Resume
import signal

async def advanced_crawl():
    config = Config(**{
        "crawler": {"enable_javascript": True},
        # ... конфигурация
    })

    crawler = Crawler(config, db)
    session = await crawler.start_crawl(url)

    # Events
    @session.on_event
    def monitor(event):
        if event.event_type == "page_crawled":
            print(f"✓ {event.url}")

    # Signal handling
    paused = False
    def signal_handler(sig, frame):
        nonlocal paused
        paused = True

    signal.signal(signal.SIGINT, signal_handler)

    # Основной цикл
    while not session.is_completed():
        if paused:
            await session.pause()
            break
        await asyncio.sleep(1)

    await db.close()
```

## Troubleshooting

### Проблема: ModuleNotFoundError

```bash
# Установите пакет в editable режиме
uv pip install -e .
```

### Проблема: Ошибка БД

```bash
# Пересоздайте БД
rm -rf webcrawler/data/*.db
crawler init-db
```

### Проблема: Playwright не установлен

```bash
# Установите браузеры
playwright install chromium firefox
playwright install-deps
```

### Проблема: Permission denied

```bash
# Дайте права на выполнение
chmod +x examples/*.py
```

## Best Practices

1. **Всегда используйте try/finally** для cleanup:
   ```python
   try:
       await session.wait_for_completion()
   finally:
       await db.close()
   ```

2. **Обрабатывайте исключения**:
   ```python
   try:
       session = await crawler.start_crawl(url)
   except ValueError as e:
       print(f"Некорректный URL: {e}")
   except Exception as e:
       print(f"Ошибка: {e}")
   ```

3. **Используйте логирование**:
   ```python
   import logging
   logging.basicConfig(level=logging.INFO)
   logger = logging.getLogger(__name__)
   ```

4. **Настройте rate limiting** для вежливого краулинга:
   ```python
   config.rate_limiting.requests_per_second = 2.0
   ```

5. **Сохраняйте session_id** для возможности возобновления:
   ```python
   session_id = session.session_id
   with open("session.txt", "w") as f:
       f.write(session_id)
   ```

## Дополнительные ресурсы

- [Документация](../docs/)
- [API Reference](../docs/api/)
- [Конфигурация](../docs/guides/configuration.md)
- [JavaScript рендеринг](../docs/guides/javascript_rendering.md)
- [Экспорт данных](../docs/guides/export_formats.md)

## Помощь

Если у вас возникли вопросы:

1. Проверьте [документацию](../docs/)
2. Изучите [конфигурацию](../config/default.yaml)
3. Запустите с `--help`:
   ```bash
   crawler --help
   crawler crawl --help
   ```

---

**Лицензия:** MIT
**Автор:** Enterprise Web Crawler Team
