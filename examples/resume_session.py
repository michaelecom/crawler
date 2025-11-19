#!/usr/bin/env python3
"""
Пример возобновления приостановленной сессии краулинга

Использование:
    python examples/resume_session.py <session-id>
"""

import sys
import asyncio
from webcrawler import Crawler
from webcrawler.utils.config import init_config
from webcrawler.storage.database import init_db_manager
from webcrawler.storage.repository import CrawlSessionRepository


async def main():
    """Основная функция"""

    # Проверка аргументов
    if len(sys.argv) < 2:
        print("❌ Использование: python resume_session.py <session-id>")
        sys.exit(1)

    session_id = sys.argv[1]

    # Инициализация
    config = init_config()
    db = await init_db_manager(config)
    crawler = Crawler(config, db)

    # Проверка существования сессии
    async with db.session() as db_session:
        session_repo = CrawlSessionRepository(db_session)
        session_data = await session_repo.get_by_session_id(session_id)

        if not session_data:
            print(f"❌ Сессия {session_id} не найдена")
            await db.close()
            sys.exit(1)

        print("📊 Информация о сессии:")
        print(f"   ID: {session_data.session_id}")
        print(f"   Начальный URL: {session_data.start_url}")
        print(f"   Статус: {session_data.status}")
        print(f"   Начало: {session_data.start_time}")
        print(f"   Обработано URL: {session_data.urls_crawled}")

        if session_data.status not in ["paused", "failed"]:
            print(f"\n⚠️  Сессия в статусе '{session_data.status}'")
            print("   Можно возобновить только 'paused' или 'failed' сессии")
            await db.close()
            sys.exit(1)

    # Возобновление сессии
    print("\n▶️  Возобновление краулинга...")

    session = await crawler.resume_session(session_id)

    # Мониторинг прогресса
    @session.on_event
    def handle_progress(event):
        if event.event_type == "progress":
            stats = event.statistics
            print(
                f"\r📊 {stats.urls_crawled}/{stats.urls_discovered} "
                f"({stats.urls_failed} ошибок)",
                end=""
            )

        if event.event_type == "page_crawled":
            if stats.urls_crawled % 100 == 0:
                print(f"\n✓ Обработано {stats.urls_crawled} страниц")

    # Ожидание завершения
    await session.wait_for_completion()

    # Результаты
    stats = session.get_statistics()
    print("\n\n" + "=" * 60)
    print("✅ Краулинг завершён!")
    print("=" * 60)
    print(f"📄 Всего обработано: {stats.urls_crawled}")
    print(f"🔗 Всего обнаружено: {stats.urls_discovered}")
    print(f"❌ Ошибок: {stats.urls_failed}")
    print(f"⏱️  Общее время: {stats.duration_seconds}s")

    # Cleanup
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
