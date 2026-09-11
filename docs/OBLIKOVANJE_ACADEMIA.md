# Оформление диплома в Academia (Višja strokovna šola Academia Maribor)

Дата проверки: 11.09.2026.

## Откуда эти правила

1. **Отдельного публичного документа с правилами оформления на academia.si нет.** Проверены главная
   страница, страницы «Diplomsko delo» программ (Programsko inženirstvo, Podatkovna znanost, Umetna
   inteligenca), FAQ и карта сайта (`sitemap_index.xml`, включая 1 500 PDF). Внутренние правила, скорее всего,
   лежат в студенческом портале **eAcademia**, куда нужен логин студента. **Артёму нужно скачать официальную
   predlogo/navodila там или спросить у ментора mag. Dušan Brglez и в referatu**, а затем сверить с этим файлом.
2. Школа публикует защищённые дипломы. Формат восстановлен **по 15 работам 2026 года** (выложены
   с февраля по август 2026). Шрифты, кегли, поля, интервалы, порядок разделов и подписи измерены программно
   (pdfplumber). Все 15 работ совпадают по основным параметрам, значит, это школьный шаблон.
3. Главный эталон: **Vasil Trajkovski, «Razvoj decentralizirane finance (DeFi) spletne aplikacije»**
   (Računalništvo, ментор mag. Dušan Brglez, 2026). Это та же программа и тот же ментор, что у Артёма.
   Глава 1 там устроена точно так же, как в диспозиции Артёма (1.1–1.4). Второй эталон: Tim Starčič
   (Informatika, 2026).

Ссылки: [страница «Diplomsko delo» (Programsko inženirstvo)](https://www.academia.si/studijski-program/potek-studija-programsko-inzenirstvo/diplomsko-delo-programsko-inzenirstvo),
[работа Trajkovski (PDF)](https://www.academia.si/wp-content/uploads/2026/07/Vasil-Trajkovski-DD-PDF_compressed.pdf),
[работа Starčič (PDF)](https://www.academia.si/wp-content/uploads/2026/06/StarcicTim_DiplomskoDelo_2026_compressed.pdf).

Готовый шаблон по этим правилам: [thesis/Diplomsko_delo_predloga_Rakhmanov.docx](../thesis/Diplomsko_delo_predloga_Rakhmanov.docx).

## Страница и текст

| Параметр | Значение (измерено) |
|---|---|
| Формат | A4, книжная ориентация |
| Поля | слева **3 см**, справа **2 см**, сверху около 2,5 см, снизу около 2,5 см |
| Шрифт основного текста | **Times New Roman 12 pt** |
| Межстрочный интервал | **1,5** (шаг строк 20,6 pt) |
| Абзацы | выравнивание **по ширине**, между абзацами около 6 pt, без красной строки |
| Номер страницы | внизу **по центру**, арабские цифры; счёт идёт с титульной страницы, но номер виден **с главы UVOD** (у Trajkovski UVOD на с. 15) |
| Главы | каждая глава **с новой страницы** |
| Объём | 56–105 страниц (медиана 67 по 15 работам) |
| Язык | словенский, с лекторированием: у **всех** работ на титуле указан лектор (напр. «Lektorica: dr. …, prof. slov.») |

## Порядок частей

1. **Naslovna stran** (титул)
2. **IZJAVA O AVTORSTVU DIPLOMSKEGA DELA** (подписывается)
3. **ZAHVALA** (необязательно; у эталона стоит после izjave)
4. **POVZETEK** + «Ključne besede:» (жирным)
5. **ABSTRACT** + название на английском (жирным) + «Keywords:»
6. **KAZALO VSEBINE**
7. **KAZALO SLIK**, **KAZALO TABEL** (при необходимости **KAZALO GRAFIKONOV**)
8. **Uporabljeni angleški izrazi in kratice** (или SEZNAM KRATIC)
9. **1 UVOD**: 1.1 Opis področja in opredelitev problema; 1.2 Namen, cilji in osnovne trditve;
   1.3 Predpostavke in omejitve; 1.4 Uporabljene raziskovalne metode
10. Теоретические и практические главы
11. Подраздел **«Odgovori na raziskovalna vprašanja in preverjanje hipotez»** (у эталона 6.6)
12. **SKLEP** (нумерованная глава)
13. **VIRI IN LITERATURA** (или LITERATURA IN VIRI; нумерованная глава)
14. **PRILOGE** (нумерованная глава)

## Титульная страница (всё по центру)

```text
VIŠJA STROKOVNA ŠOLA ACADEMIA          12 pt, жирный
MARIBOR

НАЗВАНИЕ РАБОТЫ ЗАГЛАВНЫМИ             ~20 pt, жирный

Kandidat: Ime Priimek                  12 pt
Vrsta študija: študent izrednega študija
Študijski program: Računalništvo
Mentor predavatelj: mag. Dušan Brglez
Mentor v podjetju: …
Lektorica: …

Maribor, 2026
```

«Vrsta študija» (redni/izredni) нужно указать по факту.

## Izjava o avtorstvu

Заголовок 16 pt жирный. У всех работ одинаковый стандартный текст: автор с названием работы и ментором;
«S svojim podpisom zagotavljam, da:», далее 4 пункта (собственная работа; цитирование по правилам школы;
осознание ответственности за плагиат по ZASP; согласие на публикацию на портале школы по 32.a členu ZASP).
Внизу «Maribor, mesec 2026» и «Podpis študenta:». Текст перенесён в шаблон.

## Заголовки

| Уровень | Пример | Оформление |
|---|---|---|
| Глава | `1 UVOD` | 16 pt, жирный, ЗАГЛАВНЫЕ, номер без точки, новая страница |
| Подраздел | `1.1 Opis področja in opredelitev problema` | 14 pt, жирный курсив |
| Пункт | `2.3.1 Decentralizirana izmenjava (DEX)` | 12 pt, жирный курсив |
| Служебные (KAZALO…, IZJAVA) | `KAZALO VSEBINE` | 16 pt, жирный, без номера |
| POVZETEK, ABSTRACT, ZAHVALA | | 12 pt, жирный |

Оглавление автоматическое, с точками и номерами страниц: главы жирными заглавными, 1.1 малыми
заглавными, 1.1.1 курсивом.

## Рисунки, таблицы, графики

- Подписи 10 pt, **по центру**, нумерация сквозная: `Slika 1: …`, `Tabela 1: …`, `Grafikon 1: …`.
- **Рисунок:** подпись **под** рисунком, под ней источник: `(Vir: Schär, 2021)` или `Vir: lasten`.
- **Таблица:** подпись **над** таблицей, источник **под** таблицей: `Vir: Lasten vir`.
- Каждый рисунок и таблица упоминаются в тексте.

## Цитирование и литература

Стиль **APA 7 в словенской локализации** (так во всех 15 работах):

- в тексте: `(Schär, 2021, str. 13–15)`, `(Hovemeyer in Pugh, 2004)`, `(Marchesi idr., 2020, str. 5)`,
  без года: `(b. d.)`;
- список по алфавиту, **висячий отступ**, название книги или статьи **курсивом**;
- веб-источник: `Google. (b. d.). *SEO Starter Guide: The basics*. Pridobljeno 11. 9. 2026 s https://…`;
- статья: `Ziakis, C., Vlachopoulou, M., Kyrkoudis, T. in Karagkiozidou, M. (2019). Important factors for improving Google search rank. *Future Internet, 11*(2), 32. https://doi.org/10.3390/fi11020032`;
- закон: `Zakon o dostopnosti do proizvodov in storitev za invalide (ZDPSI). (2023). *Uradni list RS*, št. 14/23.`

Список проверенных источников в этом формате: [thesis/literatura.md](../thesis/literatura.md).

## BTEC Unit 16: Computing Research Project (Pearson Set)

Диспозиция оформлена для двух программ сразу: Pearson BTEC HND in Computing, Unit 16, и словенский
Diplomsko delo. Критерии Unit 16 взяты из спецификации Pearson (Issue 2, 2022, Unit code K/618/7425):

| Критерий | Требование | Где закрыть в работе |
|---|---|---|
| P1 | исследовательское предложение с вопросом/гипотезой и обзором литературы | диспозиция; 1.2; глава 2 |
| P2 | рассмотреть методы первичного и вторичного исследования | 1.4 |
| M1 | проанализировать подходы и обосновать выбор методов (философия/теория, Research Onion Saunders) | 1.4: позитивизм, дедукция, количественный квазиэксперимент, лонгитюдные данные |
| D1 | критически оценить методологии применительно к проекту | 1.4 + 3.5 (ограничения, альтернативы) |
| P3 | провести первичное и вторичное исследование с учётом затрат, доступа и этики | 3.1–3.3; согласие компании, конфиденциальность данных GSC |
| P4 | применить аналитические инструменты и проанализировать данные | 3.2 (аудит), 3.5 (DiD, bootstrap) |
| M2 | достоинства, ограничения и ловушки сбора и анализа данных | 1.3, 3.5 |
| P5 | донести результаты до целевой аудитории | презентация, отчёт для компании, демо-сайт |
| M3 | насколько результаты отвечают целям | 3.6, 4 |
| D2 | оценить результаты и дать обоснованные рекомендации | 4 (рекомендации компании) |
| P6 | эффективность применённых методов | 4.x «Refleksija raziskovalnega procesa» |
| P7 | альтернативные методологии и извлечённые уроки | 4.x |
| M4 | рекомендации по улучшению и будущие соображения | 4.x |
| D3 | рефлексия и вовлечённость, ведущие к рекомендациям | 4.x |

Для LO3 в спецификации отдельно упоминается анализ стейкхолдеров (кто, приоритет, частота и форма
коммуникации). Это можно дать короткой таблицей в приложении.

**Уточнить в школе:** нужен ли для BTEC отдельный английский отчёт или reflective log, или всё закрывается
словенским дипломом, презентацией и защитой.

## Чеклист перед сдачей

- [ ] Сверено с официальной predlogo из eAcademia
- [ ] Титул: все поля, включая лектора и вид обучения
- [ ] Izjava подписана
- [ ] Povzetek и Abstract примерно по 1 странице, 5 ключевых слов
- [ ] Оглавление и перечни рисунков/таблиц обновлены (правая кнопка → «Posodobi polje»)
- [ ] Номера страниц видны с UVOD
- [ ] У каждого рисунка и таблицы есть номер, подпись и Vir
- [ ] Все цитаты есть в литературе и наоборот; формат APA (sl)
- [ ] Каждое число в результатах есть в `claims.csv` одного `run_id`; синтетические числа в текст не попали
- [ ] Лекторирование
- [ ] Согласие компании на название в работе
- [ ] Раздел «Odgovori na raziskovalna vprašanja in preverjanje hipotez»
- [ ] Рефлексия (BTEC P6/P7/M4/D3)
