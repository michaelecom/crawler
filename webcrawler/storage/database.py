"""
Менеджер подключений к базе данных.

Управляет async подключениями к SQLite/PostgreSQL,
пулом соединений и транзакциями.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, QueuePool

from webcrawler.storage.models import Base
from webcrawler.utils.config import Config
from webcrawler.utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """
    Менеджер подключений к базе данных.

    Обеспечивает создание и управление async соединениями,
    инициализацию схемы и миграции.

    Example:
        >>> config = Config.from_yaml("config.yaml")
        >>> db_manager = DatabaseManager(config)
        >>> await db_manager.initialize()
        >>>
        >>> async with db_manager.session() as session:
        ...     result = await session.execute(query)
    """

    def __init__(self, config: Config):
        """
        Инициализация менеджера БД.

        Args:
            config: Объект конфигурации приложения
        """
        self.config = config
        self.database_url = config.get_database_url()
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker[AsyncSession]] = None

        logger.info(
            "database_manager_initialized",
            db_type=config.database.type,
            url=self._mask_password(self.database_url)
        )

    def _mask_password(self, url: str) -> str:
        """
        Скрыть пароль в database URL для безопасного логирования.

        Args:
            url: Database URL

        Returns:
            str: URL с замаскированным паролем
        """
        if "@" in url and "://" in url:
            parts = url.split("://")
            if len(parts) == 2:
                protocol = parts[0]
                rest = parts[1]
                if "@" in rest:
                    credentials, location = rest.split("@", 1)
                    if ":" in credentials:
                        username = credentials.split(":")[0]
                        return f"{protocol}://{username}:***@{location}"
        return url

    async def initialize(self) -> None:
        """
        Инициализировать подключение к базе данных.

        Создаёт engine, session factory и настраивает пул соединений.
        """
        logger.info("initializing_database", url=self._mask_password(self.database_url))

        # Параметры для engine
        engine_kwargs = {
            "echo": False,  # Логирование SQL запросов (для debug можно включить)
            "future": True,
        }

        # Настройка пула соединений
        if self.config.database.type == "sqlite":
            # SQLite: NullPool или небольшой пул
            engine_kwargs["poolclass"] = NullPool
            engine_kwargs["connect_args"] = {
                "check_same_thread": False,  # Для async
            }

            # Включаем WAL mode для лучшей конкурентности
            @event.listens_for(AsyncEngine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.close()

        else:  # PostgreSQL
            pool_size = self.config.database.postgresql.get("pool_size", 20)
            pool_recycle = self.config.database.postgresql.get("pool_recycle", 3600)

            engine_kwargs["poolclass"] = QueuePool
            engine_kwargs["pool_size"] = pool_size
            engine_kwargs["pool_recycle"] = pool_recycle
            engine_kwargs["pool_pre_ping"] = True  # Проверка соединений перед использованием

        # Создаём engine
        self.engine = create_async_engine(self.database_url, **engine_kwargs)

        # Создаём session factory
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        # Проверяем подключение
        try:
            async with self.engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("database_connection_successful")
        except Exception as e:
            logger.error("database_connection_failed", error=str(e))
            raise

    async def create_tables(self) -> None:
        """
        Создать все таблицы в базе данных.

        Используется для первоначальной инициализации.
        В production рекомендуется использовать миграции (Alembic).
        """
        if not self.engine:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        logger.info("creating_database_tables")

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("database_tables_created")

    async def drop_tables(self) -> None:
        """
        Удалить все таблицы из базы данных.

        ⚠️ ОСТОРОЖНО: Удаляет все данные!
        Используется только в dev/test окружении.
        """
        if not self.engine:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        logger.warning("dropping_database_tables")

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        logger.warning("database_tables_dropped")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Контекстный менеджер для создания database сессии.

        Автоматически управляет транзакциями и commit/rollback.

        Yields:
            AsyncSession: Database сессия

        Example:
            >>> async with db_manager.session() as session:
            ...     result = await session.execute(select(URL))
            ...     urls = result.scalars().all()
        """
        if not self.session_factory:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error("session_rollback", error=str(e), error_type=type(e).__name__)
            raise
        finally:
            await session.close()

    async def close(self) -> None:
        """
        Закрыть все подключения к базе данных.

        Должно вызываться при завершении приложения.
        """
        if self.engine:
            logger.info("closing_database_connections")
            await self.engine.dispose()
            logger.info("database_connections_closed")

    async def get_table_count(self, table_name: str) -> int:
        """
        Получить количество записей в таблице.

        Args:
            table_name: Название таблицы

        Returns:
            int: Количество записей

        Example:
            >>> count = await db_manager.get_table_count("urls")
            >>> print(f"Total URLs: {count}")
        """
        async with self.session() as session:
            result = await session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            count = result.scalar()
            return count or 0

    async def get_database_size(self) -> int:
        """
        Получить размер базы данных в байтах.

        Returns:
            int: Размер БД в байтах

        Example:
            >>> size = await db_manager.get_database_size()
            >>> print(f"Database size: {size / 1024 / 1024:.2f} MB")
        """
        if self.config.database.type == "sqlite":
            import os
            from pathlib import Path

            db_path = Path(self.config.database.sqlite_path)
            if db_path.exists():
                return os.path.getsize(db_path)
            return 0

        else:  # PostgreSQL
            async with self.session() as session:
                query = text(
                    "SELECT pg_database_size(current_database())"
                )
                result = await session.execute(query)
                size = result.scalar()
                return size or 0

    async def vacuum(self) -> None:
        """
        Выполнить VACUUM для оптимизации БД.

        Полезно для SQLite после удаления большого объёма данных.
        """
        if self.config.database.type == "sqlite":
            logger.info("vacuuming_sqlite_database")
            async with self.engine.begin() as conn:
                await conn.execute(text("VACUUM"))
            logger.info("sqlite_database_vacuumed")
        else:
            logger.info("vacuum_not_supported_for_postgresql")

    async def get_table_info(self) -> dict[str, int]:
        """
        Получить информацию о всех таблицах.

        Returns:
            dict: Словарь {table_name: row_count}

        Example:
            >>> info = await db_manager.get_table_info()
            >>> for table, count in info.items():
            ...     print(f"{table}: {count} rows")
        """
        tables = [
            "crawl_sessions",
            "urls",
            "links",
            "errors",
            "content_hashes",
            "statistics"
        ]

        info = {}
        for table in tables:
            try:
                count = await self.get_table_count(table)
                info[table] = count
            except Exception as e:
                logger.warning(f"failed_to_get_count_for_{table}", error=str(e))
                info[table] = -1

        return info

    async def check_health(self) -> bool:
        """
        Проверить работоспособность подключения к БД.

        Returns:
            bool: True если БД работает

        Example:
            >>> is_healthy = await db_manager.check_health()
            >>> if not is_healthy:
            ...     logger.error("Database is not healthy!")
        """
        try:
            async with self.session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error("database_health_check_failed", error=str(e))
            return False


# Singleton instance для глобального доступа
_global_db_manager: Optional[DatabaseManager] = None


async def get_db_manager() -> DatabaseManager:
    """
    Получить глобальный экземпляр DatabaseManager.

    Returns:
        DatabaseManager: Глобальный менеджер БД

    Raises:
        RuntimeError: Если менеджер не был инициализирован

    Example:
        >>> from webcrawler.storage.database import get_db_manager
        >>> db = await get_db_manager()
        >>> async with db.session() as session:
        ...     # работа с БД
        ...     pass
    """
    global _global_db_manager
    if _global_db_manager is None:
        raise RuntimeError(
            "DatabaseManager не инициализирован. "
            "Вызовите init_db_manager() перед использованием."
        )
    return _global_db_manager


async def init_db_manager(config: Config, create_tables: bool = False) -> DatabaseManager:
    """
    Инициализировать глобальный DatabaseManager.

    Args:
        config: Объект конфигурации
        create_tables: Создать таблицы если не существуют

    Returns:
        DatabaseManager: Инициализированный менеджер БД

    Example:
        >>> from webcrawler.utils.config import init_config
        >>> from webcrawler.storage.database import init_db_manager
        >>>
        >>> config = init_config("config.yaml")
        >>> db = await init_db_manager(config, create_tables=True)
    """
    global _global_db_manager

    _global_db_manager = DatabaseManager(config)
    await _global_db_manager.initialize()

    if create_tables:
        await _global_db_manager.create_tables()

    return _global_db_manager


async def close_db_manager() -> None:
    """
    Закрыть глобальный DatabaseManager.

    Должно вызываться при завершении приложения.
    """
    global _global_db_manager
    if _global_db_manager:
        await _global_db_manager.close()
        _global_db_manager = None
