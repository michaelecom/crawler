# Dockerfile для Enterprise Web Crawler
# Multi-stage build для оптимизации размера образа

# Stage 1: Base - установка зависимостей
FROM python:3.14-slim as base

# Метаданные
LABEL maintainer="Enterprise Web Crawler"
LABEL description="Высокопроизводительный веб-краулер для анализа сайтов"

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    gcc \
    g++ \
    make \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libjpeg-dev \
    libpng-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Установка Playwright dependencies
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Установка UV package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Рабочая директория
WORKDIR /app

# Копирование файлов зависимостей
COPY pyproject.toml README.md ./

# Stage 2: Dependencies - установка Python зависимостей
FROM base as dependencies

# Установка зависимостей через UV
RUN uv pip install --system --no-cache-dir .

# Установка Playwright browsers
RUN playwright install chromium firefox
RUN playwright install-deps

# Stage 3: Development - для разработки
FROM dependencies as development

# Установка dev зависимостей
RUN uv pip install --system --no-cache-dir -e ".[dev]"

# Копирование исходного кода
COPY . .

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV CRAWLER_ENV=development

# Порты
EXPOSE 8000 9090 8765

# Команда по умолчанию
CMD ["crawler", "--help"]

# Stage 4: Production - оптимизированный образ
FROM python:3.14-slim as production

# Системные зависимости (минимальный набор)
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    libjpeg62-turbo \
    libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

# Playwright runtime dependencies
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Создание непривилегированного пользователя
RUN useradd -m -u 1000 crawler && \
    mkdir -p /app /data /logs /exports && \
    chown -R crawler:crawler /app /data /logs /exports

WORKDIR /app

# Копирование зависимостей из stage dependencies
COPY --from=dependencies /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin
COPY --from=dependencies /root/.cache/ms-playwright /home/crawler/.cache/ms-playwright

# Копирование исходного кода
COPY --chown=crawler:crawler . .

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV CRAWLER_ENV=production
ENV PATH="/home/crawler/.local/bin:$PATH"

# Переключение на непривилегированного пользователя
USER crawler

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD crawler --version || exit 1

# Порты
EXPOSE 8000 9090 8765

# Volumes для данных
VOLUME ["/data", "/logs", "/exports"]

# Команда по умолчанию
CMD ["crawler", "--help"]
