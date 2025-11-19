"""
Модели базы данных для хранения данных краулера.

Использует SQLAlchemy 2.x с асинхронной поддержкой.
Все модели оптимизированы для работы с миллионами записей.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(AsyncAttrs, DeclarativeBase):
    """Базовый класс для всех моделей."""

    pass


class CrawlSession(Base):
    """
    Модель для хранения информации о сессиях краулинга.

    Каждая сессия представляет отдельный запуск краулера.
    """

    __tablename__ = "crawl_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    # Параметры краулинга
    start_url: Mapped[str] = mapped_column(Text, nullable=False)
    max_depth: Mapped[int] = mapped_column(Integer, default=0)
    max_pages: Mapped[int] = mapped_column(Integer, default=0)
    include_subdomains: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_javascript: Mapped[bool] = mapped_column(Boolean, default=False)

    # Статус сессии
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True
    )  # pending, running, paused, completed, failed

    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Статистика
    total_urls_discovered: Mapped[int] = mapped_column(Integer, default=0)
    total_urls_crawled: Mapped[int] = mapped_column(Integer, default=0)
    total_urls_failed: Mapped[int] = mapped_column(Integer, default=0)
    total_bytes_downloaded: Mapped[int] = mapped_column(BigInteger, default=0)

    # Конфигурация (JSON)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Ошибка (если сессия упала)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    urls: Mapped[list["URL"]] = relationship(
        "URL",
        back_populates="session",
        cascade="all, delete-orphan"
    )
    errors: Mapped[list["Error"]] = relationship(
        "Error",
        back_populates="session",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<CrawlSession(id={self.id}, session_id={self.session_id}, status={self.status})>"


class URL(Base):
    """
    Модель для хранения информации о URL.

    Содержит все метаданные о каждой обработанной странице.
    """

    __tablename__ = "urls"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("crawl_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # URL информация
    url: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False)

    # Домен
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subdomain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Статус обработки
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True
    )  # pending, crawling, completed, failed, skipped

    # HTTP метаданные
    http_status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content_encoding: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    content_length: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Временные метки
    discovered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    crawled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_modified: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Производительность
    response_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    download_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Глубина от стартового URL
    depth: Mapped[int] = mapped_column(Integer, default=0, index=True)

    # Счётчик посещений (если на страницу ведут множественные ссылки)
    visit_count: Mapped[int] = mapped_column(Integer, default=0)

    # HTTP заголовки (JSON)
    headers: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Редиректы
    redirect_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    redirect_chain: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # SSL/TLS информация
    ssl_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ssl_cipher: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Контент метаданные
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta_keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta_robots: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Структурированные данные
    has_schema_org: Mapped[bool] = mapped_column(Boolean, default=False)
    has_open_graph: Mapped[bool] = mapped_column(Boolean, default=False)
    structured_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Ссылки
    internal_links_count: Mapped[int] = mapped_column(Integer, default=0)
    external_links_count: Mapped[int] = mapped_column(Integer, default=0)

    # Контент хеш (для дедупликации)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # Флаги
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    is_honeypot: Mapped[bool] = mapped_column(Boolean, default=False)
    is_robots_allowed: Mapped[bool] = mapped_column(Boolean, default=True)

    # Ошибка (если есть)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships
    session: Mapped["CrawlSession"] = relationship("CrawlSession", back_populates="urls")
    outgoing_links: Mapped[list["Link"]] = relationship(
        "Link",
        foreign_keys="Link.source_url_id",
        back_populates="source_url",
        cascade="all, delete-orphan"
    )
    incoming_links: Mapped[list["Link"]] = relationship(
        "Link",
        foreign_keys="Link.target_url_id",
        back_populates="target_url",
        cascade="all, delete-orphan"
    )

    # Индексы для производительности
    __table_args__ = (
        Index("idx_url_session_url", "session_id", "url_hash"),
        Index("idx_url_domain_status", "domain", "status"),
        Index("idx_url_content_hash", "content_hash"),
    )

    def __repr__(self) -> str:
        return f"<URL(id={self.id}, url={self.url[:50]}..., status={self.status})>"


class Link(Base):
    """
    Модель для хранения графа ссылок между страницами.

    Представляет связь "страница A ссылается на страницу B".
    """

    __tablename__ = "links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("crawl_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Источник и цель ссылки
    source_url_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("urls.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    target_url_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("urls.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Тип ссылки
    link_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="hyperlink"
    )  # hyperlink, redirect, canonical, alternate, etc.

    # Текст ссылки (anchor text)
    anchor_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Атрибуты ссылки
    rel_attribute: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_nofollow: Mapped[bool] = mapped_column(Boolean, default=False)

    # Позиция ссылки на странице
    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Временная метка
    discovered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    source_url: Mapped["URL"] = relationship(
        "URL",
        foreign_keys=[source_url_id],
        back_populates="outgoing_links"
    )
    target_url: Mapped["URL"] = relationship(
        "URL",
        foreign_keys=[target_url_id],
        back_populates="incoming_links"
    )

    # Уникальность: одна ссылка между двумя URL в рамках сессии
    __table_args__ = (
        UniqueConstraint("session_id", "source_url_id", "target_url_id", name="uq_link"),
        Index("idx_link_source", "source_url_id"),
        Index("idx_link_target", "target_url_id"),
    )

    def __repr__(self) -> str:
        return f"<Link(id={self.id}, source={self.source_url_id}, target={self.target_url_id})>"


class Error(Base):
    """
    Модель для хранения журнала ошибок краулинга.

    Сохраняет все ошибки для анализа и отладки.
    """

    __tablename__ = "errors"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("crawl_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # URL с ошибкой
    url: Mapped[str] = mapped_column(Text, nullable=False)

    # Тип и описание ошибки
    error_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    error_details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # HTTP статус (если применимо)
    http_status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Стек трейс (для отладки)
    stack_trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Количество повторов
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # Временная метка
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True
    )

    # Relationships
    session: Mapped["CrawlSession"] = relationship("CrawlSession", back_populates="errors")

    __table_args__ = (
        Index("idx_error_type_time", "error_type", "occurred_at"),
    )

    def __repr__(self) -> str:
        return f"<Error(id={self.id}, type={self.error_type}, url={self.url[:50]}...)>"


class ContentHash(Base):
    """
    Модель для детектирования дубликатов контента.

    Хранит хеши контента для быстрого поиска дубликатов.
    """

    __tablename__ = "content_hashes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("crawl_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Хеш контента
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    # Первый URL с этим хешем (оригинал)
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    original_url_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Счётчик дубликатов
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)

    # Временная метка
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<ContentHash(hash={self.content_hash}, duplicates={self.duplicate_count})>"


class Statistics(Base):
    """
    Модель для хранения агрегированной статистики.

    Предвычисленные метрики для быстрого доступа.
    """

    __tablename__ = "statistics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("crawl_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )

    # Общая статистика
    total_urls: Mapped[int] = mapped_column(Integer, default=0)
    total_pages_crawled: Mapped[int] = mapped_column(Integer, default=0)
    total_errors: Mapped[int] = mapped_column(Integer, default=0)
    total_duplicates: Mapped[int] = mapped_column(Integer, default=0)

    # По статус-кодам
    status_2xx_count: Mapped[int] = mapped_column(Integer, default=0)
    status_3xx_count: Mapped[int] = mapped_column(Integer, default=0)
    status_4xx_count: Mapped[int] = mapped_column(Integer, default=0)
    status_5xx_count: Mapped[int] = mapped_column(Integer, default=0)

    # Производительность
    avg_response_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_bytes_downloaded: Mapped[int] = mapped_column(BigInteger, default=0)
    pages_per_second: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Топы
    top_domains: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    top_error_types: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    top_content_types: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Временные метки
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Statistics(session_id={self.session_id}, total_urls={self.total_urls})>"
