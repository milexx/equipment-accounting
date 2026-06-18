# Gate И Acceptance Для Модуля Оценщика

Дата: 2026-06-18.

Статус: рабочий checklist перед переходом от research к backend-разработке.

## 1. Текущий Gate

Текущий статус:

```text
continue_endurance_with_caution
```

Backend-модели, Alembic-миграции и UI `/pricing` не начинать, пока не принято одно из решений:

- `go_worker_prototype`;
- `hold_http_unstable`;
- `browser_profile_research`.

## 2. Условия `go_worker_prototype`

Можно переходить к backend-скелету, если выполнены все условия:

- выполнено минимум 3 live day run;
- live run делается не чаще 1 раза в день;
- минимум 2 из 3 позиций дают пригодные данные в большинстве запусков;
- блокировки `403`, `429`, CAPTCHA не доминируют над успешными позициями;
- `page_not_found` и ошибки URL устранены без частых live-проверок;
- offline-анализатор формирует таблицу результатов;
- reject/unknown причины понятны и не скрывают очевидно релевантные объявления;
- нет необходимости в proxy rotation, CAPTCHA bypass или платном data provider.

## 3. Условия `hold_http_unstable`

Остановить перенос в приложение, если наблюдается хотя бы одно:

- 2 дня подряд большинство позиций получает `HTTP 403`, `HTTP 429` или CAPTCHA;
- успешные данные стабильно есть только по одной позиции из трёх;
- Avito возвращает непредсказуемые HTML-структуры, которые нельзя разобрать без браузера;
- для продолжения нужен обход CAPTCHA, proxy rotation или покупка стороннего сервиса;
- результаты нельзя использовать как повторяемую дневную историю.

## 4. Условия `browser_profile_research`

Переходить к отдельному browser-profile research только если:

- простой HTTP нестабилен;
- бизнес всё равно считает Avito обязательным источником;
- принято ограничение stop-on-block;
- не планируется CAPTCHA bypass;
- не планируется proxy rotation;
- отдельный браузерный профиль можно изолировать от основной системы.

## 5. Day 2 Checklist

Перед запуском:

```bash
cd research/avito-monitor-worker-poc
.venv/bin/python -m unittest discover -s tests
.venv/bin/python src/worker.py --dry-run-config --config config/search_jobs.json
```

Запуск:

```bash
.venv/bin/python src/worker.py --config config/search_jobs.json --runs-dir runs
```

После запуска:

```bash
.venv/bin/python src/worker.py --analyze-run runs/{run_id}
.venv/bin/python src/worker.py --write-markdown-report runs/{run_id} --output runs/{run_id}/offline_report.md
```

В git добавить только markdown-документ day 2, не raw HTML и не JSON runtime.

## 6. Шаблон Решения После Day 2

```text
date:
run_id:
decision:
reason:

kyocera_m2040dn:
lenovo_t14:
dell_r740:

next_action:
```

Возможные `decision`:

- `continue_endurance_day_3`;
- `hold_http_unstable`;
- `adjust_queries_offline`;
- `browser_profile_research_candidate`.

## 7. Acceptance Для Research-Фазы

Research-фаза считается завершённой, когда есть:

- `docs/33_price_monitoring_endurance_day_1.md`;
- `docs/34_price_monitoring_endurance_day_2_plan.md`;
- day 2 отчёт;
- day 3 отчёт или обоснованное раннее решение `hold_http_unstable`;
- итоговый документ с решением gate.

Итоговый документ должен ответить:

- переносим ли worker в приложение;
- оставляем ли Avito как research-only;
- нужен ли browser-profile research;
- какие риски остаются для pilot.
