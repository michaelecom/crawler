"""
CLI интерфейс для веб-краулера.

Предоставляет команды для запуска, мониторинга и экспорта
результатов краулинга через терминал.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from webcrawler.analyzers import ContentAnalyzer, LinkExtractor, StatsCalculator
from webcrawler.core.crawler import Crawler, CrawlEvent, CrawlStatus
from webcrawler.export import JSONExporter, CSVExporter, GraphMLExporter
from webcrawler.storage.database import close_db_manager, init_db_manager
from webcrawler.storage.repository import CrawlSessionRepository
from webcrawler.utils.config import Config, init_config
from webcrawler.utils.helpers import format_bytes, format_duration

# Инициализация
app = typer.Typer(
    name="crawler",
    help="Enterprise Web Crawler - мощный инструмент для анализа веб-сайтов",
    add_completion=False,
)
console = Console()


def version_callback(value: bool):
    """Вывести версию приложения."""
    if value:
        console.print("[bold]Enterprise Web Crawler[/bold] v1.0.0")
        console.print("Python Web Crawler с поддержкой JavaScript и распределённого краулинга")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Показать версию и выйти",
    ),
):
    """
    Enterprise Web Crawler - продвинутый краулер для анализа веб-сайтов.

    Поддерживает миллионы страниц, JavaScript рендеринг, распределённый краулинг
    и экспорт в различные форматы.
    """
    pass


@app.command()
def crawl(
    url: str = typer.Argument(..., help="URL для краулинга"),
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Путь к файлу конфигурации",
        exists=True,
    ),
    max_depth: Optional[int] = typer.Option(
        None, "--max-depth", "-d", help="Максимальная глубина обхода"
    ),
    max_pages: Optional[int] = typer.Option(
        None, "--max-pages", "-p", help="Максимальное количество страниц"
    ),
    enable_javascript: Optional[bool] = typer.Option(
        None, "--javascript/--no-javascript", "-j", help="Включить JavaScript рендеринг"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Файл для сохранения session ID"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробный вывод"),
):
    """
    Запустить краулинг веб-сайта.

    Примеры:
        crawler crawl https://example.com
        crawler crawl https://example.com --max-pages 1000
        crawler crawl https://example.com --javascript --max-depth 3
    """
    try:
        # Загрузка конфигурации
        if config_file:
            config = Config.from_yaml(str(config_file))
        else:
            config = init_config()

        # Override параметров
        if max_depth is not None:
            config.crawler.max_depth = max_depth
        if max_pages is not None:
            config.crawler.max_pages = max_pages
        if enable_javascript is not None:
            config.crawler.enable_javascript = enable_javascript

        # Установка уровня логирования
        if verbose:
            config.logging.level = "DEBUG"

        console.print(
            Panel(
                f"[bold cyan]Запуск краулинга:[/bold cyan] {url}\n"
                f"[dim]Макс. глубина: {config.crawler.max_depth or 'без ограничений'}[/dim]\n"
                f"[dim]Макс. страниц: {config.crawler.max_pages or 'без ограничений'}[/dim]\n"
                f"[dim]JavaScript: {'включен' if config.crawler.enable_javascript else 'выключен'}[/dim]",
                title="🚀 Web Crawler",
            )
        )

        # Запуск asyncio event loop
        asyncio.run(_run_crawl(url, config, output, verbose))

    except KeyboardInterrupt:
        console.print("\n[yellow]Краулинг прерван пользователем[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[bold red]Ошибка:[/bold red] {e}")
        if verbose:
            console.print_exception()
        sys.exit(1)


async def _run_crawl(
    url: str, config: Config, output: Optional[Path], verbose: bool
):
    """
    Внутренняя функция для запуска краулинга.

    Args:
        url: URL для краулинга
        config: Конфигурация
        output: Файл для сохранения session ID
        verbose: Подробный вывод
    """
    # Инициализация БД
    db = await init_db_manager(config, create_tables=True)

    # Создание краулера
    crawler = Crawler(config, db)

    # Запуск сессии
    session = await crawler.start_crawl(url)
    session_id = session.session_id

    console.print(f"[green]✓[/green] Сессия создана: [bold]{session_id}[/bold]")

    # Сохранение session ID в файл
    if output:
        output.write_text(session_id)
        console.print(f"[green]✓[/green] Session ID сохранён в {output}")

    # Progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("•"),
        TextColumn("[cyan]{task.fields[crawled]}[/cyan] обработано"),
        TextColumn("•"),
        TextColumn("[yellow]{task.fields[discovered]}[/yellow] найдено"),
        TextColumn("•"),
        TextColumn("[red]{task.fields[failed]}[/red] ошибок"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task(
            "[cyan]Краулинг...",
            total=config.crawler.max_pages or 100,
            crawled=0,
            discovered=0,
            failed=0,
        )

        # Callback для обновления прогресса
        def on_event(event: CrawlEvent):
            """Обработчик событий краулинга."""
            if event.event_type == "page_crawled":
                stats = event.statistics
                progress.update(
                    task,
                    completed=stats.urls_crawled,
                    crawled=stats.urls_crawled,
                    discovered=stats.urls_discovered,
                    failed=stats.urls_failed,
                )

                if verbose:
                    console.print(
                        f"[dim]  ✓ {event.url} ({event.status_code})[/dim]"
                    )

            elif event.event_type == "error":
                if verbose:
                    console.print(f"[red]  ✗ {event.url}: {event.error}[/red]")

        session.on_event(on_event)

        # Ожидание завершения
        await session.wait_for_completion()

    # Финальная статистика
    stats = session.get_statistics()

    console.print("\n[bold green]✓ Краулинг завершён![/bold green]\n")

    # Таблица статистики
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Метрика", style="dim")
    table.add_column("Значение", justify="right")

    table.add_row("Обнаружено URL", f"{stats.urls_discovered:,}")
    table.add_row("Обработано страниц", f"{stats.urls_crawled:,}")
    table.add_row("Ошибок", f"{stats.urls_failed:,}")
    table.add_row("Пропущено", f"{stats.urls_skipped:,}")
    table.add_row("", "")
    table.add_row("Статус 2xx", f"{stats.status_2xx:,}")
    table.add_row("Статус 3xx", f"{stats.status_3xx:,}")
    table.add_row("Статус 4xx", f"{stats.status_4xx:,}")
    table.add_row("Статус 5xx", f"{stats.status_5xx:,}")
    table.add_row("", "")
    table.add_row("Загружено данных", format_bytes(stats.total_bytes_downloaded))
    table.add_row("Ср. время ответа", f"{stats.avg_response_time:.3f}s")
    table.add_row("Скорость", f"{stats.pages_per_second:.2f} стр/сек")

    console.print(table)
    console.print(f"\n[dim]Session ID:[/dim] [bold]{session_id}[/bold]")

    # Закрытие БД
    await close_db_manager()


@app.command()
def resume(
    session_id: str = typer.Argument(..., help="ID сессии для возобновления"),
    config_file: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Путь к файлу конфигурации"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробный вывод"),
):
    """
    Возобновить остановленную сессию краулинга.

    Примеры:
        crawler resume crawl_abc123
        crawler resume crawl_abc123 --verbose
    """
    try:
        # Загрузка конфигурации
        if config_file:
            config = Config.from_yaml(str(config_file))
        else:
            config = init_config()

        console.print(
            f"[cyan]Возобновление сессии:[/cyan] [bold]{session_id}[/bold]"
        )

        # Запуск
        asyncio.run(_run_resume(session_id, config, verbose))

    except KeyboardInterrupt:
        console.print("\n[yellow]Краулинг прерван пользователем[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[bold red]Ошибка:[/bold red] {e}")
        if verbose:
            console.print_exception()
        sys.exit(1)


async def _run_resume(session_id: str, config: Config, verbose: bool):
    """Возобновление сессии."""
    db = await init_db_manager(config)
    crawler = Crawler(config, db)

    # Возобновление
    session = await crawler.resume_crawl(session_id)

    console.print("[green]✓[/green] Сессия возобновлена")

    # Progress (аналогично crawl)
    # ... (код аналогичен _run_crawl)

    await session.wait_for_completion()
    await close_db_manager()


@app.command()
def stats(
    session_id: str = typer.Argument(..., help="ID сессии"),
    config_file: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Путь к файлу конфигурации"
    ),
):
    """
    Показать статистику сессии краулинга.

    Примеры:
        crawler stats crawl_abc123
    """
    try:
        if config_file:
            config = Config.from_yaml(str(config_file))
        else:
            config = init_config()

        asyncio.run(_show_stats(session_id, config))

    except Exception as e:
        console.print(f"[bold red]Ошибка:[/bold red] {e}")
        sys.exit(1)


async def _show_stats(session_id: str, config: Config):
    """Показать статистику сессии."""
    db = await init_db_manager(config)

    async with db.session() as db_session:
        repo = CrawlSessionRepository(db_session)

        # Загрузка сессии
        crawl_session = await repo.get_by_session_id(session_id)

        if not crawl_session:
            console.print(f"[red]Сессия {session_id} не найдена[/red]")
            await close_db_manager()
            return

        # Вывод информации
        console.print(
            Panel(
                f"[bold]Session ID:[/bold] {crawl_session.session_id}\n"
                f"[bold]Статус:[/bold] {crawl_session.status}\n"
                f"[bold]Start URL:[/bold] {crawl_session.start_url}\n"
                f"[bold]Создана:[/bold] {crawl_session.created_at}\n"
                f"[bold]Запущена:[/bold] {crawl_session.started_at or 'N/A'}\n"
                f"[bold]Завершена:[/bold] {crawl_session.completed_at or 'N/A'}",
                title="📊 Информация о сессии",
            )
        )

        # Таблица статистики
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Метрика", style="dim")
        table.add_column("Значение", justify="right")

        table.add_row("Обнаружено URL", f"{crawl_session.total_urls_discovered:,}")
        table.add_row("Обработано страниц", f"{crawl_session.total_urls_crawled:,}")
        table.add_row("Ошибок", f"{crawl_session.total_urls_failed:,}")
        table.add_row(
            "Загружено данных", format_bytes(crawl_session.total_bytes_downloaded)
        )

        console.print(table)

    await close_db_manager()


@app.command(name="sessions")
def list_sessions(
    config_file: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Путь к файлу конфигурации"
    ),
    status: Optional[str] = typer.Option(
        None, "--status", "-s", help="Фильтр по статусу"
    ),
    limit: int = typer.Option(20, "--limit", "-l", help="Количество сессий"),
):
    """
    Показать список всех сессий краулинга.

    Примеры:
        crawler sessions
        crawler sessions --status completed
        crawler sessions --limit 50
    """
    try:
        if config_file:
            config = Config.from_yaml(str(config_file))
        else:
            config = init_config()

        asyncio.run(_list_sessions(config, status, limit))

    except Exception as e:
        console.print(f"[bold red]Ошибка:[/bold red] {e}")
        sys.exit(1)


async def _list_sessions(config: Config, status_filter: Optional[str], limit: int):
    """Список сессий."""
    db = await init_db_manager(config)

    async with db.session() as db_session:
        repo = CrawlSessionRepository(db_session)

        # Загрузка сессий
        sessions = await repo.get_all_sessions(limit=limit)

        if not sessions:
            console.print("[yellow]Нет сессий краулинга[/yellow]")
            await close_db_manager()
            return

        # Фильтрация по статусу
        if status_filter:
            sessions = [s for s in sessions if s.status == status_filter]

        # Таблица сессий
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Session ID", style="dim")
        table.add_column("Start URL")
        table.add_column("Статус")
        table.add_column("Обработано", justify="right")
        table.add_column("Создана")

        for session in sessions:
            # Цвет статуса
            status_color = {
                "pending": "yellow",
                "running": "cyan",
                "paused": "blue",
                "completed": "green",
                "failed": "red",
            }.get(session.status, "white")

            table.add_row(
                session.session_id[:16] + "...",
                session.start_url[:50] + "..." if len(session.start_url) > 50 else session.start_url,
                f"[{status_color}]{session.status}[/{status_color}]",
                f"{session.total_urls_crawled:,}",
                session.created_at.strftime("%Y-%m-%d %H:%M"),
            )

        console.print(table)
        console.print(f"\n[dim]Всего сессий: {len(sessions)}[/dim]")

    await close_db_manager()


@app.command()
def cleanup(
    older_than_days: int = typer.Option(
        30, "--older-than", "-o", help="Удалить сессии старше N дней"
    ),
    status: Optional[str] = typer.Option(
        "completed", "--status", "-s", help="Удалить сессии со статусом"
    ),
    config_file: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Путь к файлу конфигурации"
    ),
    confirm: bool = typer.Option(
        False, "--yes", "-y", help="Подтвердить без запроса"
    ),
):
    """
    Очистить старые данные краулинга.

    Примеры:
        crawler cleanup --older-than 30
        crawler cleanup --status completed --yes
    """
    try:
        if config_file:
            config = Config.from_yaml(str(config_file))
        else:
            config = init_config()

        if not confirm:
            confirm_delete = typer.confirm(
                f"Удалить сессии со статусом '{status}' старше {older_than_days} дней?"
            )
            if not confirm_delete:
                console.print("[yellow]Операция отменена[/yellow]")
                return

        asyncio.run(_cleanup(config, older_than_days, status))

    except Exception as e:
        console.print(f"[bold red]Ошибка:[/bold red] {e}")
        sys.exit(1)


async def _cleanup(config: Config, older_than_days: int, status: str):
    """Очистка данных."""
    from datetime import datetime, timedelta

    db = await init_db_manager(config)

    async with db.session() as db_session:
        repo = CrawlSessionRepository(db_session)

        # Дата отсечки
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)

        # Удаление
        deleted = await repo.delete_old_sessions(
            older_than=cutoff_date, status=status
        )

        console.print(f"[green]✓[/green] Удалено сессий: {deleted}")

    await close_db_manager()


@app.command()
def init(
    output: Path = typer.Option(
        "config.yaml", "--output", "-o", help="Файл для сохранения конфигурации"
    ),
):
    """
    Создать файл конфигурации по умолчанию.

    Примеры:
        crawler init
        crawler init --output my-config.yaml
    """
    try:
        # Копирование default.yaml
        import shutil

        default_config = Path(__file__).parent.parent / "config" / "default.yaml"

        if not default_config.exists():
            console.print("[red]Файл конфигурации по умолчанию не найден[/red]")
            sys.exit(1)

        shutil.copy(default_config, output)

        console.print(f"[green]✓[/green] Конфигурация создана: {output}")
        console.print("\n[dim]Отредактируйте файл и запустите:[/dim]")
        console.print(f"[cyan]crawler crawl https://example.com --config {output}[/cyan]")

    except Exception as e:
        console.print(f"[bold red]Ошибка:[/bold red] {e}")
        sys.exit(1)


@app.command()
def export(
    session_id: str = typer.Argument(..., help="ID сессии для экспорта"),
    format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Формат экспорта (json, csv, graphml)"
    ),
    output: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="Путь к выходному файлу"
    ),
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Путь к файлу конфигурации",
        exists=True,
    ),
    compress: bool = typer.Option(
        False,
        "--compress",
        help="Сжать файл (gzip)"
    ),
    pretty: bool = typer.Option(
        True,
        "--pretty/--compact",
        help="Красивое форматирование (только JSON)"
    ),
    split: bool = typer.Option(
        False,
        "--split",
        help="Разделить на несколько файлов (только CSV)"
    ),
):
    """
    Экспортировать результаты краулинга.

    Примеры:
        crawler export abc123 --format json --output results.json
        crawler export abc123 --format csv --split
        crawler export abc123 --format graphml --output graph.graphml
    """
    try:
        console.print("[bold blue]Export данных краулинга[/bold blue]\n")

        # Инициализация
        config = init_config(str(config_file) if config_file else None)
        db_manager = asyncio.run(init_db_manager(config))

        # Определить выходной файл
        if output is None:
            extensions = {
                "json": ".json",
                "csv": ".csv",
                "graphml": ".graphml"
            }
            output = Path(f"{session_id}{extensions.get(format, '.txt')}")

        # Выбрать экспортер
        if format == "json":
            exporter = JSONExporter(db_manager)
            asyncio.run(
                exporter.export(
                    session_id=session_id,
                    output_path=str(output),
                    pretty=pretty,
                    compress=compress
                )
            )

        elif format == "csv":
            exporter = CSVExporter(db_manager)
            asyncio.run(
                exporter.export(
                    session_id=session_id,
                    output_path=str(output),
                    split_by_type=split
                )
            )

        elif format == "graphml":
            exporter = GraphMLExporter(db_manager)
            asyncio.run(
                exporter.export(
                    session_id=session_id,
                    output_path=str(output),
                    max_nodes=10000
                )
            )

        else:
            console.print(f"[bold red]Неизвестный формат:[/bold red] {format}")
            console.print("\n[dim]Доступные форматы: json, csv, graphml[/dim]")
            sys.exit(1)

        console.print(f"\n[green]✓[/green] Экспорт завершён: [cyan]{output}[/cyan]")

        # Cleanup
        asyncio.run(close_db_manager(db_manager))

    except ValueError as e:
        console.print(f"[bold red]Ошибка:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Ошибка экспорта:[/bold red] {e}")
        sys.exit(1)


@app.command()
def analyze(
    session_id: str = typer.Argument(..., help="ID сессии для анализа"),
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Путь к файлу конфигурации",
        exists=True,
    ),
    content: bool = typer.Option(
        True,
        "--content/--no-content",
        help="Анализ контента и SEO"
    ),
    links: bool = typer.Option(
        True,
        "--links/--no-links",
        help="Анализ ссылок"
    ),
    stats: bool = typer.Option(
        True,
        "--stats/--no-stats",
        help="Статистика краулинга"
    ),
):
    """
    Анализировать результаты краулинга.

    Примеры:
        crawler analyze abc123
        crawler analyze abc123 --content --links
        crawler analyze abc123 --stats
    """
    try:
        console.print("[bold blue]Анализ результатов краулинга[/bold blue]\n")

        # Инициализация
        config = init_config(str(config_file) if config_file else None)
        db_manager = asyncio.run(init_db_manager(config))

        # Content анализ
        if content:
            console.print("[bold cyan]📊 Анализ контента и SEO[/bold cyan]")

            analyzer = ContentAnalyzer(db_manager)
            report = asyncio.run(analyzer.analyze(session_id))

            # Вывод результатов
            console.print(f"\nSEO Score: [bold green]{report.seo_score}[/bold green]/100")
            console.print(f"Всего проблем: {len(report.issues)}")

            # Группировка по severity
            severity_counts = report.summary
            if "severity_critical" in severity_counts:
                console.print(f"  [bold red]Critical:[/bold red] {severity_counts['severity_critical']}")
            if "severity_error" in severity_counts:
                console.print(f"  [bold yellow]Error:[/bold yellow] {severity_counts['severity_error']}")
            if "severity_warning" in severity_counts:
                console.print(f"  [dim]Warning:[/dim] {severity_counts['severity_warning']}")

            # Топ 10 проблем
            if report.issues:
                console.print("\n[bold]Топ проблем:[/bold]")
                for i, issue in enumerate(report.issues[:10], 1):
                    severity_color = {
                        "critical": "bold red",
                        "error": "yellow",
                        "warning": "dim",
                        "info": "dim"
                    }.get(issue.severity.value, "dim")
                    console.print(
                        f"  {i}. [{severity_color}]{issue.severity.value}[/{severity_color}]: "
                        f"{issue.message[:80]}"
                    )

        # Link анализ
        if links:
            console.print("\n[bold cyan]🔗 Анализ ссылок[/bold cyan]")

            extractor = LinkExtractor(db_manager)
            link_report = asyncio.run(extractor.analyze(session_id))

            console.print(f"\nВсего ссылок: {link_report.total_links}")
            console.print(f"  Внутренних: {link_report.internal_links}")
            console.print(f"  Внешних: {link_report.external_links}")
            console.print(f"Orphan pages: {len(link_report.orphan_pages)}")

            # Hub pages
            if link_report.hub_pages:
                console.print("\n[bold]Топ 5 Hub pages:[/bold]")
                for i, (url, count) in enumerate(link_report.hub_pages[:5], 1):
                    console.print(f"  {i}. {url[:60]}... ({count} исходящих)")

            # Authority pages
            if link_report.authority_pages:
                console.print("\n[bold]Топ 5 Authority pages:[/bold]")
                for i, (url, count) in enumerate(link_report.authority_pages[:5], 1):
                    console.print(f"  {i}. {url[:60]}... ({count} входящих)")

        # Статистика
        if stats:
            console.print("\n[bold cyan]📈 Статистика краулинга[/bold cyan]")

            calculator = StatsCalculator(db_manager)
            crawl_stats = asyncio.run(calculator.calculate(session_id))

            # Вывод сводки
            summary = calculator.get_summary(crawl_stats)
            console.print(f"\n{summary}")

        # Cleanup
        asyncio.run(close_db_manager(db_manager))

        console.print("\n[green]✓[/green] Анализ завершён")

    except ValueError as e:
        console.print(f"[bold red]Ошибка:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Ошибка анализа:[/bold red] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def cli_main():
    """Точка входа для CLI."""
    app()


if __name__ == "__main__":
    cli_main()
