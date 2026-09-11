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
| Завершено | пайплайн ingest → report, verify, release; 50 тестов; сайт; протокол-черновик; разбор диспозиции; литература |
| `data_sha256` smoke | `7e3badd1fe3aed14ab721cb1b7e76c9cac657479a84d95919f80eaa617ad333e` (одинаков на Windows и Linux) |

## Журнал проверок

| Дата (UTC) | Где | Что выполнено | Результат |
|---|---|---|---|
| 11.09.2026 | Windows 11, Python 3.11.9, `.venv` | doctor; `pytest --junitxml`; smoke; verify; release в `site/` | 49 passed; verify passed |
| 11.09.2026 | локальный браузер (http.server) | заполненность таблиц, SVG, тултип, вкладки, отсутствие горизонтальной прокрутки на 1280 px и 375 px, наложение подписей | без ошибок консоли; визуальные скриншоты ниже первого экрана получить не удалось (панель браузера скрыта) |
| 11.09.2026 | GitHub Actions run 34599437592, ubuntu, Python 3.11 | clean install из lock, doctor, pytest, smoke, verify, release, deploy Pages | 49/49; run `smoke-20260911T123306Z-b237fb` из `a2f67d1`, `working_tree_dirty=false` |
| 11.09.2026 | сверка Windows и CI | `data_sha256` одного снимка различался (`7d2db6f5…` vs `7e3badd1…`) | исправлено: порядок файлов в `tree_sha256` теперь по строке POSIX, добавлен тест; `.gitattributes` переупорядочен |

| 11.09.2026 | academia.si (сайт, sitemap, FAQ, 15 PDF дипломов 2026) | поиск правил оформления; замер шрифтов, полей, интервалов, порядка разделов | публичного документа с правилами нет; формат восстановлен по работам → `docs/OBLIKOVANJE_ACADEMIA.md` |
| 11.09.2026 | издатели, DOI, uradni-list.si, StatCounter | проверка литературы и фактов диспозиции | исправлены Giomelakis, ZDPSI вместо ZDSMA, Whitespark 2026, доля Google 93,2 % (не >95 %) |
| 11.09.2026 | `thesis/tools/build_docs.py` | генерация исправленной диспозиции и шаблона диплома (DOCX) | см. коммит |

Не выполнялось: реальный краулинг по сети, выгрузка GSC, запуск `configs/full.yaml` (нет данных),
проверка сайта скринридером.

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
