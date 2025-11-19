# JavaScript рендеринг

Руководство по краулингу современных SPA (Single Page Applications) и динамических сайтов с использованием headless browser.

## Обзор

Многие современные веб-сайты используют JavaScript для динамической генерации контента. Обычные HTTP запросы получают только начальный HTML, который не содержит основной контент. Для таких сайтов требуется полноценный браузер.

### Когда нужен JavaScript рендеринг

✅ **Использовать:**
- SPA приложения (React, Vue, Angular)
- Контент, загружаемый через AJAX
- Бесконечная прокрутка (infinite scroll)
- Динамические формы и модальные окна
- Сайты с ленивой загрузкой изображений

❌ **Не нужен:**
- Статические HTML сайты
- Server-side rendered сайты
- Традиционные CMS (WordPress, Drupal)
- API endpoints

### Технология

Enterprise Web Crawler использует **Playwright** - современный фреймворк для автоматизации браузеров от Microsoft.

**Преимущества Playwright:**
- Поддержка Chromium, Firefox, WebKit
- Полная асинхронность (async/await)
- Автоматическое ожидание элементов
- Перехват сетевых запросов
- Эмуляция мобильных устройств
- Скриншоты и PDF

## Базовое использование

### Включение JavaScript рендеринга

```yaml
# config.yaml
crawler:
  enable_javascript: true
  javascript_timeout: 30
```

```bash
# CLI
crawler crawl https://spa-example.com --javascript
```

```python
# Python API
from webcrawler import Crawler
from webcrawler.utils.config import init_config

config = init_config()
config.crawler.enable_javascript = True

crawler = Crawler(config, db)
session = await crawler.start_crawl("https://spa-example.com")
```

### Автоматическое определение

Crawler может автоматически определять, требуется ли JavaScript:

```yaml
crawler:
  # Автоопределение JavaScript фреймворков
  auto_detect_javascript: true

  # Если обнаружен JS фреймворк, использовать браузер
  auto_enable_javascript: true
```

Детектируемые фреймворки:
- React (проверка `window.React`)
- Vue.js (проверка `window.Vue`)
- Angular (проверка `window.ng`)
- Next.js (мета-теги)
- Nuxt.js (мета-теги)

## Конфигурация браузера

### Выбор браузера

```yaml
javascript:
  # Браузер: chromium, firefox, webkit
  browser: "chromium"

  # Headless режим (без GUI)
  headless: true

  # Аргументы запуска браузера
  browser_args:
    - "--disable-gpu"
    - "--no-sandbox"
    - "--disable-dev-shm-usage"
```

### Производительность

```yaml
javascript:
  # Количество браузерных контекстов (вкладок)
  max_contexts: 10

  # Переиспользование контекстов
  reuse_contexts: true

  # Закрывать контекст после N страниц
  context_max_pages: 100

  # Таймаут загрузки страницы (мс)
  page_load_timeout: 30000

  # Таймаут ожидания селектора (мс)
  wait_timeout: 5000
```

### Блокировка ресурсов

Ускорение загрузки через блокировку ненужных ресурсов:

```yaml
javascript:
  # Блокировать типы ресурсов
  block_resources:
    - "image"      # Изображения
    - "media"      # Видео/аудио
    - "font"       # Шрифты
    - "stylesheet" # CSS (осторожно!)

  # Блокировать домены (реклама, аналитика)
  block_domains:
    - "*.google-analytics.com"
    - "*.doubleclick.net"
    - "*.facebook.net"
    - "*.googletagmanager.com"
```

Пример: блокировка только тяжёлых ресурсов:

```yaml
javascript:
  block_resources:
    - "media"
  block_domains:
    - "*.ads.*"
    - "*.analytics.*"
```

## Ожидание контента

### Стратегии ожидания

```yaml
javascript:
  # Стратегия: load, domcontentloaded, networkidle
  wait_until: "networkidle"

  # Дополнительное ожидание после загрузки (мс)
  wait_after_load: 2000

  # Ожидать конкретный селектор
  wait_for_selector: null

  # Ожидать исчезновения селектора (лоадер)
  wait_for_hidden_selector: ".loading-spinner"
```

#### Стратегии wait_until

**load** - Событие `load` (все ресурсы загружены)
```yaml
wait_until: "load"  # Медленно, но гарантирует полную загрузку
```

**domcontentloaded** - DOM готов, но ресурсы могут загружаться
```yaml
wait_until: "domcontentloaded"  # Быстро, но может пропустить AJAX
```

**networkidle** - Нет сетевой активности 500мс
```yaml
wait_until: "networkidle"  # Оптимально для SPA
```

### Кастомные условия ожидания

```yaml
javascript:
  # Ожидать пока функция вернёт true
  wait_for_function: |
    () => {
      return document.querySelectorAll('.item').length > 0;
    }

  # Таймаут для функции (мс)
  wait_for_function_timeout: 10000
```

Пример: ожидание загрузки React компонента:

```yaml
javascript:
  wait_for_function: |
    () => {
      const root = document.getElementById('root');
      return root && root.children.length > 0;
    }
```

## Прокрутка и динамический контент

### Infinite scroll

Для сайтов с бесконечной прокруткой:

```yaml
javascript:
  # Включить автопрокрутку
  auto_scroll: true

  # Количество прокруток
  scroll_count: 10

  # Задержка между прокрутками (мс)
  scroll_delay: 1000

  # Прокручивать до конца
  scroll_to_end: true
```

Пример реализации:

```python
from webcrawler.core.js_fetcher import JSFetcher

fetcher = JSFetcher(config)

async with fetcher.get_context() as context:
    page = await context.new_page()
    await page.goto(url)

    # Автопрокрутка
    for i in range(10):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1000)

    content = await page.content()
```

### Lazy loading изображений

```yaml
javascript:
  # Прокручивать для загрузки lazy images
  trigger_lazy_loading: true

  # Задержка после прокрутки (мс)
  lazy_load_wait: 500
```

## Взаимодействие со страницей

### Клики и навигация

```yaml
javascript:
  # Кликать кнопки "Показать ещё"
  click_selectors:
    - "button.load-more"
    - "a.show-more"

  # Максимум кликов
  max_clicks: 5

  # Задержка между кликами (мс)
  click_delay: 1000
```

### Заполнение форм

Для сайтов с защитой от ботов:

```yaml
javascript:
  # Эмулировать движения мыши
  emulate_mouse: true

  # Эмулировать ввод с клавиатуры
  emulate_keyboard: true

  # Задержка между действиями (мс)
  action_delay: 100
```

## Эмуляция устройств

### Мобильные устройства

```yaml
javascript:
  # Эмулировать устройство
  device_emulation:
    enabled: true

    # Устройство: iPhone 12, Pixel 5, iPad Pro
    device: "iPhone 12"

    # Или кастомные настройки
    custom:
      viewport:
        width: 375
        height: 812
      user_agent: "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0)"
      device_scale_factor: 3
      is_mobile: true
      has_touch: true
```

### Geolocation

```yaml
javascript:
  # Эмуляция местоположения
  geolocation:
    enabled: true
    latitude: 37.7749
    longitude: -122.4194
    accuracy: 100
```

### Locale и timezone

```yaml
javascript:
  # Локаль
  locale: "ru-RU"

  # Часовой пояс
  timezone: "Europe/Moscow"

  # Разрешения
  permissions:
    - "geolocation"
    - "notifications"
```

## Перехват сетевых запросов

### Мониторинг XHR/Fetch

```yaml
javascript:
  # Перехватывать сетевые запросы
  intercept_requests: true

  # Логировать все запросы
  log_requests: true

  # Извлекать данные из API responses
  extract_api_data: true
```

Программный перехват:

```python
async def intercept_route(route, request):
    # Блокировать рекламу
    if "ads" in request.url:
        await route.abort()
    # Модифицировать заголовки
    elif "api" in request.url:
        headers = {**request.headers, "X-Custom": "value"}
        await route.continue_(headers=headers)
    else:
        await route.continue_()

page.route("**/*", intercept_route)
```

### Извлечение AJAX данных

```yaml
javascript:
  # Паттерны URL для перехвата
  api_patterns:
    - "*/api/*"
    - "*/graphql"
    - "*.json"

  # Сохранять responses
  save_api_responses: true
```

## Скриншоты и PDF

### Скриншоты страниц

```yaml
javascript:
  # Делать скриншоты
  take_screenshots: true

  # Директория для скриншотов
  screenshot_dir: "screenshots/"

  # Формат: png, jpeg
  screenshot_format: "png"

  # Полная страница или viewport
  full_page: true

  # Качество для JPEG (1-100)
  screenshot_quality: 80
```

Программное создание скриншотов:

```python
# Скриншот всей страницы
await page.screenshot(
    path="screenshot.png",
    full_page=True
)

# Скриншот элемента
element = await page.query_selector(".main-content")
await element.screenshot(path="element.png")
```

### Генерация PDF

```yaml
javascript:
  # Генерировать PDF
  generate_pdf: false

  # Директория для PDF
  pdf_dir: "pdfs/"

  # Формат страницы
  pdf_format: "A4"

  # Ориентация: portrait, landscape
  pdf_orientation: "portrait"

  # Включить фон
  print_background: true
```

## Обход защиты от ботов

### Стелс режим

```yaml
javascript:
  # Стелс режим (скрывать автоматизацию)
  stealth_mode: true

  # Модифицировать navigator.webdriver
  hide_webdriver: true

  # Рандомизация User-Agent
  randomize_user_agent: true

  # Рандомизация viewport
  randomize_viewport: true
```

### Задержки и рандомизация

```yaml
javascript:
  # Случайная задержка перед действиями (мс)
  random_delay_min: 500
  random_delay_max: 2000

  # Эмулировать человеческое поведение
  human_behavior: true
```

### Cookies и сессии

```yaml
javascript:
  # Сохранять cookies между запросами
  persist_cookies: true

  # Файл для cookies
  cookies_file: "cookies.json"

  # Сохранять localStorage
  persist_local_storage: true
```

Программная работа с cookies:

```python
# Установить cookies
await context.add_cookies([
    {
        "name": "session",
        "value": "abc123",
        "domain": "example.com",
        "path": "/"
    }
])

# Получить cookies
cookies = await context.cookies()

# Сохранить cookies
import json
with open("cookies.json", "w") as f:
    json.dump(cookies, f)
```

## Отладка

### Режим отладки

```yaml
javascript:
  # Headless = false для визуальной отладки
  headless: false

  # Замедление выполнения (мс)
  slow_mo: 1000

  # DevTools автоматически
  devtools: true
```

### Логирование браузера

```yaml
javascript:
  # Логировать console.log из браузера
  log_console: true

  # Логировать errors из браузера
  log_errors: true

  # Сохранять HAR (HTTP Archive)
  save_har: true
  har_dir: "har/"
```

Программное логирование:

```python
# Перехват console.log
page.on("console", lambda msg: print(f"Browser: {msg.text}"))

# Перехват ошибок JavaScript
page.on("pageerror", lambda err: print(f"JS Error: {err}"))

# Перехват падений
page.on("crash", lambda: print("Page crashed"))
```

## Производительность

### Оптимизация памяти

```yaml
javascript:
  # Лимит памяти на контекст (MB)
  memory_limit: 512

  # Закрывать неиспользуемые вкладки
  close_idle_pages: true

  # Таймаут idle (секунды)
  idle_timeout: 60
```

### Параллелизм

```yaml
javascript:
  # Количество браузеров
  max_browsers: 2

  # Контекстов на браузер
  contexts_per_browser: 10

  # Страниц на контекст
  pages_per_context: 1
```

### Кеширование

```yaml
javascript:
  # Включить кеш браузера
  enable_cache: true

  # Директория кеша
  cache_dir: "cache/browser/"

  # Размер кеша (MB)
  cache_size: 1000
```

## Примеры использования

### React SPA

```yaml
crawler:
  start_urls:
    - "https://react-spa.example.com"
  enable_javascript: true

javascript:
  browser: "chromium"
  headless: true
  wait_until: "networkidle"
  wait_for_selector: "#root"
  block_resources:
    - "media"
  stealth_mode: true
```

### Infinite scroll блог

```yaml
crawler:
  start_urls:
    - "https://blog.example.com"
  enable_javascript: true

javascript:
  browser: "chromium"
  auto_scroll: true
  scroll_count: 20
  scroll_delay: 1000
  trigger_lazy_loading: true
  take_screenshots: false
```

### E-commerce с защитой

```yaml
crawler:
  start_urls:
    - "https://shop.example.com"
  enable_javascript: true

javascript:
  browser: "chromium"
  headless: true
  stealth_mode: true
  hide_webdriver: true
  human_behavior: true
  random_delay_min: 1000
  random_delay_max: 3000
  persist_cookies: true
  device_emulation:
    enabled: true
    device: "Desktop Chrome"
```

## Troubleshooting

### Проблема: Страница не загружается

```yaml
javascript:
  # Увеличить таймаут
  page_load_timeout: 60000

  # Изменить стратегию
  wait_until: "domcontentloaded"
```

### Проблема: Контент не появляется

```yaml
javascript:
  # Добавить ожидание после загрузки
  wait_after_load: 5000

  # Ожидать конкретный элемент
  wait_for_selector: ".content"
```

### Проблема: Blocked by bot protection

```yaml
javascript:
  # Включить стелс
  stealth_mode: true
  hide_webdriver: true

  # Эмулировать реальное устройство
  device_emulation:
    enabled: true
    device: "Desktop Chrome"

  # Задержки
  random_delay_min: 2000
  random_delay_max: 5000
```

### Проблема: Утечка памяти

```yaml
javascript:
  # Ограничить переиспользование
  context_max_pages: 50

  # Закрывать idle pages
  close_idle_pages: true
  idle_timeout: 30

  # Лимит памяти
  memory_limit: 512
```

## Best Practices

1. **Используйте JS только когда нужно** - проверьте, можно ли получить данные без браузера
2. **Блокируйте ненужные ресурсы** - ускорит загрузку на 50-70%
3. **Оптимизируйте ожидание** - не используйте фиксированные задержки, используйте `wait_for_selector`
4. **Переиспользуйте контексты** - создание нового браузера медленное
5. **Мониторьте память** - браузеры потребляют много RAM
6. **Стелс для защищённых сайтов** - многие сайты детектируют Playwright
7. **Логируйте всё в dev** - помогает понять что происходит

## Следующие шаги

- [Распределённый краулинг](distributed_crawling.md)
- [Конфигурация](configuration.md)
- [Экспорт данных](export_formats.md)
