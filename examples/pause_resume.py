#!/usr/bin/env python3
"""
Пример использования pause/resume функциональности

Демонстрирует возможность приостанавливать и возобновлять
краулинг, а также сохранять состояние для продолжения после перезапуска.
"""

import asyncio
import signal
from webcrawler import Crawler
from webcrawler.utils.config import init_config
from webcrawler.storage.database import init_db_manager


async def main():
    """Основная функция"""

    config = init_config()
    db = await init_db_manager(config, create_tables=True)
    crawler = Crawler(config, db)

    print("🚀 Запуск краулинга с pause/resume...")

    # Запуск краулинга большого сайта
    session = await crawler.start_crawl(
        url="https://example.com",
        max_pages=10000
    )

    session_id = session.session_id
    print(f"📊 Session ID: {session_id}")
    print("💡 Нажмите Ctrl+C для паузы")

    # Флаг паузы
    paused = False

    # Signal handler для Ctrl+C
    def signal_handler(sig, frame):
        nonlocal paused
        paused = True
        print("\n⏸️  Получен сигнал прерывания, приостановка краулинга...")

    signal.signal(signal.SIGINT, signal_handler)

    # Мониторинг событий
    @session.on_event
    def handle_events(event):
        if event.event_type == "progress":
            stats = event.statistics
            print(
                f"\r📊 Прогресс: {stats.urls_crawled}/{stats.urls_discovered} "
                f"({stats.urls_failed} ошибок)",
                end=""
            )

    # Основной цикл
    try:
        while not session.is_completed():
            # Проверка флага паузы
            if paused:
                print("\n⏸️  Приостановка сессии...")
                await session.pause()

                print(f"\n💾 Сессия приостановлена: {session_id}")
                print("📝 Текущий прогресс сохранён в БД")
                print("\n💡 Для возобновления запустите:")
                print(f"   python examples/resume_session.py {session_id}")

                break

            # Ожидание 1 секунду перед следующей проверкой
            await asyncio.sleep(1)

        # Если завершилось естественно
        if session.is_completed():
            stats = session.get_statistics()
            print("\n✅ Краулинг завершён!")
            print(f"📄 Обработано: {stats.urls_crawled} страниц")

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        print("💾 Сохранение текущего состояния...")
        await session.pause()

    # Cleanup
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
