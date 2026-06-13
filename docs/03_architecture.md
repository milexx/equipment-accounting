# Архитектура

Документ фиксирует финальную архитектуру MVP.

## 1. Стек

- Python 3.11+
- FastAPI
- PostgreSQL 15+
- SQLAlchemy 2.0
- Alembic
- Jinja2
- HTMX
- Минимальный CSS
- Pillow или совместимая библиотека для превью
- Файловая система для фото в MVP

Стек выбран так, чтобы новый разработчик мог понять проект за 1-2 дня.

## 2. Структура Проекта

```text
app/
  main.py
  config.py
  api/
    deps.py
    equipment.py
    equipment_types.py
    exports.py
    photos.py
    auth.py
  services/
    equipment_service.py
    equipment_type_service.py
    photo_service.py
    export_service.py
    audit_service.py
  repositories/
    equipment_repository.py
    equipment_type_repository.py
    user_repository.py
    audit_repository.py
  models/
    base.py
    region.py
    user.py
    equipment.py
    equipment_type.py
    photo.py
    audit.py
  schemas/
    equipment.py
    equipment_type.py
    auth.py
    export.py
  auth/
    provider.py
    database.py
    keycloak.py
  storage/
    photo_storage.py
    filesystem.py
    s3.py
  templates/
  static/
alembic/
tests/
prototypes/
```

## 3. Слои

```text
HTTP/Jinja/HTMX
      |
      v
api/
      |
      v
services/
      |
      +--> repositories/ --> models/ --> PostgreSQL
      |
      +--> storage/ -------> filesystem/S3
      |
      +--> auth/ ----------> database/Keycloak
```

## 4. Правила Зависимостей

- `api/` принимает HTTP-запросы, валидирует вход, вызывает сервисы и рендерит шаблоны.
- `api/` не содержит SQL.
- `api/` не работает с файловой системой напрямую.
- `services/` содержат бизнес-логику и сценарии.
- `services/` не зависят от FastAPI request/response.
- `repositories/` отвечают за запросы к БД, фильтрацию и пагинацию.
- `storage/` скрывает файловую систему или S3.
- `auth/` скрывает способ аутентификации и авторизации.
- `models/` не содержат бизнес-сценарии.

## 5. AuthProvider

Интерфейс:

```python
class AuthProvider:
    def get_current_user(self, request): ...
    def get_current_region_id(self, request) -> int | None: ...
    def is_center(self, request) -> bool: ...
    def has_permission(self, user, equipment_id: int) -> bool: ...
```

MVP:

- `DemoAuthProvider`;
- `DatabaseAuthProvider`;
- пользователи и токены в PostgreSQL;
- роли `region`, `center` и `center_admin`.

Будущее:

- `KeycloakAuthProvider`;
- JWT;
- роль и регион берутся из claims/attributes.

Переключение:

```text
AUTH_PROVIDER=database|keycloak
```

В текущей разработке Keycloak не реализуется. `KeycloakAuthProvider` остаётся заглушкой и должен явно сообщать, что интеграция не подключена. Критерий готовности к Keycloak: будущий переход должен затронуть конфигурацию, provider и dependency wiring, но не бизнес-сервисы.

## 6. PhotoStorage

Интерфейс:

```python
class PhotoStorage:
    def save_original(self, file_data, extension: str) -> str: ...
    def save_thumbnail(self, image_data, extension: str = "webp") -> str: ...
    def delete(self, paths: list[str]) -> None: ...
    def open(self, path: str): ...
```

Сервисный слой работает с фото через `PhotoService`, который:

- проверяет размер;
- проверяет формат;
- создаёт UUID;
- вызывает `PhotoStorage`;
- генерирует превью;
- записывает метаданные в БД;
- пишет audit log.

MVP:

- `FilesystemPhotoStorage`;
- хэш-папки;
- оригиналы и миниатюры.

Будущее:

- `S3PhotoStorage`.

Переключение:

```text
PHOTO_STORAGE=filesystem|s3
```

## 7. EquipmentService

Отвечает за:

- создание записи;
- редактирование базовых полей;
- валидацию динамических полей;
- проверку обязательных фото перед отправкой на проверку;
- смену статусов;
- проверку прав через `AuthProvider`;
- запись audit log.

## 8. EquipmentTypeService

Отвечает за:

- управление типами;
- управление динамическими полями;
- проверку уникальности кода поля внутри типа;
- запрет опасных изменений поля после появления данных;
- выключение типа/поля вместо физического удаления.

## 9. Фильтрация

Фильтрация реализуется в `EquipmentRepository`.

Правила:

- все списки идут с `LIMIT` и `OFFSET` или keyset-пагинацией;
- региональный пользователь всегда получает фильтр `region_id`;
- удалённые записи исключаются по умолчанию;
- JSONB-фильтры разрешены только по полям, помеченным `is_filterable`;
- для часто используемых JSONB-фильтров создаются expression-индексы.

## 9.1. Конкурентная Работа

Система проектируется под одновременную работу минимум 60 региональных пользователей и активную работу центра.

Правила реализации:

- создание и редактирование записи выполняются короткими транзакциями;
- обработка файлов и генерация превью не должны выполняться внутри долгой транзакции БД;
- повторная отправка формы должна быть идемпотентной: один пользовательский ввод не создаёт несколько одинаковых карточек;
- редактирование карточки использует optimistic locking по версии записи или `updated_at`;
- если пользователь сохраняет устаревшую версию карточки, сервис возвращает конфликт и предлагает обновить данные;
- смена статусов выполняется атомарно: сервис проверяет текущий статус в той же транзакции, где применяет переход;
- для критических переходов статуса допустим `SELECT ... FOR UPDATE` по одной строке оборудования;
- списки центра всегда читаются через пагинацию и индексы, без блокировок на запись;
- массовые действия центра выполняются пакетами с ограниченным размером и пишут audit log по каждой записи.

Типовые конфликты:

- регион редактирует запись, пока центр возвращает её на доработку;
- центр меняет статус, пока другой пользователь центра открывает ту же карточку;
- пользователь дважды нажимает кнопку отправки;
- браузер повторяет POST после сетевого сбоя.

Во всех случаях система должна либо безопасно объединить независимые изменения, либо явно остановить сохранение с сообщением о конфликте.

## 10. Основные Страницы

- `/login` - вход.
- `/` - региональная главная или центральный реестр в зависимости от роли.
- `/equipment` - список оборудования.
- `/equipment/new` - создание;
- `/equipment/{id}` - карточка;
- `/equipment/{id}/edit` - редактирование;
- `/equipment-types` - типы оборудования;
- `/equipment-types/{id}/fields` - поля типа;
- `/exports` - экспорт;
- `/admin/regions` - регионы, если требуется для MVP;
- `/admin/users` - пользователи, если требуется для MVP.

Интерфейс должен быть рабочим инструментом, не лендингом: плотные таблицы, фильтры, понятные формы, минимум декоративности.

Для региона `/equipment/new` должен работать как короткий мастер ввода. Для центра `/equipment` должен быть полноценным реестром с сохранёнными представлениями, настраиваемыми колонками и массовыми действиями.

## 11. API/Routes

Основные маршруты:

- `GET /equipment` - список с фильтрами и пагинацией.
- `GET /equipment/new` - форма создания.
- `POST /equipment` - создание.
- `GET /equipment/{id}` - карточка.
- `GET /equipment/{id}/edit` - форма редактирования.
- `POST /equipment/{id}` - сохранение изменений.
- `POST /equipment/{id}/submit` - отправка на проверку.
- `POST /equipment/{id}/accept` - принятие центром.
- `POST /equipment/{id}/revision` - возврат на доработку.
- `POST /equipment/{id}/archive` - архивирование.
- `POST /equipment/{id}/delete` - логическое удаление.
- `POST /equipment/{id}/photos` - добавление фото.
- `POST /equipment/{id}/photos/{photo_id}/delete` - удаление фото.
- `GET /equipment/{id}/photos/{photo_id}` - авторизованная выдача фото.
- `GET /equipment/{id}/photos/{photo_id}/thumb` - авторизованная выдача превью.
- `GET /equipment-types` - управление типами.
- `POST /equipment-types` - создание типа.
- `POST /equipment-types/{id}` - обновление типа.
- `POST /equipment-types/{id}/fields` - добавление поля.
- `POST /equipment-types/{id}/fields/{field_id}` - обновление поля.
- `POST /exports/equipment` - запуск экспорта.

## 12. ExportService

Отвечает за:

- применение текущих фильтров;
- ограничение 10 000 записей;
- генерацию XLSX;
- опциональную генерацию CSV;
- переход к асинхронному режиму при превышении лимита времени.

## 13. AuditService

Отвечает за запись событий:

- создание;
- редактирование;
- добавление/удаление фото;
- смена статуса;
- архивирование;
- удаление.

Audit log пишется из сервисного слоя, а не из `api/`.

## 14. Конфигурация

Ключевые переменные окружения:

```text
DATABASE_URL=
AUTH_PROVIDER=database
PHOTO_STORAGE=filesystem
PHOTO_ROOT=/var/lib/equipment-accounting/photos
MAX_PHOTO_SIZE_MB=10
EXPORT_SYNC_LIMIT=10000
SESSION_SECRET=
```

## 15. Тестирование

Минимальный набор тестов:

- права региона;
- права центра;
- смена статусов;
- обязательность фото при отправке;
- валидация динамических полей;
- фильтрация по базовым полям;
- фильтрация по JSONB-полю;
- запрет доступа к чужому фото;
- audit log при изменениях;
- повторная отправка формы не создаёт дубль;
- конфликт редактирования устаревшей карточки;
- атомарная смена статуса при параллельных запросах.
