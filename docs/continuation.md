# Continuation

## Что Уже Сделано

- Создан проект `/opt/workspace/projects/equipment-accounting`.
- Сохранена исходная постановка в `research/source_prompt.md`.
- Созданы стартовые документы в `docs/`.
- Выделены ключевые открытые вопросы.
- Зафиксированы рабочие решения в `docs/07_decisions.md`.
- `docs/05_mvp_plan.md` переписан как контрольный MVP-план: границы MVP, Definition of Done, текущие статусы, очередь M1-M5 и backlog после MVP.
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
- Маршруты начали использовать локальный `AuthProvider`:
  - `/equipment` доступен только центру;
  - `/region` для регионального пользователя показывает только его регион;
  - карточки чужих регионов запрещены для регионального пользователя;
  - действия центра доступны только центру;
  - в форме создания регион зафиксирован для пользователя филиала.
- В demo/database режиме пользователя можно переключить через `?as=center`, `?as=region24`, `?as=region08`, `?as=region31`, заголовок `x-demo-user` или cookie `demo_user`.
- Реализован простой `/login` для demo/database режима:
  - выбор пользователя из таблицы `users`;
  - установка cookie `demo_user`;
  - `/logout` сбрасывает cookie;
  - вход сделан отдельными кнопками пользователей;
  - после входа филиал сразу попадает в `/region`, центр - в `/equipment`;
  - главная показывает текущего пользователя и ведёт центр/филиал на разные рабочие экраны.
- В форме создания `/equipment/new` динамические поля теперь показываются только для выбранного типа оборудования; поля скрытых типов отключаются и не отправляются.
- В карточке `/equipment/{id}` реализовано редактирование фото:
  - дозагрузка фото;
  - изменение назначения фото;
  - удаление фото вместе с файлами оригинала и миниатюры;
  - изменение порядка показа;
  - проверка `row_version`;
  - запись audit log.
- На главной странице убраны прямые действия `Добавить оборудование` и `Выйти`.
- Добавлен раздел `/documentation`, который показывает актуальные документы из `docs/`:
  - бизнес-процесс системы;
  - план реализации MVP.
- Просмотр документов в `/documentation` рендерит markdown как HTML: заголовки, списки, таблицы, code blocks и inline code.
- Реализован admin-раздел `/admin` для роли `center_admin`:
  - список, создание и редактирование пользователей;
  - выбор роли `region`, `center`, `center_admin`;
  - привязка регионального пользователя к региону;
  - включение/выключение пользователя;
  - список, создание и редактирование регионов;
  - включение/выключение региона;
  - вход пользователя `admin` ведёт сразу в `/admin`.
- В `/admin` реализовано управление типами оборудования и динамическими полями:
  - список, создание и редактирование типов;
  - включение/выключение типа;
  - список полей по каждому типу;
  - создание и редактирование поля;
  - тип значения, обязательность, фильтруемость, порядок, подсказка;
  - варианты значений для `select` и `multiselect`;
  - включение/выключение поля без удаления исторических данных.
- Реестр центра `/equipment` расширен в рамках M3:
  - фильтр по региону;
  - фильтр по типу оборудования;
  - фильтр по местонахождению;
  - фильтр по статусу продажи;
  - фильтры по активным динамическим полям с `is_filterable=true`;
  - экспорт CSV по текущим фильтрам через `/equipment/export.csv`;
  - экспорт ограничен 10 000 записей.
- В карточке реализованы маршруты M4:
  - сохранение оценки, цены продажи и описания для продажи;
  - подготовка к продаже;
  - публикация;
  - фиксация продажи;
  - согласование списания;
  - перевод к утилизации;
  - фиксация утилизации;
  - архивация;
  - soft delete.

## Точка Возврата На 2026-06-16

- Рабочая ветка: `dev`.
- Текущий опубликованный коммит: `57048c4 Publish tech stack documentation`.
- Ветка `dev` синхронизирована с `origin/dev`.
- MVP завершён и помечен тегом `mvp-2026-06-14` на коммите `588e92a`.
- После MVP выполнена UI-полировка региона, центра и admin-раздела.
- Добавлен `DESIGN.md` как локальный стандарт спокойного операционного интерфейса.
- Центр `/equipment`: очереди вынесены выше фильтров, видимым оставлен компактный поиск, остальные фильтры спрятаны в раскрываемый блок `Фильтры`.
- Admin `/admin`: верхняя навигация упрощена, добавлена сводка, редактируемые списки свернуты в раскрываемые секции.
- Документация `/documentation`: опубликованы бизнес-процесс, MVP-план, инструкция оператора/admin и техстек системы.
- Dev-сервер оставлен запущенным на `0.0.0.0:8010`; предупреждения `Invalid HTTP request received` от внешних сканеров можно игнорировать.

Команда приёмки, которая прошла:

```bash
.venv/bin/python -c "from scripts.check_mvp_acceptance import main; raise SystemExit(main())"
```

Проверенный чек-лист M5:

1. Smoke-тест основных страниц: `/health`, `/login`, `/region`, `/equipment`, `/equipment/new`, `/equipment/{id}`.
2. Проверка доступа регионов и центра.
3. Проверка защиты от двойной отправки формы.
4. Проверка конфликта `row_version`.
5. Проверка загрузки, назначения, удаления и сортировки фото.
6. Проверка создания 60 параллельных карточек.
7. Проверка работы центра со списком во время массового создания.
8. Обновление `README.md`.
9. Инструкция для admin/оператора.
10. Финальное обновление `docs/continuation.md`.
11. Тестовые записи с префиксом `MVP_ACCEPTANCE_` очищены.

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
http://185.168.208.240:8010/equipment/1/edit
http://185.168.208.240:8010/region
http://185.168.208.240:8010/login
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
57048c4 Publish tech stack documentation
e2dd1f6 Make registry filters compact
6e999fa Add design guide and simplify registry workspace
ff482a3 Calm admin interface layout
30f30b4 Simplify admin navigation
40ff6f3 Handle empty registry filter ids
cc30970 Harden center filter layout rendering
20fc97a Refine center registry filters
36a336e Fix center registry filter layout
55e6574 Simplify regional workspace navigation
588e92a Complete MVP acceptance stabilization
fb54f57 Update MVP continuation checkpoint
8dbce92 Add sale and writeoff route actions
e5117b6 Add registry filters and CSV export
fe42e1b Add admin equipment type management
6ab8667 Add admin user and region management
```

## Точка Возврата На 2026-06-17: Исследование Оценщика

MVP не трогать. Вся работа по оценщику велась как будущий дополнительный модуль и research.

Созданы документы:

```text
docs/14_price_monitoring_module.md
docs/15_price_monitoring_mvp_plan.md
docs/16_price_monitoring_decisions.md
docs/17_price_monitoring_developer_handoff.md
docs/18_avito_data_source_discovery.md
docs/19_avito_data_source_discovery_results.md
docs/20_intermediary_avito_data_services.md
docs/21_avito_vendor_spike_requests.md
docs/22_avito_self_service_technical_spike.md
docs/23_apify_avito_spike_results.md
docs/24_free_avito_source_options.md
docs/25_agentic_browser_avito_mode.md
docs/26_self_hosted_avito_background_monitoring.md
docs/27_duff89_parser_avito_audit.md
docs/28_duff89_parser_avito_poc_results.md
docs/29_clean_room_avito_parser_design.md
docs/30_clean_room_avito_parser_poc_results.md
docs/31_price_monitoring_research_timeline_2026-06-17.md
docs/32_price_monitoring_implementation_plan.md
docs/33_price_monitoring_endurance_day_1.md
docs/34_price_monitoring_endurance_day_2_plan.md
docs/35_price_monitoring_database_design.md
docs/36_price_monitoring_gate_acceptance.md
docs/38_price_monitoring_day2_operator_runbook.md
docs/39_price_monitoring_risk_and_decision_matrix.md
```

Ключевые решения:

- Официальный API Avito для поиска публичных объявлений по рынку не найден.
- Официальные API Avito относятся к управлению своими объявлениями, статистике, продвижению и связанным сервисам, но не к поиску чужих объявлений для оценки рынка.
- Прямой простой запрос к Avito с сервера ранее давал `HTTP 429` / CAPTCHA.
- Платные источники данных исключены как production-вариант:
  - Apify;
  - Bright Data;
  - MarketParser;
  - ShopAPIS;
  - и аналоги.
- Apify технически подтвердил, что данные Avito можно получить, но получил статус `no_go_paid_service`.
- Exa/SERP API не подходят как источник daily snapshot, потому что это поисковые/индексные результаты, а не структурированный Avito listing source.
- Готовый open-source `Duff89/parser_avito` проверен в `/tmp`:
  - первый one-shot run без cookies/proxy получил 50 объявлений;
  - сохранил 49 в Excel;
  - второй run показал, что parser фильтрует уже виденные объявления и поэтому не подходит как daily full snapshot из коробки;
  - у проекта не найден явный LICENSE, код нельзя переносить в продукт.
- Принято решение делать собственный clean-room parser-worker как research POC, не копируя чужой код.

Research POC:

```text
research/avito-monitor-worker-poc/
```

Содержит:

```text
README.md
config/search_jobs.example.json
src/worker.py
.gitignore
```

Статус POC:

```text
pipeline_works_http_unstable
```

Что подтверждено:

- clean-room worker может извлечь 50 карточек из сохранённого live HTML Avito;
- нормализация в JSON работает;
- raw snapshot сохраняется до фильтрации;
- фильтр делит объявления на `relevant`, `unknown`, `rejected`;
- snapshot считается только по `relevant`.

Последний offline-пересчёт по сохранённому HTML:

```text
raw: 50
normalized: 50
relevant: 37
unknown: 3
rejected: 10
min_price: 15000
max_price: 65000
median_price: 23995
```

Что не подтверждено:

- стабильный live HTTP доступ без cookies/proxy;
- production-надежность;
- работа по 3-5 позициям;
- endurance test 3-5 дней;
- качество фильтров для всех категорий.

Важное ограничение:

```text
Не делать частые live-запросы к Avito.
```

Следующий безопасный план:

1. Не запускать live Avito parser часто.
2. Следующий live run делать не чаще 1 раза в день.
3. Расширить research config до 3 позиций только перед endurance test.
4. Endurance test: 3 позиции, 1 запуск в день, 3-5 дней, без cookies/proxy.
5. По итогам выбрать:
   - `go_worker_prototype`;
   - `hold_http_unstable`;
   - `browser_profile_research`.

Реализация разложена в отдельный инженерный план:

```text
docs/32_price_monitoring_implementation_plan.md
```

Главное правило плана: до `go_worker_prototype` после endurance test не переносить модуль в основное приложение и не начинать миграции/UI `/pricing`.

Endurance day 1 выполнен 2026-06-18:

```text
run_id: 20260618T075423Z
status: partial_success_http_unstable
kyocera_m2040dn: HTTP 403 blocked
lenovo_t14: HTTP 200 success, raw 50, relevant 30, median 29450
dell_r740: HTTP 200 no_data
```

Решение после day 1: `continue_endurance_with_caution`.

Offline-анализ day 1 уточнил:

- `dell_r740` был не реальным `no_data`, а `page_not_found` в HTML при HTTP 200;
- причина: неподходящий category URL `/all/servernoe_oborudovanie`;
- для day 2 URL заменён на более широкий `/all?q=Dell+PowerEdge+R740`;
- worker доработан: future `page_not_found` будет `parser_error`, а не `no_data`;
- добавлена команда offline-анализа:

```bash
.venv/bin/python src/worker.py --analyze-run runs/{run_id}
.venv/bin/python src/worker.py --write-markdown-report runs/{run_id} --output runs/{run_id}/offline_report.md
.venv/bin/python src/worker.py --write-endurance-doc runs/{run_id} --output ../../docs/34_price_monitoring_endurance_day_2.md --day 2 --date 2026-06-19
.venv/bin/python src/worker.py --write-gate-summary --runs-dir runs --output ../../docs/37_price_monitoring_gate_summary.md
.venv/bin/python src/worker.py --from-html runs/{run_id}/{job_code}/raw_pages/page_1.html --job-code {job_code} --config config/search_jobs.json --runs-dir runs
.venv/bin/python src/worker.py --dry-run-config --config config/search_jobs.json
.venv/bin/python src/worker.py --preflight --config config/search_jobs.json --runs-dir runs
```

- добавлены offline-тесты POC:

```bash
.venv/bin/python -m unittest discover -s tests
```

- добавлен guard от повторного live run в тот же UTC-день:

```text
blocked_by_same_day_guard
```

Важно: не делать повторный live Avito run 2026-06-18. Следующий live run - 2026-06-19 или позже, один запуск в день.

Офлайн-подготовка после day 1:

- подготовлен предварительный проект БД без миграций: `docs/35_price_monitoring_database_design.md`;
- подготовлен gate/acceptance checklist: `docs/36_price_monitoring_gate_acceptance.md`;
- подготовлен operator runbook для day 2: `docs/38_price_monitoring_day2_operator_runbook.md`;
- подготовлена risk/decision matrix: `docs/39_price_monitoring_risk_and_decision_matrix.md`;
- правило не изменилось: backend-модели, Alembic и UI `/pricing` не начинать до решения `go_worker_prototype`.

## Точка Возврата На 2026-06-17: Демо-Меню

Для демо сценария "регионы - центр" скрыт администратор центра из видимого списка входа `/login`.

Изменение:

```text
app/api/auth.py
```

Что сделано:

- пользователь с ролью `center_admin` больше не показывается на странице `/login`;
- маршруты `/admin` не отключены;
- прямой доступ к `/admin?as=admin` сохранён;
- `equipment-accounting.service` перезапущен;
- проверено:
  - `/login` показывает регионы и `Пользователь центра`;
  - `/admin?as=admin` открывается со статусом `200`.

Причина:

```text
Раздел администратора центра сложный и перегружает демо. Пока заходить в него по прямой ссылке, позже можно вернуть в меню.
```

## Как Продолжать

Следующий осмысленный шаг:

1. Проверить `git status`.
2. Проверить, что dev-сервер доступен на `http://185.168.208.240:8010/health`.
3. Если интерфейс “не поменялся”, сначала проверить внешний HTML/CSS через `curl` и версию query-string у `/static/app.css`.
4. Перед новыми UI-правками читать `DESIGN.md`.
5. Если пользователь предлагает новую доработку, оценить её как post-MVP, если она не блокирует показ/пилот.
6. Если доработка нужна для демо стейкхолдерам, делать точечно и пушить в `origin/dev`.
7. Если бизнес-решения меняются, сначала обновить `docs/07_decisions.md` и `docs/11_business_processes.md`, затем синхронизировать требования, архитектуру, БД и `technical_specification.md`.

## Принятые Предварительные Решения

- Стек фиксирован: FastAPI, PostgreSQL, SQLAlchemy, Alembic, Jinja2, HTMX.
- Динамические поля: `equipment.attributes JSONB` + описание полей в `equipment_type_fields`.
- Фото: файловая система в MVP, абстракция под S3.
- Авторизация: простой провайдер в MVP, абстракция под Keycloak.
- Нужен audit log, хотя в исходной постановке он не был явно обязательным.
