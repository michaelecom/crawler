"""
Pytest конфигурация и общие fixtures для всех тестов.
"""

import asyncio
import os
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from webcrawler.storage.database import DatabaseManager
from webcrawler.storage.models import Base
from webcrawler.utils.config import Config


# Pytest asyncio configuration
@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """
    Создать event loop для async тестов.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_config() -> Config:
    """
    Тестовая конфигурация.

    Использует SQLite в памяти для быстрых тестов.
    """
    # Создаём минимальную конфигурацию для тестов
    config_dict = {
        "crawler": {
            "start_urls": ["https://example.com"],
            "max_depth": 0,
            "max_pages": 100,
            "include_subdomains": True,
            "restrict_to_domain": True,
            "enable_javascript": False,
            "javascript_timeout": 30,
            "javascript_wait_until": "networkidle",
            "javascript_screenshots": False,
            "javascript_wait_for_ajax": True,
            "include_external_links": False,
            "follow_nofollow_links": False,
            "allowed_content_types": ["text/html"],
            "max_file_size": 10485760,  # 10 MB для тестов
        },
        "rate_limiting": {
            "requests_per_second": 10.0,
            "delay_between_requests": 100,
            "max_concurrent_requests": 10,
            "request_timeout": 10,
            "max_retries": 2,
            "backoff_factor": 2.0,
            "adaptive_delays": False,  # Отключаем для предсказуемости тестов
        },
        "robots": {
            "obey_robots": True,
            "user_agent": "TestCrawler/1.0",
            "custom_user_agent": "Mozilla/5.0 (compatible; TestCrawler/1.0)",
        },
        "sitemap": {
            "enabled": True,
            "auto_discover": True,
            "timeout": 10,
            "max_urls": 1000,
        },
        "database": {
            "type": "sqlite",
            "sqlite_path": ":memory:",  # In-memory для тестов
        },
        "proxy": {
            "enabled": False,
        },
        "distributed": {
            "enabled": False,
        },
        "export": {
            "formats": ["json"],
            "output_dir": "/tmp/test_exports",
        },
        "logging": {
            "level": "DEBUG",
            "file": "/tmp/test_crawler.log",
            "rotation": "1 day",
            "retention": "7 days",
            "format": "simple",
            "colorize": False,
        },
        "performance": {
            "db_batch_size": 100,
            "checkpoint_interval": 60,
            "url_cache_size": 1000,
        },
        "monitoring": {
            "enable_metrics": False,
        },
    }

    # Создаём Config из dict
    return Config(**config_dict)


@pytest.fixture
async def test_db_engine():
    """
    Создать тестовый database engine (SQLite in-memory).
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Создать таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    await engine.dispose()


@pytest.fixture
async def test_db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Создать тестовую database сессию.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_factory = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def test_db_manager(test_config) -> AsyncGenerator[DatabaseManager, None]:
    """
    Создать тестовый DatabaseManager.
    """
    from webcrawler.storage.database import DatabaseManager

    db_manager = DatabaseManager(test_config)
    await db_manager.initialize()
    await db_manager.create_tables()

    yield db_manager

    await db_manager.close()


@pytest.fixture
def sample_html() -> str:
    """
    Sample HTML для тестов парсера.
    """
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="description" content="Test page description">
        <meta name="keywords" content="test, page, keywords">
        <meta name="robots" content="index, follow">
        <meta property="og:title" content="Test Page">
        <meta property="og:description" content="OG Description">
        <title>Test Page Title</title>
        <link rel="canonical" href="https://example.com/canonical">
        <link rel="alternate" hreflang="es" href="https://example.com/es">
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": "Test Page"
        }
        </script>
    </head>
    <body>
        <h1>Main Heading</h1>
        <h2>Sub Heading</h2>
        <p>Some content with <a href="/page1">internal link</a> and
           <a href="https://external.com">external link</a>.</p>
        <a href="/page2" rel="nofollow">Nofollow link</a>
        <img src="/image.jpg" alt="Test image">
    </body>
    </html>
    """


@pytest.fixture
def sample_robots_txt() -> str:
    """
    Sample robots.txt для тестов.
    """
    return """
User-agent: *
Disallow: /admin
Disallow: /private

User-agent: Googlebot
Allow: /

Sitemap: https://example.com/sitemap.xml
Sitemap: https://example.com/sitemap2.xml

Crawl-delay: 1
"""


@pytest.fixture
def sample_sitemap_xml() -> str:
    """
    Sample sitemap.xml для тестов.
    """
    return """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://example.com/page1</loc>
        <lastmod>2025-01-01</lastmod>
        <changefreq>weekly</changefreq>
        <priority>0.8</priority>
    </url>
    <url>
        <loc>https://example.com/page2</loc>
        <lastmod>2025-01-02</lastmod>
        <priority>0.5</priority>
    </url>
</urlset>
"""


@pytest.fixture
def temp_test_dir(tmp_path) -> Path:
    """
    Временная директория для тестов.
    """
    test_dir = tmp_path / "crawler_test"
    test_dir.mkdir(exist_ok=True)
    return test_dir


# Markers для категоризации тестов
def pytest_configure(config):
    """Регистрация custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "asyncio: Async tests")
