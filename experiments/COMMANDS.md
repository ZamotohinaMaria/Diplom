# Карта скриптов experiments/

Собрано `experiments/collect_env.py` 04.11.2026 из docstring скриптов — при изменении скриптов перезапустить. Все команды — из корня репозитория. Каждый запуск записывается в `EXPERIMENTS.csv`.

## Порядок запуска

| № | Скрипт | Этап | Что делает |
|---|---|---|---|
| 1 | [audit_duplicates.py](audit_duplicates.py) | Неделя 1, задача 1 — аудит дублей | Задача 1. Аудит дублей последовательностей API в MalBehavD-V1. |
| 2 | [leak_check.py](leak_check.py) | Неделя 1, задача 2 — утечка в схеме НИРС | Задача 2. Утечка в текущей схеме run_splits.py. |
| 3 | [make_splits.py](make_splits.py) | Неделя 1, задача 3 — разбиения A и B | Задача 3. Разбиения train / val / test для двух протоколов. |
| 4 | [baseline_tfidf.py](baseline_tfidf.py) | Неделя 1, задача 4 — TF-IDF + LogReg на A/B; неделя 2 — пилот C | Задача 4, модель 1: TF-IDF по n-граммам API (n = 1–3) + логистическая регрессия. |
| 5 | [run_gine_splits.py](run_gine_splits.py) | Неделя 1, задача 4 — GINE на A/B; неделя 2 — пилот C | Задача 4, модель 2: GINE (лучшая конфигурация из НИРС, архитектура без изменений) на разбиениях A/B. |
| 6 | [h1_table.py](h1_table.py) | Неделя 1, задача 4 — итог H1 | Задача 4, итог: таблица «модель × протокол» (среднее ± std по seed) и разница A − B для проверки H1. |
| 7 | [make_split_c.py](make_split_c.py) | Неделя 2, пункт 2 — разбиение C | Пункт 2 (неделя 2–8.11.2026). Протокол C — разбиение по исполняемым файлам. |
| 8 | [pilot_c_table.py](pilot_c_table.py) | Неделя 2, пункт 3 — итог пилота C | Пункт 3 (неделя 2–8.11.2026), итог: таблица пилота на разбиении C. |
| 9 | [collect_env.py](collect_env.py) | Неделя 2, пункт 4 — окружение и карта скриптов | Пункт 4 (неделя 2–8.11.2026). Окружение и карта скриптов — для воспроизводимости. |
| 10 | [log_run.py](log_run.py) | Модуль журнала EXPERIMENTS.csv | Журнал запусков: строка в EXPERIMENTS.csv появляется в начале запуска (status=running) |
| 11 | [eval_utils.py](eval_utils.py) | Общие функции оценки | Общие функции задачи 4: загрузка данных и разбиений, подбор порогов на val, метрики на test. |

## audit_duplicates.py

Задача 1. Аудит дублей последовательностей API в MalBehavD-V1.

```
python experiments/audit_duplicates.py
```

Результаты:

- `derived/hashes.csv` — row_idx, sha256_file, label, seq_hash, seq_len
- `derived/audit_duplicates_table.csv` — сводная таблица (всего / benign / malware)
- `derived/audit_top5_groups.csv` — 5 крупнейших групп одинаковых последовательностей
- `experiments/logs/audit_duplicates.txt` — текстовый отчёт (то же, что на экране)

## leak_check.py

Задача 2. Утечка в текущей схеме run_splits.py.

```
python experiments/leak_check.py
```

Результаты:

- `derived/leak_check_run_splits.csv` — по строке на seed + mean/std
- `experiments/logs/leak_check.txt` — текстовый отчёт (то же, что на экране)

## make_splits.py

Задача 3. Разбиения train / val / test для двух протоколов.

```
python experiments/make_splits.py
```

Результаты:

- `derived/splits/{A,B}_seed{N}.json` — индексы строк (row_idx исходного CSV) для train / val / test
- `derived/splits/summary.csv` — размеры частей, доли malware, утечка, разнесённые повторы файлов
- `experiments/logs/make_splits.txt` — текстовый отчёт (то же, что на экране)

## baseline_tfidf.py

Задача 4, модель 1: TF-IDF по n-граммам API (n = 1–3) + логистическая регрессия.

```
python experiments/baseline_tfidf.py                                 # оба блока
python experiments/baseline_tfidf.py --blocks ngram1                 # только проверка на 1-граммах
python experiments/baseline_tfidf.py --protocols B --seeds 42 43     # часть разбиений
python experiments/baseline_tfidf.py --protocols C --seeds 42 --blocks main   # пилот C
```

Результаты:

- `derived/results_tfidf.csv` — строка на (protocol, seed)
- `derived/predictions/tfidf_{A,B}_seed{N}.csv` — вероятности на val и test
- `experiments/logs/baseline_tfidf.txt` — текстовый отчёт
- `derived/results_tfidf_ngram1.csv`
- `derived/predictions/tfidf_ngram1_{A,B}_seed{N}.csv`
- `experiments/logs/baseline_tfidf_ngram1.txt`
- `derived/results_pilot_C_tfidf.csv`
- `derived/predictions/tfidf_C_seed42.csv`
- `experiments/logs/pilot_C_tfidf.txt`

## run_gine_splits.py

Задача 4, модель 2: GINE (лучшая конфигурация из НИРС, архитектура без изменений) на разбиениях A/B.

```
python experiments/run_gine_splits.py
python experiments/run_gine_splits.py --protocols A --seeds 42      # один прогон, чтобы оценить время
python experiments/run_gine_splits.py --protocols C --seeds 42 --device cpu   # пилот C
```

Результаты:

- `derived/results_gine.csv` — строка на (protocol, seed)
- `derived/predictions/gine_{A,B}_seed{N}.csv` — вероятности на val и test
- `derived/gine_models/gine_{A,B}_seed{N}.pt` — веса лучшей эпохи (в git не попадают)
- `experiments/logs/run_gine_splits.txt` — текстовый отчёт
- `derived/configs/gine_{protocol}_seed{N}.json` — конфигурация запуска (настройки, эпоха, температура, пороги)
- `derived/results_pilot_C_gine.csv`
- `derived/predictions/gine_C_seed42.csv`
- `experiments/logs/pilot_C_gine.txt`

## h1_table.py

Задача 4, итог: таблица «модель × протокол» (среднее ± std по seed) и разница A − B для проверки H1.

```
python experiments/h1_table.py
```

Результаты:

- `derived/h1_table.md` — отчёт: таблицы среднее ± std, разница A − B и пояснения к столбцам
- `derived/h1_table.csv` — среднее ± std (для дальнейшей обработки)
- `derived/h1_diff.csv` — разница A − B по каждой модели и метрике (числа без округления)

## make_split_c.py

Пункт 2 (неделя 2–8.11.2026). Протокол C — разбиение по исполняемым файлам.

```
python experiments/make_split_c.py
```

Результаты:

- `derived/splits/C_seed{N}.json` — индексы строк (row_idx исходного CSV) для train / val / test
- `derived/splits/groups_C.csv` — группа C для каждой строки (row_idx, label, seq_hash, sha256_file, group_c, ...)
- `derived/splits/summary_C.csv` — размеры частей, доли malware, крупнейшая группа в test, критерии
- `experiments/logs/make_split_c.txt текстовый отчёт (то же`
- `что на экране)`

## pilot_c_table.py

Пункт 3 (неделя 2–8.11.2026), итог: таблица пилота на разбиении C.

```
python experiments/baseline_tfidf.py --protocols C --seeds 42 --blocks main
python experiments/run_gine_splits.py --protocols C --seeds 42 --device cpu
python experiments/pilot_c_table.py
```

Результаты:

- `derived/pilot_C_table.md` — отчёт: таблица пилота, выбранные на val настройки, контекст A/B
- `derived/pilot_C_table.csv` — числа пилота без округления (строка на модель)

## collect_env.py

Пункт 4 (неделя 2–8.11.2026). Окружение и карта скриптов — для воспроизводимости.

```
python experiments/collect_env.py
```

Результаты:

- `ENVIRONMENT.md` — окружение: таблица версий и как воспроизвести
- `requirements.txt` — точные версии библиотек, которые импортируют скрипты
- `requirements-freeze.txt` — все установленные пакеты (name==version)
- `experiments/COMMANDS.md` — карта скриптов experiments/: порядок, назначение, команды, результаты

## log_run.py

Журнал запусков: строка в EXPERIMENTS.csv появляется в начале запуска (status=running)

Модуль, сам не запускается: его импортируют другие скрипты.

## eval_utils.py

Общие функции задачи 4: загрузка данных и разбиений, подбор порогов на val, метрики на test.

Модуль, сам не запускается: его импортируют другие скрипты.
