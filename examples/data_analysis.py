#!/usr/bin/env python3
"""
Пример анализа результатов краулинга через repositories

Демонстрирует как извлекать и анализировать данные краулинга
используя repository pattern.
"""

import asyncio
from collections import Counter
from webcrawler.storage.database import DatabaseManager
from webcrawler.storage.repository import (
    CrawlSessionRepository,
    URLRepository,
    LinkRepository,
    ErrorRepository,
)
from webcrawler.utils.config import init_config


async def analyze_session(session_id: str):
    """Анализ сессии краулинга"""

    # Инициализация БД
    config = init_config()
    db = DatabaseManager(config)
    await db.initialize()

    async with db.session() as db_session:
        # Repositories
        session_repo = CrawlSessionRepository(db_session)
        url_repo = URLRepository(db_session)
        link_repo = LinkRepository(db_session)
        error_repo = ErrorRepository(db_session)

        # Информация о сессии
        print("=" * 60)
        print("📊 Анализ сессии краулинга")
        print("=" * 60)

        session = await session_repo.get_by_session_id(session_id)
        if not session:
            print(f"❌ Сессия {session_id} не найдена")
            return

        print(f"\n🆔 Session ID: {session.session_id}")
        print(f"🌐 Start URL: {session.start_url}")
        print(f"📅 Start Time: {session.start_time}")
        print(f"📅 End Time: {session.end_time}")
        print(f"⏱️  Duration: {session.duration_seconds}s")
        print(f"📊 Status: {session.status}")

        # Статистика URL
        print("\n" + "-" * 60)
        print("📄 Статистика URL")
        print("-" * 60)

        total_urls = await url_repo.count_by_session(session_id)
        completed_urls = await url_repo.count_by_status(session_id, "completed")
        pending_urls = await url_repo.count_by_status(session_id, "pending")
        failed_urls = await url_repo.count_by_status(session_id, "failed")

        print(f"Всего URL: {total_urls}")
        print(f"  ✓ Обработано: {completed_urls}")
        print(f"  ⏳ В очереди: {pending_urls}")
        print(f"  ❌ Ошибок: {failed_urls}")

        # Распределение по глубине
        print("\n📊 Распределение по глубине:")
        urls_all = await url_repo.get_all_by_session(session_id)
        depth_counter = Counter(url.depth for url in urls_all)
        for depth in sorted(depth_counter.keys()):
            count = depth_counter[depth]
            bar = "█" * (count // 10)
            print(f"  Глубина {depth}: {count:>5} {bar}")

        # Статус коды
        print("\n📊 Статус коды:")
        status_counter = Counter(url.status_code for url in urls_all if url.status_code)
        for status in sorted(status_counter.keys()):
            count = status_counter[status]
            emoji = "✅" if status == 200 else "⚠️" if status < 400 else "❌"
            print(f"  {emoji} {status}: {count}")

        # Content types
        print("\n📊 Типы контента:")
        content_counter = Counter(url.content_type for url in urls_all if url.content_type)
        for content_type, count in content_counter.most_common(10):
            print(f"  {content_type}: {count}")

        # Топ 10 самых больших страниц
        print("\n📦 Топ 10 самых больших страниц:")
        urls_by_size = sorted(
            (url for url in urls_all if url.size_bytes),
            key=lambda u: u.size_bytes,
            reverse=True
        )[:10]

        for i, url in enumerate(urls_by_size, 1):
            size_mb = url.size_bytes / (1024 * 1024)
            print(f"  {i}. {size_mb:.2f} MB - {url.url}")

        # Топ 10 самых медленных страниц
        print("\n⏱️  Топ 10 самых медленных страниц:")
        urls_by_time = sorted(
            (url for url in urls_all if url.response_time),
            key=lambda u: u.response_time,
            reverse=True
        )[:10]

        for i, url in enumerate(urls_by_time, 1):
            print(f"  {i}. {url.response_time:.3f}s - {url.url}")

        # Статистика ссылок
        print("\n" + "-" * 60)
        print("🔗 Статистика ссылок")
        print("-" * 60)

        all_links = await link_repo.get_all_by_session(session_id)
        internal_links = [l for l in all_links if l.link_type == "internal"]
        external_links = [l for l in all_links if l.link_type == "external"]

        print(f"Всего ссылок: {len(all_links)}")
        print(f"  🔗 Внутренних: {len(internal_links)}")
        print(f"  🌐 Внешних: {len(external_links)}")

        # Топ внешних доменов
        print("\n🌐 Топ 10 внешних доменов:")
        from urllib.parse import urlparse
        external_domains = Counter()
        for link in external_links:
            domain = urlparse(link.target_url).netloc
            external_domains[domain] += 1

        for domain, count in external_domains.most_common(10):
            print(f"  {domain}: {count} ссылок")

        # Страницы с наибольшим количеством исходящих ссылок
        print("\n🔗 Страницы с наибольшим количеством ссылок:")
        source_counter = Counter(link.source_url for link in all_links)
        for url, count in source_counter.most_common(10):
            print(f"  {count} ссылок: {url}")

        # Ошибки
        print("\n" + "-" * 60)
        print("❌ Ошибки")
        print("-" * 60)

        errors = await error_repo.get_all_by_session(session_id)
        error_types = Counter(e.error_type for e in errors)

        print(f"Всего ошибок: {len(errors)}")
        for error_type, count in error_types.most_common():
            print(f"  {error_type}: {count}")

        # Примеры ошибок
        if errors:
            print("\n📋 Примеры ошибок:")
            for error in errors[:5]:
                print(f"  [{error.error_type}] {error.url}")
                print(f"    {error.error_message}")

    # Cleanup
    await db.close()


async def main():
    """Основная функция"""

    import sys

    if len(sys.argv) < 2:
        print("❌ Использование: python data_analysis.py <session-id>")
        print("\nПолучить список сессий:")
        print("  crawler sessions")
        sys.exit(1)

    session_id = sys.argv[1]
    await analyze_session(session_id)


if __name__ == "__main__":
    asyncio.run(main())
