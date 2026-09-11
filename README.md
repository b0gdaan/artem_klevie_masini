# SEO-оптимизация сайтов: воспроизводимый исследовательский пакет

Дипломная работа (Academia, Pearson BTEC HND in Computing / Računalništvo, 2026):
**«SEO-optimizacija spletnih mest: metode in strategije doseganja visokih pozicij v iskalnikih»**.

Репозиторий содержит основу для практической части: аудит сайта, измерение эффекта SEO-мер по данным
Google Search Console, проверку устойчивости, отчёт и демонстрационный сайт. Всё запускается одной
командой и проверяется по контракту воспроизводимости.

**Демонстрация:** https://b0gdaan.github.io/artem_klevie_masini/

> Текущий статус: пайплайн полностью работает на **синтетическом** снимке (вымышленный сайт
> `primer-finance.test` с заранее заложенными эффектами). Данных реального сайта ещё нет, поэтому
> все цифры на странице и в отчётах проверяют метод, а не отвечают на вопрос диплома.
> Следующие шаги описаны в [docs/HANDOFF.md](docs/HANDOFF.md).

## Почему Python

Практическая часть включает краулинг и разбор HTML, выгрузку данных Search Console и PageSpeed Insights
через API, статистическую оценку (разность разностей, bootstrap) и генерацию таблиц и рисунков для текста.
Всё это есть в экосистеме Python (requests, BeautifulSoup, pandas, numpy, matplotlib), а у Google для
Search Console есть официальный Python-клиент. Сайт демонстрации написан на чистых HTML/CSS/JS: данные для
него экспортирует тот же запуск. Подробнее: [docs/DECISIONS.md](docs/DECISIONS.md).

## Быстрый старт

Нужен Python 3.11 (именно на нём сделан `requirements.lock`).

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.lock      # Linux/macOS: .venv/bin/python
.venv/Scripts/python -m pip install --no-deps -e .
.venv/Scripts/python -m research doctor
.venv/Scripts/python -m research smoke
```

`smoke` проходит все этапы на зафиксированном снимке без сети и сразу запускает `verify`.

## Команды

| Команда | Что делает |
|---|---|
| `python -m research doctor` | Проверяет Python, версии пакетов из lock-файла, конфигурации, данные и права на запись |
| `python -m research smoke` | Полный маленький эксперимент на `data/raw/smoke` без сети, затем verify |
| `python -m research run --config configs/full.yaml` | Все обязательные этапы для реального снимка |
| `python -m research resume --run-id <id\|latest>` | Проверяет готовые этапы по хешам и продолжает незавершённые |
| `python -m research verify --run-id <id>` | Полнота, хеши, происхождение, пересчёт метрик из прогнозов, реестр утверждений |
| `python -m research report --run-id <id>` | Пересобирает таблицы, рисунки и экспорт одного запуска |
| `python -m research release --run-id <id> --junit reports/junit.xml --site-dir site` | Выпуск после verify и чистого JUnit-отчёта |
| `python -m research status --run-id <id>` | Статусы этапов |
| `python -m research crawl --url https://... --out data/raw/<снимок>/crawl/before` | Вежливый краулинг сайта (сеть, robots.txt) |
| `python -m research checksums --snapshot data/raw/<снимок>` | Запечатать новый снимок (`SHA256SUMS`) |
| `python -m research fixtures --out <папка>` | Заново сгенерировать синтетический снимок |

Этапы: `ingest → validate → transform → split → fit → predict → evaluate / diagnostics → report`, затем
отдельно `verify` и `release`. Запуск без обязательного этапа получает статус `incomplete`.

## Структура

```text
configs/        smoke.yaml (синтетика), full.yaml (реальный сайт, шаблон предрегистрации)
src/research/   данные, аудит, краулер, разбиения, оценка, отчёт, verify, release, CLI
tests/          unit, integration, reproducibility (матрица из контракта)
data/raw/       неизменяемые снимки; в git только synthetic smoke
data/processed/ результат transform, ключ = хеш данных + хеш кода (не в git)
runs/<run_id>/  manifest.yaml, логи, прогнозы, метрики, модель CTR, отчёт (не в git)
reports/        JUnit и описание реестра утверждений
thesis/         структура диплома, литература (literatura.md, references.bib)
presentation/   план слайдов и речи
docs/           протокол, решения, данные, восстановление, handoff, разбор диспозиции
site/           GitHub Pages; данные кладёт release в site/data/
```

## Данные и конфиденциальность

Реальные данные компании (Search Console, Google Business Profile, выгрузки Moz/Ahrefs) **не коммитятся**:
папки `data/raw/*` кроме `smoke` в `.gitignore`. В репозитории хранятся только способ получения и
контрольные суммы ([docs/DATA.md](docs/DATA.md)). Название компании на публичном сайте не указывается,
пока не подтверждено согласие (см. [разбор диспозиции](docs/DISPOZICIJA_REVIEW.md)).

## Документы

- [docs/DISPOZICIJA_REVIEW.md](docs/DISPOZICIJA_REVIEW.md): тема, сильные стороны, риски гипотез, новый график
- [docs/PROTOCOL.md](docs/PROTOCOL.md): вопрос, метрики, пороги, окна, неопределённость (до просмотра данных)
- [thesis/literatura.md](thesis/literatura.md): список литературы с пометками, что проверить
- [docs/DATA.md](docs/DATA.md), [docs/RECOVERY.md](docs/RECOVERY.md), [docs/DECISIONS.md](docs/DECISIONS.md), [docs/HANDOFF.md](docs/HANDOFF.md)
