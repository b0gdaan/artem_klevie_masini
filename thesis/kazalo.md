# Kazalo diplomskega dela (по образцу Academia 2026)

Структура совпадает с одобренной диспозицией (1 Uvod, 2 Teoretični del, 3 Praktični del, 4 Sklep,
5 Literatura). Добавлено только то, что есть во всех дипломах Academia и что нужно для BTEC Unit 16:
служебные страницы, подраздел с ответами на RV и проверкой гипотез, рефлексия, приложения.
Готовый DOCX с этой структурой: [Diplomsko_delo_predloga_Rakhmanov.docx](Diplomsko_delo_predloga_Rakhmanov.docx).

## Начальные страницы (без номера страницы)

Naslovna stran → IZJAVA O AVTORSTVU DIPLOMSKEGA DELA → ZAHVALA → POVZETEK (Ključne besede) →
ABSTRACT (Keywords) → KAZALO VSEBINE → KAZALO SLIK → KAZALO TABEL → KAZALO GRAFIKONOV →
Uporabljeni angleški izrazi in kratice

## Основная часть (номер страницы с UVOD)

| Poglavje | Содержание | Материал из репозитория |
|---|---|---|
| **1 UVOD** | | |
| 1.1 Opis področja in opredelitev problema | SEO и PPC, доля Google в Словении (StatCounter) | literatura №16, №27 |
| 1.2 Namen, cilji in osnovne trditve | RV1–RV4, H1–H5 в исправленной формулировке | `Dispozicija_popravljena_Rakhmanov.docx`, `configs/full.yaml` |
| 1.3 Predpostavke in omejitve | один сайт, неслучайные группы, core updates, DA не метрика Google, ZDPSI и микропредприятия | `docs/DISPOZICIJA_REVIEW.md` |
| 1.4 Uporabljene raziskovalne metode | описание, компиляция, сравнение; разность разностей, bootstrap, placebo; Research Onion (BTEC M1) | `docs/PROTOCOL.md`, №34–41 |
| **2 TEORETIČNI DEL – SEO: OSNOVE IN RAZVOJ** | | |
| 2.1 Delovanje Googlovih algoritmov in dejavniki uvrstitve | индексирование, PageRank, helpful content, E-E-A-T, YMYL | №1–10, №16–19 |
| 2.2 Tehnični SEO: hitrost, mobilnost in struktura | Core Web Vitals, mobile-first, canonical, статусы | №17, №23 |
| 2.3 Vsebinska optimizacija in ključne besede | title, meta, H1, структурированные данные, CTR и позиция | №11–13, №18 |
| 2.4 Gradnja povratnih povezav (off-page SEO) | ссылки, DA/DR и их ограничения | №2–3, №26 |
| 2.5 Lokalni SEO in Google Business Profile | факторы локального ранжирования | №22, №25 |
| 2.6 Dostopnost spletnih mest in SEO | WCAG 2.1/2.2, EAA, ZDPSI | №24, №28–33 |
| **3 PRAKTIČNI DEL – SEO-REVIZIJA IN OPTIMIZACIJA SPLETNEGA MESTA** | | |
| 3.1 Predstavitev izbranega spletnega mesta in začetno stanje | сайт, группы страниц, базовые показатели | `pages.csv`, Lighthouse «pred» |
| 3.2 Izvedba SEO-revizije | Screaming Frog и собственный аудит; частые ошибки (RV4) | `audit_summary.csv`, `audit_issues.png`, C-AUDIT |
| 3.3 Implementacija SEO-ukrepov in merjenje rezultatov | журнал мер, окна, данные GSC; RV2, RV3 | `interventions.csv`, `timeseries.png` |
| 3.4 Dostopnost spletnega mesta (WCAG) in vpliv na SEO | H4 | C-H4, Lighthouse accessibility |
| 3.5 Analiza rezultatov in robustnost | H1–H5, абляция, placebo, ограничения | `metrics.csv`, `ablation.csv`, `placebo.csv`, `effects.png` |
| 3.6 Odgovori na raziskovalna vprašanja in preverjanje hipotez | по одному абзацу на RV и H | `claims.csv` |
| **4 SKLEP** | выводы, рекомендации компании (BTEC D2) | |
| 4.1 Refleksija raziskovalnega procesa | эффективность методов, альтернативы, уроки (BTEC P6, P7, M4, D3) | `docs/HANDOFF.md` (журнал) |
| **5 VIRI IN LITERATURA** | APA 7 (sl) | `thesis/literatura.md` |
| **6 PRILOGE** | A протокол, B журнал изменений сайта, C воспроизводимость, D анализ стейкхолдеров (BTEC LO3) | `docs/PROTOCOL.md`, `RELEASE.json` |

## Правило для чисел в тексте

Каждое число результата в тексте должно иметь строку в `report/claims.csv` одного `run_id`. Округление делается
при вставке и документируется. Числа из синтетического запуска в текст диплома не переносятся.
