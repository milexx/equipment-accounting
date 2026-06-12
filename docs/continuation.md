# Continuation

## Что Уже Сделано

- Создан проект `/opt/workspace/projects/equipment-accounting`.
- Сохранена исходная постановка в `research/source_prompt.md`.
- Созданы стартовые документы в `docs/`.
- Выделены ключевые открытые вопросы.
- Зафиксированы рабочие решения в `docs/07_decisions.md`.
- Собрано единое ТЗ в `docs/technical_specification.md`.
- Финализированы `docs/02_requirements.md`, `docs/03_architecture.md` и `docs/04_database.md`.
- Зафиксирован подход к разработке, демо и релизам в `docs/10_development_release.md`.
- Описаны бизнес-процессы системы в `docs/11_business_processes.md`.

## Как Продолжать

Следующий осмысленный шаг:

1. Проверить git status.
2. Начинать scaffold FastAPI-приложения.
3. Поднять локальное демо в этом проекте.
4. Если бизнес-решения меняются, сначала обновить `docs/07_decisions.md`, затем синхронизировать требования, архитектуру, БД и `technical_specification.md`.

## Принятые Предварительные Решения

- Стек фиксирован: FastAPI, PostgreSQL, SQLAlchemy, Alembic, Jinja2, HTMX.
- Динамические поля: `equipment.attributes JSONB` + описание полей в `equipment_type_fields`.
- Фото: файловая система в MVP, абстракция под S3.
- Авторизация: простой провайдер в MVP, абстракция под Keycloak.
- Нужен audit log, хотя в исходной постановке он не был явно обязательным.
