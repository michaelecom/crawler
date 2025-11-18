# Установка

Детальное руководство по установке Enterprise Web Crawler.

## Системные требования

### Минимальные

- **Python**: 3.12+
- **RAM**: 2 GB
- **Диск**: 1 GB свободного места
- **ОС**: Linux, macOS, Windows

### Рекомендуемые

- **Python**: 3.14+
- **RAM**: 8 GB+
- **Диск**: 10 GB+ (для больших краулинг-сессий)
- **ОС**: Linux (Ubuntu 22.04+, Debian 11+)

## Методы установки

### 1. UV (Рекомендуется)

UV — современный быстрый менеджер пакетов для Python.

```bash
# Установка UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Клонирование репозитория
git clone https://github.com/yourusername/crawler.git
cd crawler

# Установка проекта
uv pip install -e .

# Установка с dev зависимостями
uv pip install -e ".[dev]"
```

### 2. pip

```bash
# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/macOS
# или
venv\Scripts\activate  # Windows

# Установка
pip install -e .

# Или из requirements
pip install -r requirements.txt
```

### 3. Docker

#### Простой способ

```bash
# Через Makefile
make quickstart
```

#### Ручной способ

```bash
# Сборка образа
docker-compose build

# Запуск
docker-compose up -d

# Проверка
docker-compose ps
```

## Установка зависимостей

### Playwright (для JavaScript)

Если планируете использовать JavaScript рендеринг:

```bash
# Установка browsers
playwright install chromium firefox webkit

# Установка system dependencies
playwright install-deps
```

### PostgreSQL (опционально)

Для production рекомендуется PostgreSQL:

```bash
# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# macOS
brew install postgresql

# Или через Docker
docker run -d \
  --name crawler_postgres \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 \
  postgres:16-alpine
```

### Redis (опционально)

Для распределённого краулинга:

```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis

# Или через Docker
docker run -d \
  --name crawler_redis \
  -p 6379:6379 \
  redis:7-alpine
```

## Проверка установки

```bash
# Проверка CLI
crawler --version

# Проверка imports
python -c "from webcrawler import Crawler; print('OK')"

# Запуск тестов
pytest tests/ -v

# Проверка линтера
ruff check webcrawler/
```

## Конфигурация

### Создание конфигурации

```bash
# Копирование примера
cp config/default.yaml config.yaml

# Или через CLI
crawler init --output config.yaml
```

### Environment variables

Создайте `.env` файл:

```bash
cp .env.example .env
```

Отредактируйте `.env`:

```bash
# Database
CRAWLER_DB_TYPE=postgresql
CRAWLER_DB_HOST=localhost
CRAWLER_DB_PORT=5432
CRAWLER_DB_NAME=webcrawler
CRAWLER_DB_USER=crawler
CRAWLER_DB_PASSWORD=secure_password

# Redis
CRAWLER_REDIS_HOST=localhost
CRAWLER_REDIS_PORT=6379

# Logging
CRAWLER_LOG_LEVEL=INFO
```

## Инициализация базы данных

```bash
# Через CLI
crawler init-db

# Или через Python
python -c "
import asyncio
from webcrawler.utils.config import init_config
from webcrawler.storage.database import init_db_manager

async def init():
    config = init_config()
    db = await init_db_manager(config, create_tables=True)
    print('Database initialized')
    await db.close()

asyncio.run(init())
"
```

## Troubleshooting

### Ошибки при установке Playwright

```bash
# Переустановка browsers
playwright install --force chromium

# Проверка system dependencies
playwright install-deps --dry-run
```

### Ошибки импорта

```bash
# Проверка PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Переустановка
pip install -e . --force-reinstall
```

### Ошибки БД

```bash
# SQLite: проверка прав
ls -la data/

# PostgreSQL: проверка подключения
psql -h localhost -U crawler -d webcrawler
```

## Следующие шаги

- [Быстрый старт](quickstart.md)
- [Конфигурация](configuration.md)
- [Базовое использование](basic_usage.md)
