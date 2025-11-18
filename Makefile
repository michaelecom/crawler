# Makefile для Enterprise Web Crawler
# Упрощает работу с Docker, тестами и развёртыванием

.PHONY: help build up down restart logs test lint format clean install dev prod

# По умолчанию показываем help
.DEFAULT_GOAL := help

# Цвета для вывода
CYAN := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m  # No Color

# Help
help: ## Показать это сообщение
	@echo "${CYAN}Enterprise Web Crawler - Makefile Commands${NC}"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "${GREEN}%-20s${NC} %s\n", $$1, $$2}'
	@echo ""

# Installation
install: ## Установить зависимости через UV
	@echo "${CYAN}Установка зависимостей...${NC}"
	uv pip install -e .
	@echo "${GREEN}✓ Зависимости установлены${NC}"

install-dev: ## Установить зависимости для разработки
	@echo "${CYAN}Установка dev зависимостей...${NC}"
	uv pip install -e ".[dev]"
	playwright install chromium firefox
	@echo "${GREEN}✓ Dev зависимости установлены${NC}"

# Docker - Development
dev: ## Запустить dev окружение
	@echo "${CYAN}Запуск dev окружения...${NC}"
	docker-compose -f docker-compose.dev.yml up -d
	@echo "${GREEN}✓ Dev окружение запущено${NC}"
	@echo "${YELLOW}Войти в контейнер: make shell${NC}"

dev-down: ## Остановить dev окружение
	@echo "${CYAN}Остановка dev окружения...${NC}"
	docker-compose -f docker-compose.dev.yml down
	@echo "${GREEN}✓ Dev окружение остановлено${NC}"

shell: ## Войти в dev контейнер
	docker-compose -f docker-compose.dev.yml exec crawler-dev bash

# Docker - Production
build: ## Собрать Docker образ
	@echo "${CYAN}Сборка Docker образа...${NC}"
	docker-compose build
	@echo "${GREEN}✓ Образ собран${NC}"

up: ## Запустить все сервисы
	@echo "${CYAN}Запуск сервисов...${NC}"
	docker-compose up -d
	@echo "${GREEN}✓ Сервисы запущены${NC}"
	@echo "${YELLOW}Просмотр логов: make logs${NC}"

down: ## Остановить все сервисы
	@echo "${CYAN}Остановка сервисов...${NC}"
	docker-compose down
	@echo "${GREEN}✓ Сервисы остановлены${NC}"

restart: down up ## Перезапустить все сервисы

logs: ## Показать логи всех сервисов
	docker-compose logs -f

logs-crawler: ## Показать логи краулера
	docker-compose logs -f crawler

ps: ## Показать статус контейнеров
	docker-compose ps

# Testing
test: ## Запустить тесты
	@echo "${CYAN}Запуск тестов...${NC}"
	pytest tests/ -v --cov=webcrawler --cov-report=html
	@echo "${GREEN}✓ Тесты завершены${NC}"

test-unit: ## Запустить unit тесты
	@echo "${CYAN}Запуск unit тестов...${NC}"
	pytest tests/unit/ -v
	@echo "${GREEN}✓ Unit тесты завершены${NC}"

test-integration: ## Запустить интеграционные тесты
	@echo "${CYAN}Запуск интеграционных тестов...${NC}"
	pytest tests/integration/ -v
	@echo "${GREEN}✓ Интеграционные тесты завершены${NC}"

test-watch: ## Запустить тесты в watch режиме
	pytest-watch tests/ -v

# Code Quality
lint: ## Проверить код линтером
	@echo "${CYAN}Проверка кода...${NC}"
	ruff check webcrawler/
	mypy webcrawler/
	@echo "${GREEN}✓ Код проверен${NC}"

format: ## Отформатировать код
	@echo "${CYAN}Форматирование кода...${NC}"
	black webcrawler/ tests/
	ruff check --fix webcrawler/
	@echo "${GREEN}✓ Код отформатирован${NC}"

type-check: ## Проверить типы с mypy
	@echo "${CYAN}Проверка типов...${NC}"
	mypy webcrawler/ --strict
	@echo "${GREEN}✓ Типы проверены${NC}"

# Database
db-init: ## Инициализировать базу данных
	@echo "${CYAN}Инициализация БД...${NC}"
	crawler init-db
	@echo "${GREEN}✓ БД инициализирована${NC}"

db-migrate: ## Выполнить миграции
	@echo "${CYAN}Миграции БД...${NC}"
	alembic upgrade head
	@echo "${GREEN}✓ Миграции выполнены${NC}"

db-reset: ## Сбросить базу данных
	@echo "${RED}ВНИМАНИЕ: Все данные будут удалены!${NC}"
	@read -p "Продолжить? [y/N] " -n 1 -r; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		crawler reset-db; \
		echo "${GREEN}✓ БД сброшена${NC}"; \
	fi

# Cleanup
clean: ## Очистить временные файлы
	@echo "${CYAN}Очистка временных файлов...${NC}"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	@echo "${GREEN}✓ Очистка завершена${NC}"

clean-all: clean ## Полная очистка (включая volumes)
	@echo "${CYAN}Полная очистка...${NC}"
	docker-compose down -v --remove-orphans
	docker-compose -f docker-compose.dev.yml down -v --remove-orphans
	rm -rf webcrawler/data/*.db
	rm -rf logs/*.log
	@echo "${GREEN}✓ Полная очистка завершена${NC}"

# Documentation
docs: ## Сгенерировать документацию
	@echo "${CYAN}Генерация документации...${NC}"
	cd docs && make html
	@echo "${GREEN}✓ Документация сгенерирована${NC}"
	@echo "${YELLOW}Открыть: docs/_build/html/index.html${NC}"

docs-serve: docs ## Запустить dev сервер для документации
	@echo "${CYAN}Запуск сервера документации...${NC}"
	cd docs/_build/html && python -m http.server 8080

# CI/CD
ci: lint test ## Запустить CI проверки локально

pre-commit: format lint test ## Запустить pre-commit проверки

# Monitoring
monitoring-up: ## Запустить Prometheus и Grafana
	@echo "${CYAN}Запуск мониторинга...${NC}"
	docker-compose --profile monitoring up -d
	@echo "${GREEN}✓ Мониторинг запущен${NC}"
	@echo "${YELLOW}Prometheus: http://localhost:9091${NC}"
	@echo "${YELLOW}Grafana: http://localhost:3000 (admin/admin)${NC}"

monitoring-down: ## Остановить мониторинг
	@echo "${CYAN}Остановка мониторинга...${NC}"
	docker-compose --profile monitoring down
	@echo "${GREEN}✓ Мониторинг остановлен${NC}"

# Quick start
quickstart: build up ## Быстрый старт (build + up)
	@echo "${GREEN}✓ Crawler готов к использованию${NC}"
	@echo ""
	@echo "${CYAN}Доступные сервисы:${NC}"
	@echo "  Web UI:      http://localhost:8000"
	@echo "  Prometheus:  http://localhost:9090"
	@echo "  PgAdmin:     http://localhost:5050"
	@echo ""
	@echo "${YELLOW}Просмотр логов: make logs${NC}"
	@echo "${YELLOW}Остановка:      make down${NC}"

# Version
version: ## Показать версию
	@crawler --version
