"""
JavaScript-enabled fetcher для рендеринга динамического контента.

Использует Playwright для загрузки и рендеринга страниц с JavaScript.
Необходим для современных SPA и динамических сайтов.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

from webcrawler.core.fetcher import FetchResult
from webcrawler.utils.config import Config
from webcrawler.utils.logger import LoggerMixin
from webcrawler.utils.rate_limiter import RateLimiter


@dataclass
class JavaScriptFetchResult(FetchResult):
    """
    Результат загрузки страницы с JavaScript рендерингом.

    Расширяет базовый FetchResult дополнительными полями.
    """

    # Screenshot (опционально)
    screenshot: Optional[bytes] = None

    # Console logs
    console_logs: list[str] = None

    # JavaScript errors
    js_errors: list[str] = None

    def __post_init__(self):
        """Инициализация списков."""
        if self.console_logs is None:
            self.console_logs = []
        if self.js_errors is None:
            self.js_errors = []


class JavaScriptFetcher(LoggerMixin):
    """
    Fetcher с поддержкой JavaScript через Playwright.

    Загружает страницы в headless browser, ожидает выполнения JavaScript,
    извлекает финальный отрендеренный HTML.

    Используется для:
    - Single Page Applications (SPA)
    - Динамический контент
    - AJAX загрузки
    - React/Vue/Angular приложения

    Example:
        >>> config = Config.from_yaml("config.yaml")
        >>> rate_limiter = RateLimiter()
        >>> fetcher = JavaScriptFetcher(config, rate_limiter)
        >>> await fetcher.start()
        >>> result = await fetcher.fetch("https://spa-example.com")
        >>> print(result.content)  # Полный отрендеренный HTML
        >>> await fetcher.close()
    """

    def __init__(
        self,
        config: Config,
        rate_limiter: RateLimiter,
        browser_type: str = "chromium",
    ):
        """
        Инициализация JavaScript fetcher.

        Args:
            config: Объект конфигурации
            rate_limiter: Rate limiter для контроля запросов
            browser_type: Тип браузера (chromium, firefox, webkit)
        """
        self.config = config
        self.rate_limiter = rate_limiter
        self.browser_type = browser_type

        # Playwright компоненты
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

        # Настройки
        self.timeout = config.crawler.javascript_timeout * 1000  # в миллисекундах
        self.wait_until = config.crawler.javascript_wait_until  # load, domcontentloaded, networkidle
        self.enable_screenshots = config.crawler.javascript_screenshots

        self.logger.info(
            "js_fetcher_initialized",
            browser_type=browser_type,
            timeout=self.timeout,
            wait_until=self.wait_until,
        )

    async def start(self) -> None:
        """
        Запустить браузер и создать контекст.

        Должен вызываться перед использованием fetcher.

        Example:
            >>> await fetcher.start()
        """
        self.logger.info("starting_playwright_browser", browser_type=self.browser_type)

        try:
            # Запуск Playwright
            self.playwright = await async_playwright().start()

            # Выбор браузера
            if self.browser_type == "chromium":
                browser_launcher = self.playwright.chromium
            elif self.browser_type == "firefox":
                browser_launcher = self.playwright.firefox
            elif self.browser_type == "webkit":
                browser_launcher = self.playwright.webkit
            else:
                raise ValueError(f"Unknown browser type: {self.browser_type}")

            # Параметры браузера
            browser_args = {
                "headless": True,  # Headless mode
            }

            # Proxy настройки
            if self.config.proxy.enabled:
                proxy_url = self.config.get_proxy_url()
                if proxy_url:
                    from urllib.parse import urlparse

                    parsed = urlparse(proxy_url)
                    browser_args["proxy"] = {
                        "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
                    }
                    if parsed.username:
                        browser_args["proxy"]["username"] = parsed.username
                    if parsed.password:
                        browser_args["proxy"]["password"] = parsed.password

            # Запуск браузера
            self.browser = await browser_launcher.launch(**browser_args)

            # Создание контекста
            context_args = {
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": self.config.robots.custom_user_agent,
                "java_script_enabled": True,
                "ignore_https_errors": True,  # Игнорировать SSL ошибки
            }

            self.context = await self.browser.new_context(**context_args)

            # Настройка timeout по умолчанию
            self.context.set_default_timeout(self.timeout)

            self.logger.info(
                "playwright_browser_started",
                browser_type=self.browser_type,
                headless=True,
            )

        except Exception as e:
            self.logger.error(
                "playwright_browser_start_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    async def fetch(
        self, url: str, wait_for_selector: Optional[str] = None
    ) -> JavaScriptFetchResult:
        """
        Загрузить страницу с JavaScript рендерингом.

        Args:
            url: URL для загрузки
            wait_for_selector: CSS селектор для ожидания (опционально)

        Returns:
            JavaScriptFetchResult: Результат с отрендеренным HTML

        Raises:
            RuntimeError: Если браузер не запущен
            PlaywrightTimeoutError: При превышении timeout
            Exception: При других ошибках загрузки

        Example:
            >>> result = await fetcher.fetch(
            ...     "https://example.com",
            ...     wait_for_selector=".dynamic-content"
            ... )
            >>> print(f"Status: {result.status_code}")
            >>> print(f"HTML length: {len(result.content)}")
        """
        if not self.browser or not self.context:
            raise RuntimeError("Browser not started. Call start() first.")

        # Rate limiting
        async with self.rate_limiter.acquire(url):
            page: Optional[Page] = None

            try:
                import time

                start_time = time.time()

                # Создание новой страницы
                page = await self.context.new_page()

                # Сбор console logs и errors
                console_logs = []
                js_errors = []

                # Слушатели событий
                page.on(
                    "console",
                    lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"),
                )
                page.on(
                    "pageerror",
                    lambda error: js_errors.append(str(error)),
                )

                # Загрузка страницы
                self.logger.debug(
                    "loading_page_with_js", url=url, wait_until=self.wait_until
                )

                response = await page.goto(url, wait_until=self.wait_until)

                # Ожидание селектора (если указан)
                if wait_for_selector:
                    try:
                        await page.wait_for_selector(
                            wait_for_selector, timeout=self.timeout
                        )
                    except PlaywrightTimeoutError:
                        self.logger.warning(
                            "selector_wait_timeout",
                            url=url,
                            selector=wait_for_selector,
                        )

                # Дополнительное ожидание для AJAX запросов
                if self.config.crawler.javascript_wait_for_ajax:
                    await asyncio.sleep(1)  # 1 секунда для завершения AJAX

                # Извлечение финального HTML
                content = await page.content()

                # Screenshot (если включено)
                screenshot = None
                if self.enable_screenshots:
                    try:
                        screenshot = await page.screenshot(full_page=False)
                    except Exception as e:
                        self.logger.warning("screenshot_failed", url=url, error=str(e))

                # Время загрузки
                response_time = time.time() - start_time

                # Извлечение заголовков
                headers = {}
                if response:
                    headers = response.headers

                # Статус код
                status_code = response.status if response else 200

                # Извлечение URL (может измениться после редиректов)
                final_url = page.url

                self.logger.info(
                    "page_loaded_with_js",
                    url=url,
                    final_url=final_url,
                    status_code=status_code,
                    response_time=f"{response_time:.3f}s",
                    console_logs_count=len(console_logs),
                    js_errors_count=len(js_errors),
                )

                # Создание результата
                return JavaScriptFetchResult(
                    url=final_url,
                    status_code=status_code,
                    content=content.encode("utf-8"),
                    headers=headers,
                    response_time=response_time,
                    redirect_chain=[],  # Playwright не предоставляет redirect chain
                    ssl_info=None,  # TODO: можно извлечь из page.evaluate
                    screenshot=screenshot,
                    console_logs=console_logs,
                    js_errors=js_errors,
                )

            except PlaywrightTimeoutError as e:
                self.logger.warning(
                    "js_fetch_timeout", url=url, timeout=self.timeout / 1000
                )
                raise TimeoutError(f"JavaScript fetch timeout for {url}") from e

            except Exception as e:
                self.logger.error(
                    "js_fetch_failed",
                    url=url,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise

            finally:
                # Закрытие страницы
                if page:
                    await page.close()

    async def fetch_with_interaction(
        self,
        url: str,
        interactions: list[dict],
    ) -> JavaScriptFetchResult:
        """
        Загрузить страницу с пользовательскими взаимодействиями.

        Позволяет выполнять клики, скроллинг, ввод текста перед
        извлечением финального HTML.

        Args:
            url: URL для загрузки
            interactions: Список действий (click, scroll, type, wait)

        Returns:
            JavaScriptFetchResult: Результат после взаимодействий

        Example:
            >>> interactions = [
            ...     {"action": "click", "selector": "button.load-more"},
            ...     {"action": "wait", "timeout": 2000},
            ...     {"action": "scroll", "pixels": 1000},
            ... ]
            >>> result = await fetcher.fetch_with_interaction(url, interactions)
        """
        if not self.browser or not self.context:
            raise RuntimeError("Browser not started. Call start() first.")

        async with self.rate_limiter.acquire(url):
            page: Optional[Page] = None

            try:
                import time

                start_time = time.time()

                page = await self.context.new_page()

                # Загрузка страницы
                response = await page.goto(url, wait_until=self.wait_until)

                # Выполнение взаимодействий
                for interaction in interactions:
                    action = interaction.get("action")

                    if action == "click":
                        selector = interaction.get("selector")
                        await page.click(selector)
                        self.logger.debug("interaction_click", selector=selector)

                    elif action == "type":
                        selector = interaction.get("selector")
                        text = interaction.get("text", "")
                        await page.fill(selector, text)
                        self.logger.debug("interaction_type", selector=selector)

                    elif action == "scroll":
                        pixels = interaction.get("pixels", 0)
                        await page.evaluate(f"window.scrollBy(0, {pixels})")
                        self.logger.debug("interaction_scroll", pixels=pixels)

                    elif action == "wait":
                        timeout = interaction.get("timeout", 1000)
                        await asyncio.sleep(timeout / 1000)
                        self.logger.debug("interaction_wait", timeout=timeout)

                    elif action == "wait_for_selector":
                        selector = interaction.get("selector")
                        await page.wait_for_selector(selector)
                        self.logger.debug(
                            "interaction_wait_for_selector", selector=selector
                        )

                # Извлечение контента
                content = await page.content()
                response_time = time.time() - start_time

                return JavaScriptFetchResult(
                    url=page.url,
                    status_code=response.status if response else 200,
                    content=content.encode("utf-8"),
                    headers=response.headers if response else {},
                    response_time=response_time,
                    redirect_chain=[],
                    ssl_info=None,
                )

            except Exception as e:
                self.logger.error(
                    "js_fetch_with_interaction_failed",
                    url=url,
                    error=str(e),
                )
                raise

            finally:
                if page:
                    await page.close()

    async def execute_script(
        self, url: str, script: str
    ) -> tuple[JavaScriptFetchResult, any]:
        """
        Загрузить страницу и выполнить JavaScript код.

        Args:
            url: URL для загрузки
            script: JavaScript код для выполнения

        Returns:
            tuple: (JavaScriptFetchResult, результат выполнения скрипта)

        Example:
            >>> script = "return document.querySelectorAll('a').length"
            >>> result, link_count = await fetcher.execute_script(url, script)
            >>> print(f"Found {link_count} links")
        """
        if not self.browser or not self.context:
            raise RuntimeError("Browser not started. Call start() first.")

        async with self.rate_limiter.acquire(url):
            page: Optional[Page] = None

            try:
                import time

                start_time = time.time()

                page = await self.context.new_page()

                # Загрузка страницы
                response = await page.goto(url, wait_until=self.wait_until)

                # Выполнение скрипта
                script_result = await page.evaluate(script)

                # Извлечение контента
                content = await page.content()
                response_time = time.time() - start_time

                fetch_result = JavaScriptFetchResult(
                    url=page.url,
                    status_code=response.status if response else 200,
                    content=content.encode("utf-8"),
                    headers=response.headers if response else {},
                    response_time=response_time,
                    redirect_chain=[],
                    ssl_info=None,
                )

                return fetch_result, script_result

            except Exception as e:
                self.logger.error(
                    "js_execute_script_failed",
                    url=url,
                    error=str(e),
                )
                raise

            finally:
                if page:
                    await page.close()

    async def get_page_metrics(self, url: str) -> dict:
        """
        Получить метрики производительности страницы.

        Args:
            url: URL для загрузки

        Returns:
            dict: Метрики (load time, resources count, etc.)

        Example:
            >>> metrics = await fetcher.get_page_metrics("https://example.com")
            >>> print(f"Load time: {metrics['load_time']}s")
        """
        if not self.browser or not self.context:
            raise RuntimeError("Browser not started. Call start() first.")

        async with self.rate_limiter.acquire(url):
            page: Optional[Page] = None

            try:
                import time

                start_time = time.time()

                page = await self.context.new_page()

                # Загрузка страницы
                await page.goto(url, wait_until="networkidle")

                load_time = time.time() - start_time

                # Извлечение метрик через JavaScript
                metrics = await page.evaluate(
                    """
                    () => {
                        const performance = window.performance;
                        const timing = performance.timing;
                        const navigation = performance.navigation;

                        return {
                            loadTime: timing.loadEventEnd - timing.navigationStart,
                            domContentLoaded: timing.domContentLoadedEventEnd - timing.navigationStart,
                            firstPaint: performance.getEntriesByType('paint')[0]?.startTime || 0,
                            resourcesCount: performance.getEntriesByType('resource').length,
                            navigationTime: timing.responseEnd - timing.navigationStart,
                            renderTime: timing.domComplete - timing.domLoading,
                        }
                    }
                """
                )

                metrics["total_load_time"] = load_time

                return metrics

            except Exception as e:
                self.logger.error(
                    "get_page_metrics_failed",
                    url=url,
                    error=str(e),
                )
                raise

            finally:
                if page:
                    await page.close()

    async def close(self) -> None:
        """
        Закрыть браузер и освободить ресурсы.

        Должен вызываться при завершении работы.

        Example:
            >>> await fetcher.close()
        """
        self.logger.info("closing_playwright_browser")

        try:
            if self.context:
                await self.context.close()
                self.context = None

            if self.browser:
                await self.browser.close()
                self.browser = None

            if self.playwright:
                await self.playwright.stop()
                self.playwright = None

            self.logger.info("playwright_browser_closed")

        except Exception as e:
            self.logger.error("playwright_browser_close_failed", error=str(e))

    async def __aenter__(self):
        """Context manager вход."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager выход."""
        await self.close()


class HybridFetcher(LoggerMixin):
    """
    Гибридный fetcher: использует HTTP для обычных страниц,
    JavaScript для SPA и динамического контента.

    Автоматически определяет какой fetcher использовать на основе
    Content-Type и настроек конфигурации.

    Example:
        >>> hybrid = HybridFetcher(config, rate_limiter)
        >>> await hybrid.start()
        >>> result = await hybrid.fetch("https://example.com")
        >>> # Автоматически выбирает HTTP или JS fetcher
        >>> await hybrid.close()
    """

    def __init__(
        self,
        config: Config,
        rate_limiter: RateLimiter,
        http_fetcher,
        js_fetcher: Optional[JavaScriptFetcher] = None,
    ):
        """
        Инициализация гибридного fetcher.

        Args:
            config: Конфигурация
            rate_limiter: Rate limiter
            http_fetcher: HTTP fetcher (HTTPFetcher)
            js_fetcher: JavaScript fetcher (опционально)
        """
        self.config = config
        self.rate_limiter = rate_limiter
        self.http_fetcher = http_fetcher
        self.js_fetcher = js_fetcher

        # Счётчики использования
        self.http_fetch_count = 0
        self.js_fetch_count = 0

    async def start(self) -> None:
        """Запустить оба fetcher."""
        if self.js_fetcher and self.config.crawler.enable_javascript:
            await self.js_fetcher.start()

    async def fetch(
        self, url: str, force_javascript: bool = False
    ) -> FetchResult | JavaScriptFetchResult:
        """
        Загрузить страницу автоматически выбрав fetcher.

        Args:
            url: URL для загрузки
            force_javascript: Принудительно использовать JS fetcher

        Returns:
            FetchResult: Результат загрузки
        """
        # Если JS отключен или fetcher не инициализирован, используем HTTP
        if (
            not self.config.crawler.enable_javascript
            or not self.js_fetcher
            or not force_javascript
        ):
            self.http_fetch_count += 1
            return await self.http_fetcher.fetch(url)

        # Используем JavaScript fetcher
        self.js_fetch_count += 1
        return await self.js_fetcher.fetch(url)

    async def close(self) -> None:
        """Закрыть оба fetcher."""
        if self.js_fetcher:
            await self.js_fetcher.close()

        self.logger.info(
            "hybrid_fetcher_stats",
            http_fetches=self.http_fetch_count,
            js_fetches=self.js_fetch_count,
        )
