# Данные: откуда брать и как хранить

## Структура снимка

```text
data/raw/<снимок>/
  SNAPSHOT.yaml        описание: источник, даты выгрузки, кто выгрузил, сайт
  SHA256SUMS           хеши всех файлов (python -m research checksums --snapshot ...)
  pages.csv            page, url, design_group (technical|content|local|accessibility|control)
  gsc_daily.csv        date, page, segment (local|general), clicks, impressions, position
  interventions.csv    intervention_id, page (или * для всего сайта), type, date, description
  lighthouse.csv       page, snapshot (before|after), date, performance, accessibility, seo, lcp_ms, cls, inp_ms
  authority.csv        date, metric, source, value
  crawl/before/        index.csv + HTML-файлы
  crawl/after/
```

Снимок неизменяем. Новые данные означают новую папку (например `site_2026-12-01`) и новый запуск.

## Источники

| Файл | Источник | Как получить |
|---|---|---|
| `gsc_daily.csv` | Google Search Console | API `searchanalytics.query` (dimensions `date`, `page`, `query`), затем агрегировать запросы в сегменты `local/general` по зафиксированному правилу. Интерфейс GSC не даёт выгрузку «страница × день», поэтому нужен API. GSC хранит 16 месяцев истории |
| `pages.csv` | автор | список URL и групп, зафиксированный до изменений |
| `interventions.csv` | автор | журнал всех изменений сайта с датой публикации; сюда же редизайны, смена хостинга, массовые правки |
| `lighthouse.csv` | PageSpeed Insights API или Lighthouse CLI | по 3 прогона на страницу, медиана; поле `snapshot` before/after |
| `authority.csv` | Moz (DA) **или** Ahrefs (DR) | один источник на всё исследование, раз в месяц |
| `crawl/*` | `python -m research crawl` или экспорт Screaming Frog | до и после изменений |

Метрики Google Business Profile (просмотры, звонки, маршруты) пригодятся для описательной части H3.
Их можно хранить в отдельном файле `gbp_monthly.csv`, в пайплайн они пока не входят.

## Конфиденциальность

- Данные компании не коммитятся (`.gitignore`), хранятся локально и в резервной копии у автора.
- В `SNAPSHOT.yaml` и в тексте указываются только агрегаты.
- Название компании на публичном сайте используется только после подтверждения согласия.

## Контрольные суммы

```bash
python -m research checksums --snapshot data/raw/site_2026
python -m research doctor --config configs/full.yaml
```

`data_sha256` в manifest является хешем всего дерева снимка. Его стоит записать в `docs/HANDOFF.md`, чтобы
при переносе на другой компьютер проверить, что данные те же.

## Синтетический снимок `data/raw/smoke`

Создан `python -m research fixtures --out data/raw/smoke`, seed 20260911, вымышленный сайт
`primer-finance.test`, 25 страниц × 219 дней × 2 сегмента. Заложенные эффекты лежат в
`ground_truth.json`. Данные используются только для проверки метода.
