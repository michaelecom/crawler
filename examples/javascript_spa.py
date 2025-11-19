#!/usr/bin/env python3
"""
Пример краулинга SPA приложения с JavaScript рендерингом

Демонстрирует использование headless browser для краулинга
современных React/Vue/Angular приложений.
"""

import asyncio
from webcrawler import Crawler
from webcrawler.utils.config import Config
from webcrawler.storage.database import init_db_manager


async def main():
    """Основная функция"""

    # Конфигурация с JavaScript рендерингом
    config = Config(**{
        "crawler": {
            "max_depth": 3,
            "max_pages": 500,
            "enable_javascript": True,
            "include_subdomains": False,
            "restrict_to_domain": True,
        },
        "javascript": {
            "browser": "chromium",
            "headless": True,
            "wait_until": "networkidle",
            "wait_after_load": 2000,
            "auto_scroll": True,
            "scroll_count": 5,
            "block_resources": ["image", "media", "font"],
            "stealth_mode": True,
        },
        "rate_limiting": {
            "requests_per_second": 2.0,
            "max_concurrent_requests": 5,
        },
        "database": {
            "type": "sqlite",
            "sqlite_path": "data/spa_crawl.db",
        },
        "logging": {
            "level": "INFO",
        }
    })

    # Инициализация БД
    db = await init_db_manager(config, create_tables=True)

    # Краулер
    crawler = Crawler(config, db)

    print("🚀 Запуск краулинга SPA приложения...")
    print("🌐 URL: https://spa-example.com")
    print("🎭 Браузер: Chromium (headless)")

    # Запуск краулинга
    session = await crawler.start_crawl("https://spa-example.com")

    # Мониторинг прогресса
    @session.on_event
    def show_progress(event):
        if event.event_type == "page_crawled":
            print(f"✓ {event.url}")

        if event.event_type == "progress" and event.statistics.urls_crawled % 10 == 0:
            stats = event.statistics
            print(
                f"\n📊 {stats.urls_crawled} / {stats.urls_discovered} страниц обработано\n"
            )

    # Ожидание завершения
    print("\n⏳ Ожидание завершения краулинга...\n")
    await session.wait_for_completion()

    # Результаты
    stats = session.get_statistics()
    print("\n" + "=" * 60)
    print("✅ Краулинг завершён!")
    print("=" * 60)
    print(f"📄 Страниц обработано: {stats.urls_crawled}")
    print(f"🔗 URL обнаружено: {stats.urls_discovered}")
    print(f"⏱️  Время: {stats.duration_seconds}s")
    print(f"📦 Размер: {stats.total_bytes / (1024*1024):.2f} MB")

    # Экспорт результатов
    print("\n📁 Экспорт результатов...")

    from webcrawler.export import JSONExporter, HTMLExporter

    # JSON
    json_exporter = JSONExporter(db)
    await json_exporter.export(
        session_id=session.session_id,
        output_path=f"exports/{session.session_id}.json",
        compress=True
    )
    print(f"   ✓ JSON: exports/{session.session_id}.json.gz")

    # HTML отчёт
    html_exporter = HTMLExporter(db)
    await html_exporter.export(
        session_id=session.session_id,
        output_path=f"exports/{session.session_id}.html",
        include_graphs=True
    )
    print(f"   ✓ HTML: exports/{session.session_id}.html")

    # Cleanup
    await db.close()
    print("\n✨ Готово!")


if __name__ == "__main__":
    asyncio.run(main())
