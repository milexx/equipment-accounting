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
- Инициализирован git-репозиторий, рабочая ветка `dev`.
- Создана локальная PostgreSQL-база `equipment_accounting_dev`, пользователь `equipment_app`.
- Поднят FastAPI scaffold с SQLAlchemy, Alembic, Jinja2.
- Применены миграции до `20260613_0004`.
- Добавлены demo seed-данные.
- Реализован реестр `/equipment`.
- Реализована карточка `/equipment/{id}`.
- Реализована форма добавления `/equipment/new`.
- Добавлено базовое поле `location` / местонахождение.
- Добавлена защита от двойной отправки формы.
- Подключена загрузка фото при создании оборудования:
  - общий вид;
  - шильдик / серийный номер;
  - фото дефекта.
- Фото сохраняются в `var/photos`, раздаются через `/media/photos`, для карточки создаются миниатюры.
- Для нерабочего оборудования при отправке на проверку требуется минимум одно фото дефекта.
- Исправлен ORM cascade для фото: удаление карточки с фото не должно падать на `equipment_photos.equipment_id`.
- Зафиксировано обязательное требование конкурентной работы: 60+ региональных пользователей могут одновременно заводить оборудование, центр параллельно работает со списками и карточками.
- В БД добавлено поле `equipment.row_version` для будущего optimistic locking при редактировании и смене статусов.
- Реализованы действия центра в карточке:
  - принять;
  - вернуть на доработку с комментарием;
  - отправить на диагностику;
  - направить на списание;
  - направить на оценку;
  - подготовить к продаже.
- Действия центра проверяют `row_version`, меняют статус атомарно и пишут минимальный audit log.
- Реализованы рабочие очереди центра в реестре:
  - все;
  - на проверке;
  - доработка;
  - диагностика;
  - списание;
  - оценка / продажа.
- Очереди имеют счетчики и фильтруют список через `queue=...`.
- Реализован демо-интерфейс филиала `/region`:
  - выбор филиала для демо-режима;
  - крупный переход к добавлению оборудования;
  - счетчики “Все мои”, “Черновики”, “Отправлено в центр”, “Вернули на доработку”, “Принято центром”;
  - короткий список последних записей филиала.
- Реализовано редактирование карточки `/equipment/{id}/edit`:
  - основные поля;
  - местонахождение;
  - состояние и описание поломки;
  - комментарий;
  - динамические поля выбранного типа;
  - защита `row_version` от параллельного перетирания;
  - запись audit log;
  - исправление записи из “Доработки” можно сразу сохранить и отправить в центр.
- Keycloak не интегрируется в MVP, оставлена заглушка `AuthProvider`.
- Добавлена роль `center_admin` для будущего управления регионами и учётками.
- Текущие auth-provider режимы: `demo` и `database`; `keycloak` зарезервирован и явно не реализован.

## Текущее Демо

Внешний URL:

```text
http://185.168.208.240:8010/
```

Рабочие страницы:

```text
http://185.168.208.240:8010/equipment
http://185.168.208.240:8010/equipment/new
http://185.168.208.240:8010/equipment/1
http://185.168.208.240:8010/prototype
http://185.168.208.240:8010/health
```

Dev-сервер запускается так:

```bash
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8010
```

Из-за sandbox сервер для внешнего доступа нужно запускать вне sandbox / с escalation.

## Текущая База

Локальный PostgreSQL:

```text
database: equipment_accounting_dev
user: equipment_app
```

Текущие основные таблицы:

```text
regions
users
equipment_types
equipment_type_fields
equipment
equipment_photos
equipment_audit_log
```

Текущие demo-записи:

```text
1 Lenovo ThinkPad T14
2 Kyocera ECOSYS M2040dn
3 Dell PowerEdge R740
4 Тестовый монитор
5 HP M426
```

## Последние Важные Коммиты

```text
55a1fd4 Scaffold FastAPI app and dev database
b7e91ef Add equipment registry screen
a29b818 Document business processes
09b7a5b Add equipment detail page
9065235 Add equipment location field
b0bc77a Add equipment creation form
e0d40b5 Prevent duplicate equipment form submissions
614862e Update project continuation context
ac49b8b Add equipment photo upload
2aa96b6 Document concurrent usage requirements
e8610ab Add center equipment actions
```

## Как Продолжать

Следующий осмысленный шаг:

1. Проверить `git status`.
2. Проверить, что dev-сервер доступен на `http://185.168.208.240:8010/health`.
3. Следующий продуктовый шаг: связать `/region` и `/equipment` с локальным `AuthProvider`: регион брать из текущего пользователя, selector убрать для обычного филиала.
4. Отдельный UX-шаг: показывать в форме создания только поля выбранного типа оборудования, а не все fieldset сразу.
5. Для фото добавить отдельное редактирование: дозагрузка, удаление и порядок.
6. Если бизнес-решения меняются, сначала обновить `docs/07_decisions.md` и `docs/11_business_processes.md`, затем синхронизировать требования, архитектуру, БД и `technical_specification.md`.

## Принятые Предварительные Решения

- Стек фиксирован: FastAPI, PostgreSQL, SQLAlchemy, Alembic, Jinja2, HTMX.
- Динамические поля: `equipment.attributes JSONB` + описание полей в `equipment_type_fields`.
- Фото: файловая система в MVP, абстракция под S3.
- Авторизация: простой провайдер в MVP, абстракция под Keycloak.
- Нужен audit log, хотя в исходной постановке он не был явно обязательным.
