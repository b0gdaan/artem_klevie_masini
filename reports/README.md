# Reports

Отчёты создаются кодом для каждого запуска: `runs/<run_id>/report/`.

| Файл | Содержание |
|---|---|
| `report.md` | таблицы гипотез, абляции, placebo и аудита |
| `tables/*.csv` | те же таблицы для вставки в текст |
| `figures/*.png` | effects, timeseries, audit_issues |
| `claims.csv` | реестр утверждений |
| `site_data.json` | публичный экспорт для сайта (`demo_public`) |

## Реестр утверждений (CLAIMS)

Поля: `claim_id`, `section`, `statement`, `run_id`, `file`, `filter`, `metric`, `value`, `interval`, `limitation`.
`verify` сверяет каждое утверждение с `metrics.csv` того же запуска.

`reports/junit.xml` пишет pytest (`--junitxml`), в git не хранится. `release` отказывается выпускать запуск,
если в отчёте есть failed или error, и отдельно записывает число skipped.
