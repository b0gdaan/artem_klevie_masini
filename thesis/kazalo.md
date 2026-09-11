# Kazalo diplomskega dela in povezava z repozitorijem

Структура из диспозиции (раздел 2) с уточнениями. Справа указано, откуда брать материал.

| Poglavje | Содержание | Материал |
|---|---|---|
| **1 Uvod** | | |
| 1.1 Opis področja in opredelitev problema | SEO vs PPC, доля Google в Словении (с источником) | literatura №16, №27; SURS |
| 1.2 Namen, cilji in osnovne trditve | RV1–RV4, H1–H5 в уточнённой формулировке | `configs/full.yaml`, `docs/PROTOCOL.md` |
| 1.3 Predpostavke in omejitve | один сайт, неслучайные группы, core updates, DA не метрика Google | `docs/DISPOZICIJA_REVIEW.md` |
| 1.4 Uporabljene raziskovalne metode | описание, компиляция, DiD, bootstrap, placebo | `docs/PROTOCOL.md`, literatura №34–39 |
| **2 Teoretični del** | | |
| 2.1 Delovanje Googlovih algoritmov in dejavniki uvrstitve | индексирование, PageRank, helpful content, E-E-A-T и YMYL | №1–8, №16–19 |
| 2.2 Tehnični SEO | Core Web Vitals, mobile-first, canonical, статусы | №17, №23 |
| 2.3 Vsebinska optimizacija in ključne besede | title, meta, H1, структурированные данные, CTR и позиция | №11–13, №18 |
| 2.4 Gradnja povratnih povezav | ссылки, DA/DR и их ограничения | №2–3, №26 |
| 2.5 Lokalni SEO in Google Business Profile | факторы локального ранжирования | №22, №25 |
| 2.6 (новый) Dostopnost in SEO | WCAG 2.1/2.2, EAA, ZDSMA | №28–33, №24 |
| **3 Praktični del** | | |
| 3.1 Predstavitev spletnega mesta in začetno stanje | сайт, группы страниц, базовые показатели | `pages.csv`, отчёт: Lighthouse «pred» |
| 3.2 SEO-revizija (Screaming Frog, lastni pregled) | частые ошибки (RV4) | `report/tables/audit_summary.csv`, `figures/audit_issues.png`, claim C-AUDIT |
| 3.3 Implementacija ukrepov in merjenje | журнал мер, H1–H3, H5, RV2, RV3 | `interventions.csv`, `metrics.csv`, `figures/effects.png`, `figures/timeseries.png`, claims C-H1…C-H5 |
| 3.4 Dostopnost (WCAG) in vpliv na SEO | H4 | claim C-H4, Lighthouse accessibility |
| 3.5 (новый) Robustnost rezultatov | абляция, placebo, ограничения | `ablation.csv`, `placebo.csv` |
| **4 Sklep** | ответы на RV, практическая польза, что дальше | |
| **5 Literatura in viri** | | `thesis/references.bib` |
| Priloge | протокол, журнал изменений, воспроизводимость | `docs/PROTOCOL.md`, `RELEASE.json` |

## Правило для чисел в тексте

Каждое число результата в тексте должно иметь строку в `report/claims.csv` одного и того же `run_id`.
Округление делается при вставке в текст и документируется (например, «+27,4 % → 27 %»). Числа из
синтетического запуска в текст диплома не переносятся.
