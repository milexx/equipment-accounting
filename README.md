# Equipment Accounting

Веб-приложение для централизованного учёта неиспользуемого оборудования: регионы заводят карточки, центр проверяет данные, принимает решения по диагностике, списанию, утилизации, оценке и продаже.

## Статус

MVP функционально собран. Текущий контрольный этап - приёмка и стабилизация M5.

Закрыто:

- вход в demo/database режиме для ролей `region`, `center`, `center_admin`;
- рабочее место региона `/region`;
- реестр центра `/equipment` с очередями, фильтрами и CSV-экспортом;
- создание и редактирование карточек с динамическими полями;
- загрузка, назначение, удаление и сортировка фото;
- optimistic locking через `row_version`;
- действия центра по проверке, диагностике, списанию, утилизации, оценке, продаже, архиву и soft delete;
- admin-раздел `/admin` для пользователей, регионов, типов оборудования и полей;
- раздел документации `/documentation` с бизнес-процессом и MVP-планом.

## Стек

- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Jinja2
- HTMX-ready server-rendered UI
- Pillow для обработки фото

## Локальный Запуск

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/alembic upgrade head
.venv/bin/python scripts/seed_demo.py
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8010
```

Для внешнего доступа dev-сервер в текущем окружении нужно запускать вне sandbox.

## Демо-Пользователи

Вход: `http://127.0.0.1:8010/login`

- `admin` - администратор центра, открывает `/admin`;
- `center` - сотрудник центра, открывает `/equipment`;
- `region24`, `region08`, `region31` - пользователи регионов, открывают `/region`.

В demo/database режиме пользователя также можно задать через cookie `demo_user`, query-параметр `?as=...` или заголовок `x-demo-user`.

## Основные URL

- `/` - главная;
- `/login` - вход;
- `/region` - рабочее место региона;
- `/equipment` - реестр центра;
- `/equipment/new` - создание карточки;
- `/equipment/{id}` - карточка оборудования;
- `/admin` - администрирование;
- `/documentation` - документация;
- `/health` - healthcheck.

## Приёмка MVP

Перед запуском проверки должен работать dev-сервер на `http://127.0.0.1:8010`.

```bash
.venv/bin/python -c "from scripts.check_mvp_acceptance import main; raise SystemExit(main())"
```

Проверка создаёт временные карточки с префиксом `MVP_ACCEPTANCE_`, проверяет основные сценарии и удаляет тестовые данные.

Дополнительные технические проверки:

```bash
.venv/bin/python -m compileall app scripts
.venv/bin/ruff check app scripts
```

## Документы

- `docs/05_mvp_plan.md` - актуальный план MVP и правило обработки новых идей;
- `docs/11_business_processes.md` - бизнес-процесс системы;
- `docs/12_operator_admin_guide.md` - инструкция оператора и администратора;
- `docs/13_tech_stack.md` - описание техстека системы;
- `docs/technical_specification.md` - техническое задание;
- `docs/continuation.md` - точка возврата для продолжения разработки.
