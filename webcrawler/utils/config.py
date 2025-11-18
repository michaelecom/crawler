"""
Модуль для загрузки и управления конфигурацией.

Поддерживает загрузку из YAML файлов и переменных окружения
с валидацией через Pydantic.
"""

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CrawlerConfig(BaseModel):
    """Конфигурация параметров краулера."""

    start_urls: list[str] = Field(default_factory=list, description="Начальные URL для краулинга")
    max_depth: int = Field(default=0, ge=0, description="Максимальная глубина обхода (0 = без ограничений)")
    max_pages: int = Field(default=0, ge=0, description="Максимальное количество страниц (0 = без ограничений)")
    include_subdomains: bool = Field(default=True, description="Включать поддомены")
    restrict_to_domain: bool = Field(default=True, description="Ограничиться одним доменом")
    enable_javascript: bool = Field(default=False, description="Включить JavaScript рендеринг")
    javascript_timeout: int = Field(default=30, gt=0, description="Таймаут JavaScript (секунды)")
    allowed_content_types: list[str] = Field(
        default_factory=lambda: ["text/html", "application/xhtml+xml"],
        description="Разрешённые типы контента"
    )
    max_file_size: int = Field(
        default=104857600,  # 100 MB
        gt=0,
        description="Максимальный размер файла (байты)"
    )

    @field_validator('start_urls')
    @classmethod
    def validate_urls(cls, v: list[str]) -> list[str]:
        """Валидация стартовых URL."""
        if not v:
            raise ValueError("Должен быть указан хотя бы один start_url")
        return v


class RateLimitingConfig(BaseModel):
    """Конфигурация rate limiting."""

    requests_per_second: float = Field(default=5.0, gt=0, description="Запросов в секунду")
    delay_between_requests: int = Field(default=200, ge=0, description="Задержка между запросами (мс)")
    max_concurrent_requests: int = Field(default=100, gt=0, description="Максимум конкурентных запросов")
    request_timeout: int = Field(default=30, gt=0, description="Таймаут запроса (секунды)")
    max_retries: int = Field(default=3, ge=0, description="Количество повторов при ошибке")
    backoff_factor: float = Field(default=2.0, gt=0, description="Фактор экспоненциального backoff")


class RobotsConfig(BaseModel):
    """Конфигурация обработки robots.txt."""

    obey_robots: bool = Field(default=True, description="Учитывать robots.txt")
    user_agent: str = Field(default="WebCrawler/1.0", description="User-agent для robots.txt")
    custom_user_agent: str = Field(
        default="Mozilla/5.0 (compatible; WebCrawler/1.0)",
        description="Кастомный User-Agent для запросов"
    )
    robots_timeout: int = Field(default=10, gt=0, description="Таймаут загрузки robots.txt")


class SitemapConfig(BaseModel):
    """Конфигурация обработки sitemap.xml."""

    use_sitemap: bool = Field(default=True, description="Использовать sitemap.xml")
    prioritize_sitemap: bool = Field(default=True, description="Приоритет sitemap URL")
    sitemap_timeout: int = Field(default=15, gt=0, description="Таймаут загрузки sitemap")


class DatabaseConfig(BaseModel):
    """Конфигурация базы данных."""

    type: str = Field(default="sqlite", description="Тип БД: sqlite или postgresql")
    sqlite_path: str = Field(default="webcrawler/data/crawler.db", description="Путь к SQLite файлу")
    postgresql: dict[str, Any] = Field(
        default_factory=lambda: {
            "host": "localhost",
            "port": 5432,
            "database": "webcrawler",
            "user": "crawler",
            "password": "",
            "pool_size": 20,
            "pool_recycle": 3600
        },
        description="Настройки PostgreSQL"
    )
    batch_size: int = Field(default=1000, gt=0, description="Размер батча для операций")

    @field_validator('type')
    @classmethod
    def validate_db_type(cls, v: str) -> str:
        """Валидация типа БД."""
        if v not in ["sqlite", "postgresql"]:
            raise ValueError("Тип БД должен быть 'sqlite' или 'postgresql'")
        return v


class ProxyConfig(BaseModel):
    """Конфигурация прокси."""

    enabled: bool = Field(default=False, description="Использовать прокси")
    type: str = Field(default="http", description="Тип прокси: http, https, socks5")
    server: str = Field(default="", description="Адрес прокси сервера")
    port: int = Field(default=8080, gt=0, le=65535, description="Порт прокси")
    username: str = Field(default="", description="Имя пользователя для аутентификации")
    password: str = Field(default="", description="Пароль для аутентификации")
    rotate: bool = Field(default=False, description="Ротация прокси")
    servers: list[str] = Field(default_factory=list, description="Список прокси для ротации")

    @field_validator('type')
    @classmethod
    def validate_proxy_type(cls, v: str) -> str:
        """Валидация типа прокси."""
        if v not in ["http", "https", "socks5"]:
            raise ValueError("Тип прокси должен быть 'http', 'https' или 'socks5'")
        return v


class DistributedConfig(BaseModel):
    """Конфигурация распределённого краулинга."""

    enabled: bool = Field(default=False, description="Включить распределённый режим")
    redis: dict[str, Any] = Field(
        default_factory=lambda: {
            "host": "localhost",
            "port": 6379,
            "db": 0,
            "password": ""
        },
        description="Настройки Redis"
    )
    workers: int = Field(default=4, gt=0, description="Количество worker'ов")
    queue_name: str = Field(default="webcrawler:tasks", description="Имя очереди задач")


class ExportConfig(BaseModel):
    """Конфигурация экспорта."""

    formats: list[str] = Field(
        default_factory=lambda: ["json", "html", "pdf", "excel"],
        description="Форматы экспорта"
    )
    output_dir: str = Field(default="webcrawler/exports/", description="Директория для экспорта")
    graph_visualization: dict[str, Any] = Field(
        default_factory=lambda: {
            "enabled": True,
            "max_nodes": 10000,
            "layout": "force_directed",
            "export_formats": ["html", "png", "graphml"]
        },
        description="Настройки визуализации графа"
    )


class LoggingConfig(BaseModel):
    """Конфигурация логирования."""

    level: str = Field(default="INFO", description="Уровень логирования")
    file: str = Field(default="webcrawler/logs/crawler.log", description="Файл логов")
    rotation: str = Field(default="1 day", description="Ротация логов")
    retention: str = Field(default="30 days", description="Хранение логов")
    format: str = Field(default="detailed", description="Формат логов: detailed, json, simple")
    console: bool = Field(default=True, description="Вывод в консоль")
    colorize: bool = Field(default=True, description="Цветной вывод")

    @field_validator('level')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Валидация уровня логирования."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v = v.upper()
        if v not in valid_levels:
            raise ValueError(f"Уровень логирования должен быть одним из: {', '.join(valid_levels)}")
        return v

    @field_validator('format')
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        """Валидация формата логов."""
        if v not in ["detailed", "json", "simple"]:
            raise ValueError("Формат логов должен быть 'detailed', 'json' или 'simple'")
        return v


class PerformanceConfig(BaseModel):
    """Конфигурация производительности."""

    db_batch_size: int = Field(default=1000, gt=0, description="Размер батча для БД")
    checkpoint_interval: int = Field(default=300, gt=0, description="Интервал checkpoint (секунды)")
    url_cache_size: int = Field(default=100000, gt=0, description="Размер кеша URL")
    use_bloom_filter: bool = Field(default=True, description="Использовать Bloom filter")
    bloom_filter_error_rate: float = Field(
        default=0.001,
        gt=0,
        lt=1,
        description="Вероятность ложноположительных для Bloom filter"
    )


class PersistenceConfig(BaseModel):
    """Конфигурация персистентности."""

    enabled: bool = Field(default=True, description="Сохранять состояние")
    save_interval: int = Field(default=60, gt=0, description="Интервал сохранения (секунды)")
    auto_resume: bool = Field(default=True, description="Автоматическое возобновление")


class MonitoringConfig(BaseModel):
    """Конфигурация мониторинга."""

    enable_metrics: bool = Field(default=True, description="Включить метрики")
    prometheus_enabled: bool = Field(default=False, description="Prometheus endpoint")
    prometheus_port: int = Field(default=9090, gt=0, le=65535, description="Порт Prometheus")
    websocket_enabled: bool = Field(default=False, description="WebSocket мониторинг")
    websocket_port: int = Field(default=8765, gt=0, le=65535, description="Порт WebSocket")
    sentry_enabled: bool = Field(default=False, description="Sentry для ошибок")
    sentry_dsn: str = Field(default="", description="Sentry DSN")


class AnalyticsConfig(BaseModel):
    """Конфигурация аналитики."""

    detect_broken_links: bool = Field(default=True, description="Детектирование битых ссылок")
    seo_analysis: bool = Field(default=True, description="SEO анализ")
    performance_analysis: bool = Field(default=True, description="Анализ производительности")
    security_analysis: bool = Field(default=True, description="Анализ безопасности")
    detect_duplicate_content: bool = Field(default=True, description="Детектирование дубликатов")


class FeaturesConfig(BaseModel):
    """Конфигурация feature флагов."""

    incremental_crawling: bool = Field(default=False, description="Incremental crawling")
    intelligent_prioritization: bool = Field(default=True, description="Интеллектуальная приоритизация")
    adaptive_rate_limiting: bool = Field(default=True, description="Адаптивный rate limiting")
    honeypot_detection: bool = Field(default=True, description="Детектирование honeypot")


class Config(BaseSettings):
    """
    Главный класс конфигурации приложения.

    Загружает настройки из YAML файлов и переменных окружения.
    Все параметры валидируются через Pydantic.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__"
    )

    crawler: CrawlerConfig = Field(default_factory=CrawlerConfig)
    rate_limiting: RateLimitingConfig = Field(default_factory=RateLimitingConfig)
    robots: RobotsConfig = Field(default_factory=RobotsConfig)
    sitemap: SitemapConfig = Field(default_factory=SitemapConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    distributed: DistributedConfig = Field(default_factory=DistributedConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    persistence: PersistenceConfig = Field(default_factory=PersistenceConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    analytics: AnalyticsConfig = Field(default_factory=AnalyticsConfig)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)

    @classmethod
    def from_yaml(cls, config_path: str | Path) -> "Config":
        """
        Загрузить конфигурацию из YAML файла.

        Args:
            config_path: Путь к YAML файлу конфигурации

        Returns:
            Config: Объект конфигурации

        Raises:
            FileNotFoundError: Если файл не найден
            yaml.YAMLError: Если файл содержит невалидный YAML
            ValueError: Если конфигурация не проходит валидацию

        Example:
            >>> config = Config.from_yaml("webcrawler/config/default.yaml")
            >>> print(config.crawler.max_depth)
            0
        """
        config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"Конфигурационный файл не найден: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)

        if not yaml_data:
            raise ValueError(f"Конфигурационный файл пуст: {config_path}")

        return cls(**yaml_data)

    def to_yaml(self, output_path: str | Path) -> None:
        """
        Сохранить конфигурацию в YAML файл.

        Args:
            output_path: Путь для сохранения YAML файла

        Example:
            >>> config = Config.from_yaml("config.yaml")
            >>> config.crawler.max_depth = 5
            >>> config.to_yaml("custom_config.yaml")
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Преобразуем конфигурацию в словарь
        config_dict = self.model_dump(exclude_none=True)

        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def get_database_url(self) -> str:
        """
        Получить URL подключения к базе данных.

        Returns:
            str: URL для подключения к БД (SQLite или PostgreSQL)

        Example:
            >>> config = Config.from_yaml("config.yaml")
            >>> print(config.get_database_url())
            'sqlite+aiosqlite:///webcrawler/data/crawler.db'
        """
        if self.database.type == "sqlite":
            # Создаём директорию для БД, если не существует
            db_path = Path(self.database.sqlite_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite+aiosqlite:///{self.database.sqlite_path}"

        else:  # postgresql
            pg = self.database.postgresql
            password_part = f":{pg['password']}" if pg['password'] else ""
            return (
                f"postgresql+asyncpg://{pg['user']}{password_part}@"
                f"{pg['host']}:{pg['port']}/{pg['database']}"
            )

    def get_proxy_url(self) -> Optional[str]:
        """
        Получить URL прокси сервера.

        Returns:
            Optional[str]: URL прокси или None, если прокси отключен

        Example:
            >>> config = Config.from_yaml("config.yaml")
            >>> config.proxy.enabled = True
            >>> config.proxy.server = "proxy.example.com"
            >>> print(config.get_proxy_url())
            'http://proxy.example.com:8080'
        """
        if not self.proxy.enabled or not self.proxy.server:
            return None

        auth_part = ""
        if self.proxy.username and self.proxy.password:
            auth_part = f"{self.proxy.username}:{self.proxy.password}@"

        return f"{self.proxy.type}://{auth_part}{self.proxy.server}:{self.proxy.port}"


# Singleton instance для глобального доступа
_global_config: Optional[Config] = None


def get_config() -> Config:
    """
    Получить глобальный экземпляр конфигурации.

    Returns:
        Config: Глобальный объект конфигурации

    Raises:
        RuntimeError: Если конфигурация не была инициализирована

    Example:
        >>> from webcrawler.utils.config import init_config, get_config
        >>> init_config("config.yaml")
        >>> config = get_config()
        >>> print(config.crawler.max_pages)
    """
    global _global_config
    if _global_config is None:
        raise RuntimeError(
            "Конфигурация не инициализирована. "
            "Вызовите init_config() перед использованием get_config()"
        )
    return _global_config


def init_config(config_path: Optional[str | Path] = None) -> Config:
    """
    Инициализировать глобальную конфигурацию.

    Args:
        config_path: Путь к YAML файлу конфигурации.
                     Если None, используется конфигурация по умолчанию.

    Returns:
        Config: Инициализированный объект конфигурации

    Example:
        >>> from webcrawler.utils.config import init_config
        >>> config = init_config("webcrawler/config/default.yaml")
        >>> print(config.crawler.max_depth)
        0
    """
    global _global_config

    if config_path is None:
        # Используем конфигурацию по умолчанию
        default_config_path = Path(__file__).parent.parent / "config" / "default.yaml"
        config_path = default_config_path

    _global_config = Config.from_yaml(config_path)
    return _global_config


def reset_config() -> None:
    """
    Сбросить глобальную конфигурацию.

    Используется в основном для тестирования.
    """
    global _global_config
    _global_config = None
