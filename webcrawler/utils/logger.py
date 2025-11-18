"""
Модуль для настройки структурированного логирования.

Использует structlog для производительного и гибкого логирования
с поддержкой разных форматов и ротации логов.
"""

import logging
import sys
from pathlib import Path
from typing import Any

import structlog
from pythonjsonlogger import jsonlogger


def setup_logging(
    level: str = "INFO",
    log_file: str | None = None,
    log_format: str = "detailed",
    console: bool = True,
    colorize: bool = True,
) -> None:
    """
    Настроить систему логирования для приложения.

    Args:
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Путь к файлу логов (опционально)
        log_format: Формат логов ('detailed', 'json', 'simple')
        console: Выводить логи в консоль
        colorize: Цветной вывод в консоли

    Example:
        >>> setup_logging(level="DEBUG", log_file="crawler.log", colorize=True)
        >>> logger = get_logger("webcrawler")
        >>> logger.info("crawler_started", url="https://example.com")
    """
    # Преобразуем строковый уровень в numeric
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Настройка процессоров structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Добавляем процессор в зависимости от формата
    if log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    elif console and colorize:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=False))

    # Конфигурация structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Настройка стандартного logging
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Очищаем существующие handlers
    root_logger.handlers.clear()

    # Handler для консоли
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)

        if log_format == "json":
            console_formatter = jsonlogger.JsonFormatter(
                "%(asctime)s %(name)s %(levelname)s %(message)s"
            )
        elif log_format == "simple":
            console_formatter = logging.Formatter(
                "%(levelname)s: %(message)s"
            )
        else:  # detailed
            console_formatter = logging.Formatter(
                "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )

        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # Handler для файла
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(numeric_level)

        if log_format == "json":
            file_formatter = jsonlogger.JsonFormatter(
                "%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d"
            )
        else:
            file_formatter = logging.Formatter(
                "%(asctime)s | %(name)-20s | %(levelname)-8s | %(pathname)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )

        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Настраиваем уровни для внешних библиотек
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Получить логгер для модуля.

    Args:
        name: Имя логгера (обычно __name__ модуля)

    Returns:
        BoundLogger: Настроенный structlog логгер

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("processing_page", url="https://example.com", status=200)
        >>> logger.error("failed_to_fetch", url="https://error.com", error="timeout")
    """
    if name is None:
        name = "webcrawler"
    return structlog.get_logger(name)


class LoggerMixin:
    """
    Mixin для добавления логгера в классы.

    Автоматически создаёт логгер с именем класса.

    Example:
        >>> class MyCrawler(LoggerMixin):
        ...     def crawl(self, url: str):
        ...         self.logger.info("crawling", url=url)
        ...
        >>> crawler = MyCrawler()
        >>> crawler.crawl("https://example.com")
    """

    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """Получить логгер для текущего класса."""
        class_name = f"{self.__class__.__module__}.{self.__class__.__name__}"
        return get_logger(class_name)


def log_function_call(func):
    """
    Декоратор для логирования вызовов функций.

    Логирует входные параметры и результат выполнения функции.

    Args:
        func: Функция для декорирования

    Example:
        >>> @log_function_call
        ... def fetch_page(url: str) -> int:
        ...     return 200
        ...
        >>> status = fetch_page("https://example.com")
        # Логирует: function_called, function=fetch_page, args, kwargs, result
    """
    import functools
    import inspect

    logger = get_logger(func.__module__)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Получаем имена аргументов
        sig = inspect.signature(func)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()

        logger.debug(
            "function_called",
            function=func.__name__,
            arguments=dict(bound_args.arguments)
        )

        try:
            result = func(*args, **kwargs)
            logger.debug(
                "function_completed",
                function=func.__name__,
                result_type=type(result).__name__
            )
            return result
        except Exception as e:
            logger.error(
                "function_failed",
                function=func.__name__,
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        # Получаем имена аргументов
        sig = inspect.signature(func)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()

        logger.debug(
            "async_function_called",
            function=func.__name__,
            arguments=dict(bound_args.arguments)
        )

        try:
            result = await func(*args, **kwargs)
            logger.debug(
                "async_function_completed",
                function=func.__name__,
                result_type=type(result).__name__
            )
            return result
        except Exception as e:
            logger.error(
                "async_function_failed",
                function=func.__name__,
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    # Возвращаем соответствующую обёртку
    if inspect.iscoroutinefunction(func):
        return async_wrapper
    else:
        return wrapper


class ContextLogger:
    """
    Контекстный менеджер для логирования операций.

    Автоматически логирует начало и конец операции,
    а также любые исключения.

    Example:
        >>> logger = get_logger(__name__)
        >>> with ContextLogger(logger, "fetching_url", url="https://example.com"):
        ...     # выполняем операцию
        ...     response = fetch(url)
        # Автоматически логирует: operation_started, operation_completed или operation_failed
    """

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger,
        operation: str,
        **context: Any
    ):
        """
        Инициализация контекстного логгера.

        Args:
            logger: Логгер для использования
            operation: Название операции
            **context: Дополнительный контекст для логирования
        """
        self.logger = logger
        self.operation = operation
        self.context = context

    def __enter__(self):
        """Начало операции."""
        self.logger.info("operation_started", operation=self.operation, **self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Завершение операции."""
        if exc_type is None:
            self.logger.info("operation_completed", operation=self.operation, **self.context)
        else:
            self.logger.error(
                "operation_failed",
                operation=self.operation,
                error=str(exc_val),
                error_type=exc_type.__name__,
                **self.context
            )
        return False  # Не подавляем исключение
