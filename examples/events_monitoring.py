#!/usr/bin/env python3
"""
Пример с мониторингом событий краулинга в реальном времени

Демонстрирует использование event callbacks для отслеживания
прогресса краулинга.
"""

import asyncio
from datetime import datetime
from webcrawler import Crawler
from webcrawler.utils.config import init_config
from webcrawler.storage.database import init_db_manager


async def main():
    """Основная функция"""

    config = init_config()
    db = await init_db_manager(config, create_tables=True)
    crawler = Crawler(config, db)

    print("🚀 Запуск краулинга с мониторингом событий...")

    # Запуск
    session = await crawler.start_crawl("https://example.com")

    # Подписка на события
    @session.on_event
    def handle_page_crawled(event):
        """Обработка события успешного краулинга страницы"""
        if event.event_type == "page_crawled":
            status_emoji = "✅" if event.status_code == 200 else "⚠️"
            print(
                f"{status_emoji} [{event.status_code}] {event.url} "
                f"({event.response_time:.3f}s)"
            )

    @session.on_event
    def handle_error(event):
        """Обработка ошибок"""
        if event.event_type == "error":
            print(f"❌ Ошибка: {event.url}")
            print(f"   {event.error_type}: {event.error_message}")

    @session.on_event
    def handle_progress(event):
        """Обработка прогресса"""
        if event.event_type == "progress":
            stats = event.statistics
            progress = (stats.urls_crawled / stats.urls_discovered) * 100
            print(
                f"\n📊 Прогресс: {stats.urls_crawled}/{stats.urls_discovered} "
                f"({progress:.1f}%)"
            )

    @session.on_event
    def handle_link_discovered(event):
        """Обработка новых ссылок"""
        if event.event_type == "link_discovered":
            print(f"🔗 Найдена ссылка: {event.url} (глубина: {event.depth})")

    @session.on_event
    def handle_session_paused(event):
        """Обработка паузы"""
        if event.event_type == "session_paused":
            print(f"\n⏸️  Сессия приостановлена")

    @session.on_event
    def handle_session_resumed(event):
        """Обработка возобновления"""
        if event.event_type == "session_resumed":
            print(f"\n▶️  Сессия возобновлена")

    @session.on_event
    def handle_checkpoint(event):
        """Обработка checkpoint"""
        if event.event_type == "checkpoint":
            print(f"\n💾 Checkpoint создан: {event.checkpoint_id}")

    # Ожидание завершения
    await session.wait_for_completion()

    # Финальная статистика
    stats = session.get_statistics()
    print("\n" + "=" * 60)
    print("📈 Финальная статистика:")
    print("=" * 60)
    print(f"🕐 Начало:          {stats.start_time}")
    print(f"🕐 Завершение:      {stats.end_time}")
    print(f"⏱️  Длительность:    {stats.duration_seconds}s")
    print(f"📄 URL обработано:  {stats.urls_crawled}")
    print(f"🔗 URL обнаружено:  {stats.urls_discovered}")
    print(f"❌ Ошибок:          {stats.urls_failed}")
    print(f"📦 Размер данных:   {stats.total_bytes / (1024*1024):.2f} MB")
    print(f"⚡ Средн. скорость: {stats.avg_response_time:.3f}s")

    # Статус коды
    print("\n📊 Распределение статус кодов:")
    for code, count in stats.status_codes.items():
        print(f"   {code}: {count}")

    # Cleanup
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
