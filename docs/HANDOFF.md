# HANDOFF

Обновлять после каждого содержательного этапа.

## Текущий вопрос

Какие SEO-меры (технические, контентные, локальные, доступность) дают измеримое изменение видимости в
Google на сайте компании по сравнению с неизменёнными страницами (H1–H5 в `docs/PROTOCOL.md`).

## Состояние на 11.09.2026

| | |
|---|---|
| Код | ветка `main`; последний коммит см. `git log -1`; CI `tests-smoke-pages` |
| Демонстрация | https://b0gdaan.github.io/artem_klevie_masini/ (smoke-запуск из CI, режим «синтетический сценарий») |
| Данные | только синтетический `data/raw/smoke` (seed 20260911). **Реальных данных нет** |
| Окружение | Python 3.11, `requirements.lock`; локально `.venv` в корне проекта |
| Завершено | пайплайн ingest → report, verify, release; 49 тестов; сайт; протокол-черновик; разбор диспозиции; литература |

## Команды

```bash
python -m research doctor
python -m research smoke
python -m research status --run-id latest
python -m research resume --run-id latest
python -m research verify --run-id latest
python -m pytest -q --junitxml=reports/junit.xml
python -m research release --run-id latest --junit reports/junit.xml --site-dir site
```

Локальный просмотр сайта после `release`: `python -m http.server -d site 8000`.

## Текущая проблема

1. Нет доступа к данным сайта (GSC, GA4, GBP) и не выбран конкретный сайт или URL.
2. График диспозиции сорван: измерения планировались на июль–август. Новый план есть в `docs/DISPOZICIJA_REVIEW.md`.
3. Не подтверждено по оригиналу, разрешено ли называть компанию публично.

## Ближайший шаг

1. Получить доступ к Search Console (роль «Full» или «Restricted» достаточно для API) и список URL.
2. Разбить страницы на группы, записать `pages.csv`, правило локальных запросов, даты мер; закоммитить
   `configs/full.yaml`, это и есть предрегистрация.
3. Написать `src/research/gsc_export.py`: выгрузка API → `gsc_daily.csv` с сегментами (TODO, нужен OAuth-клиент).
4. Выгрузить pre-период (GSC хранит 16 месяцев), выполнить краулинг и Lighthouse «до» и запечатать снимок.
5. Внедрять меры по группам, вести `interventions.csv`.

## Известные ограничения

- Аудит доступности эвристический (часть WCAG), для диплома нужен ещё Lighthouse или WAVE.
- При 5 страницах в группе bootstrap-интервалы приблизительные.
- Метрики GBP в пайплайн пока не входят.
- Кривая ожидаемого CTR не учитывает тип выдачи (AI Overviews, локальный блок).

## Решения и документы

`docs/DECISIONS.md`, `docs/PROTOCOL.md`, `docs/DATA.md`, `docs/RECOVERY.md`, `thesis/kazalo.md`, `thesis/literatura.md`.
