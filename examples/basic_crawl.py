#!/usr/bin/env python3
"""
Базовый пример краулинга сайта

Демонстрирует минимальный код для запуска краулера
и получения результатов.
"""

import asyncio
from webcrawler import Crawler
from webcrawler.utils.config import init_config
from webcrawler.storage.database import init_db_manager


async def main():
    """Основная функция"""

    # Инициализация конфигурации
    config = init_config("config.yaml")

    # Инициализация БД
    db = await init_db_manager(config, create_tables=True)

    # Создание краулера
    crawler = Crawler(config, db)

    print("🚀 Запуск краулинга...")

    # Запуск краулинга
    session = await crawler.start_crawl(
        url="https://example.com",
        max_depth=3,
        max_pages=100
    )

    print(f"📊 Session ID: {session.session_id}")

    # Ожидание завершения
    await session.wait_for_completion()

    # Получение статистики
    stats = session.get_statistics()

    print("\n✅ Краулинг завершён!")
    print(f"📄 Обработано страниц: {stats.urls_crawled}")
    print(f"🔗 Найдено URL: {stats.urls_discovered}")
    print(f"❌ Ошибок: {stats.urls_failed}")
    print(f"⏱️  Время: {stats.duration_seconds}s")

    # Cleanup
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
