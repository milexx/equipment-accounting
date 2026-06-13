# Модель Данных

Документ фиксирует финальную модель данных MVP. DDL является проектным черновиком для Alembic-миграций.

## 1. Принципы

- Базовые поля и поля доступа хранятся обычными колонками.
- Динамические поля хранятся в `equipment.attributes JSONB`.
- Описание динамических полей хранится в `equipment_type_fields`.
- Физическое удаление оборудования в MVP не используется.
- Фото хранятся в файловой системе, в БД только метаданные и пути.
- Все значимые изменения пишутся в audit log.

## 2. Типы Enum

```sql
CREATE TYPE user_role AS ENUM ('region', 'center');

CREATE TYPE equipment_status AS ENUM (
    'draft',
    'submitted',
    'needs_revision',
    'accepted',
    'diagnostics_required',
    'writeoff_review',
    'writeoff_approved',
    'disposal_pending',
    'disposed',
    'valuation_pending',
    'valued',
    'sale_ready',
    'listed_for_sale',
    'sold',
    'archived',
    'deleted'
);

CREATE TYPE equipment_condition AS ENUM (
    'unknown',
    'working',
    'broken',
    'partially_working',
    'requires_diagnostics'
);

CREATE TYPE equipment_disposition AS ENUM (
    'undecided',
    'writeoff',
    'disposal',
    'valuation',
    'sale'
);

CREATE TYPE equipment_sale_status AS ENUM (
    'not_for_sale',
    'valuation_pending',
    'priced',
    'ready',
    'listed',
    'reserved',
    'sold'
);

CREATE TYPE equipment_photo_purpose AS ENUM (
    'general',
    'serial',
    'defect',
    'completeness',
    'other'
);

CREATE TYPE equipment_field_type AS ENUM (
    'string',
    'text',
    'integer',
    'decimal',
    'date',
    'boolean',
    'select',
    'multiselect'
);
```

Если команда хочет упростить миграции, enum можно заменить на `TEXT + CHECK`, но значения должны остаться фиксированными.

## 3. Таблицы

```sql
CREATE TABLE regions (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    region_id BIGINT REFERENCES regions(id),
    role user_role NOT NULL,
    login TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT,
    api_token_hash TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_region_user_region
        CHECK (
            (role = 'region' AND region_id IS NOT NULL)
            OR (role = 'center')
        )
);

CREATE TABLE equipment_types (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE equipment_type_fields (
    id BIGSERIAL PRIMARY KEY,
    equipment_type_id BIGINT NOT NULL REFERENCES equipment_types(id),
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    field_type equipment_field_type NOT NULL,
    is_required BOOLEAN NOT NULL DEFAULT FALSE,
    is_filterable BOOLEAN NOT NULL DEFAULT FALSE,
    display_order INTEGER NOT NULL DEFAULT 0,
    validation_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    options JSONB NOT NULL DEFAULT '[]'::jsonb,
    help_text TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (equipment_type_id, code)
);

CREATE TABLE equipment (
    id BIGSERIAL PRIMARY KEY,
    region_id BIGINT NOT NULL REFERENCES regions(id),
    equipment_type_id BIGINT NOT NULL REFERENCES equipment_types(id),
    status equipment_status NOT NULL DEFAULT 'draft',
    title TEXT NOT NULL,
    inventory_number TEXT,
    serial_number TEXT,
    location TEXT,
    condition equipment_condition NOT NULL DEFAULT 'unknown',
    disposition equipment_disposition NOT NULL DEFAULT 'undecided',
    sale_status equipment_sale_status NOT NULL DEFAULT 'not_for_sale',
    comment TEXT,
    revision_comment TEXT,
    defect_description TEXT,
    completeness TEXT,
    valuation_amount NUMERIC(14, 2),
    sale_price NUMERIC(14, 2),
    sale_description TEXT,
    is_public_listing BOOLEAN NOT NULL DEFAULT FALSE,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    row_version INTEGER NOT NULL DEFAULT 1,
    created_by_user_id BIGINT REFERENCES users(id),
    updated_by_user_id BIGINT REFERENCES users(id),
    submitted_at TIMESTAMPTZ,
    accepted_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE equipment_photos (
    id UUID PRIMARY KEY,
    equipment_id BIGINT NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    original_path TEXT NOT NULL,
    thumbnail_path TEXT NOT NULL,
    original_filename TEXT,
    content_type TEXT NOT NULL,
    purpose equipment_photo_purpose NOT NULL DEFAULT 'general',
    file_size BIGINT NOT NULL,
    width INTEGER,
    height INTEGER,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_by_user_id BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE equipment_audit_log (
    id BIGSERIAL PRIMARY KEY,
    equipment_id BIGINT NOT NULL REFERENCES equipment(id),
    actor_user_id BIGINT REFERENCES users(id),
    actor_region_id BIGINT REFERENCES regions(id),
    action TEXT NOT NULL,
    old_data JSONB,
    new_data JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## 4. Индексы

```sql
CREATE INDEX idx_users_region_id ON users(region_id);
CREATE INDEX idx_users_role ON users(role);

CREATE INDEX idx_equipment_region_id ON equipment(region_id);
CREATE INDEX idx_equipment_status ON equipment(status);
CREATE INDEX idx_equipment_type_id ON equipment(equipment_type_id);
CREATE INDEX idx_equipment_inventory_number ON equipment(inventory_number);
CREATE INDEX idx_equipment_serial_number ON equipment(serial_number);
CREATE INDEX idx_equipment_location ON equipment(location);
CREATE INDEX idx_equipment_condition ON equipment(condition);
CREATE INDEX idx_equipment_disposition ON equipment(disposition);
CREATE INDEX idx_equipment_sale_status ON equipment(sale_status);
CREATE INDEX idx_equipment_created_at ON equipment(created_at DESC);
CREATE INDEX idx_equipment_updated_at ON equipment(updated_at DESC);

CREATE INDEX idx_equipment_region_type_status
ON equipment(region_id, equipment_type_id, status);

CREATE INDEX idx_equipment_center_pipeline
ON equipment(status, condition, disposition, sale_status, updated_at DESC)
WHERE deleted_at IS NULL;

CREATE INDEX idx_equipment_active_list
ON equipment(region_id, equipment_type_id, status, updated_at DESC)
WHERE deleted_at IS NULL;

CREATE INDEX idx_equipment_not_deleted
ON equipment(id)
WHERE deleted_at IS NULL;

CREATE INDEX idx_equipment_attributes_gin
ON equipment USING GIN (attributes);

CREATE INDEX idx_equipment_photos_equipment_id
ON equipment_photos(equipment_id);

CREATE INDEX idx_equipment_photos_purpose
ON equipment_photos(equipment_id, purpose);

CREATE INDEX idx_equipment_audit_equipment_id
ON equipment_audit_log(equipment_id, created_at DESC);
```

## 4.1. Согласованность При Одновременной Работе

БД должна поддерживать одновременную работу не менее 60 региональных пользователей и центра без потери данных.

Правила:

- `equipment.row_version` используется для optimistic locking при редактировании карточки;
- каждое успешное изменение карточки увеличивает `row_version`;
- `updated_at` остаётся служебным временем изменения, но не является единственным механизмом защиты от конфликтов;
- смена статуса выполняется условным обновлением по текущему статусу и версии записи или через блокировку одной строки;
- блокировки не должны охватывать списки, экспорт или длительную обработку фото;
- повторное создание одинаковой записи в коротком интервале должно отсекаться приложением, а при необходимости дополнительно защищаться уникальным ключом идемпотентности;
- audit log фиксирует старые и новые значения, чтобы спорные изменения можно было восстановить.

Для идемпотентности форм допускается отдельная таблица `form_submissions` или поле `client_request_id`, если защиты по естественным признакам станет недостаточно.

## 5. Индексы По JSONB-Полям

Для часто фильтруемых динамических полей создавать expression-индексы.

Пример для строкового поля:

```sql
CREATE INDEX idx_equipment_attr_manufacturer
ON equipment ((attributes ->> 'manufacturer'));
```

Пример для числового поля:

```sql
CREATE INDEX idx_equipment_attr_cpu_count
ON equipment (((attributes ->> 'cpu_count')::integer));
```

Решение о создании индекса принимается для полей с `is_filterable=true`, если поле реально используется в фильтрах.

## 6. Ограничения На Уровне Приложения

Следующие правила реализуются в сервисном слое:

- минимум 1 и максимум 5 фото;
- для нерабочего оборудования минимум 1 фото с `purpose='defect'`;
- обязательность динамических полей;
- валидность типов значений в `attributes`;
- разрешённые переходы статусов;
- обязательность `defect_description` для состояния `broken`;
- обязательность цены перед публикацией в продаже;
- запрет региона на доступ к чужим записям;
- запрет удаления типа, если есть оборудование этого типа;
- запрет удаления поля, если по нему уже есть данные.

## 7. Согласованность БД И Фото

Фото физически хранятся вне БД, поэтому операции должны быть организованы так:

1. проверить права и ограничения;
2. сохранить файлы во временное или целевое место;
3. создать записи `equipment_photos`;
4. при ошибке удалить уже сохранённые файлы;
5. записать audit log.

Для удаления:

1. удалить или пометить запись фото в БД;
2. удалить файлы через `PhotoStorage`;
3. при ошибке удаления файла записать ошибку в лог для последующей очистки.

## 8. Seed-Данные MVP

Для запуска MVP нужны начальные данные:

- центр-пользователь;
- минимум один регион;
- тестовый региональный пользователь;
- 2-3 типа оборудования;
- набор полей для каждого тестового типа.
