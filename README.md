# Диплом: детектирование malware по последовательностям API-вызовов

Классификатор malware / benign на графовой модели GINE, обучаемый на датасете MalBehavD-V1, и генеративная аугментация данных (RelGAN, Diffusion-LM).

Вопросы исследования и план работ — в [0 - docs/plan-diploma.md](<0 - docs/plan-diploma.md>).

## Структура репозитория

| Папка / файл | Что это |
|---|---|
| [MalbehavD-V1-main/](MalbehavD-V1-main/) | Датасет MalBehavD-V1 (1285 benign + 1285 malware), чужой README и лицензия |
| [my-GINE-model/](my-GINE-model/) | Базовая GINE-модель (первая версия) |
| [my-GINE-model upgrade 1/](<my-GINE-model upgrade 1/>) | Улучшенная GINE-модель: checkpoint-формат, подбор порога, temperature scaling. **Рабочая версия** |
| [TextGAN-PyTorch-master/](TextGAN-PyTorch-master/) | RelGAN для генерации синтетических последовательностей (отдельные модели для goodware и malware) |
| [Diffusion-LM-main/](Diffusion-LM-main/) | Diffusion-LM, адаптированный под MalBehavD-V1 |
| [0 - docs/](<0 - docs/>) | Заметки, план, журнал экспериментов, отчёты; еженедельные конспекты и отчёты по пунктам — в `0 - docs/conspects/` |
| [ДОКИ ГАЛАНОВ/](<ДОКИ ГАЛАНОВ/>) | Документы руководителя: задания по неделям, план диплома, список литературы, черновик «Наработки диплома» |
| [experiments/](experiments/) | Скрипты экспериментов ВКР (аудит, разбиения, протоколы A/B/C, пилот C) и их текстовые отчёты в `experiments/logs/` |
| [derived/](derived/) | Производные данные и результаты скриптов из `experiments/`. Исходный датасет не меняется |
| [EXPERIMENTS.csv](EXPERIMENTS.csv) | Журнал всех запусков, включая неудачные |
| [ENVIRONMENT.md](ENVIRONMENT.md), [requirements.txt](requirements.txt), [requirements-freeze.txt](requirements-freeze.txt) | Окружение, на котором получены результаты: версии Python, библиотек, CUDA, GPU |

В каждой папке с кодом есть `COMMANDS.md` — готовые команды запуска (обучение, генерация, классификация). Для `experiments/` это [experiments/COMMANDS.md](experiments/COMMANDS.md) — карта скриптов в порядке пайплайна.

## Воспроизведение

1. Окружение — [ENVIRONMENT.md](ENVIRONMENT.md): версии и как поставить (`requirements.txt`; PyTorch и torch_geometric — под свою CUDA).
2. Команды в порядке запуска — [experiments/COMMANDS.md](experiments/COMMANDS.md). Короткий порядок:
   ```
   python experiments/audit_duplicates.py
   python experiments/leak_check.py
   python experiments/make_splits.py
   python experiments/baseline_tfidf.py
   python experiments/run_gine_splits.py
   python experiments/h1_table.py
   python experiments/make_split_c.py
   python experiments/baseline_tfidf.py --protocols C --seeds 42 --blocks main
   python experiments/run_gine_splits.py --protocols C --seeds 42 --device cpu
   python experiments/pilot_c_table.py
   ```
3. Оба файла пересобираются командой `python experiments/collect_env.py` (карта — из docstring скриптов, поэтому не расходится с кодом).
4. GINE на GPU недетерминирован: при повторе числа могут немного отличаться; на CPU (`--device cpu`) повторяются точно.

## Как устроен пайплайн

1. **Данные.** `MalbehavD-V1-main/MalBehavD-V1-dataset.csv` — широкий формат: `sha256`, `labels`, колонки `0..N` с именами API.
2. **Детектор.** Обучение GINE: `train_gine.py` → предсказание и метрики: `predict_gine.py`; многократные сплиты: `run_splits.py`.
3. **Генерация.** TextGAN или Diffusion-LM создают синтетические последовательности и сохраняют их в тот же CSV-формат.
4. **Оценка синтетики.** `generation_quality_checks.py` (качество генерации) и классификация синтетики обученным детектором.

Сквозной порядок прогонов — в [0 - docs/experiments-log.md](<0 - docs/experiments-log.md>).

## Результаты по неделям

<details>
<summary><b>Неделя 1 (26.10–01.11.2026): файлы в experiments/ и derived/</b></summary>

Все пути — от корня репозитория. `{A,B}` — протокол разбиения, `seed{42..46}` — пять seed, то есть шаблон `X_{A,B}_seed{42..46}` означает 10 файлов: `X_A_seed42` … `X_A_seed46`, `X_B_seed42` … `X_B_seed46`.

Протокол **A** — случайное стратифицированное разбиение строк (`StratifiedKFold`). Протокол **B** — групповое: все копии одной последовательности API (одинаковый `seq_hash`) в одной части. Обе схемы: 5 фолдов, фолд 0 → test, фолд 1 → val, фолды 2–4 → train (≈ 1534 / 512 / 512 строк).

### experiments/ — скрипты

| Файл | Что делает | Читает | Пишет |
|---|---|---|---|
| [log_run.py](experiments/log_run.py) | Модуль журнала: добавляет строку в `EXPERIMENTS.csv` при старте (`running`) и обновляет её в конце (`ok` / `failed` / `interrupted`), записывает параметры, seed, sha256 датасета и файла разбиения, метрики. Подключён ко всем скриптам ниже, а также к GINE (обе версии), RelGAN и Diffusion-LM | — | `EXPERIMENTS.csv` |
| [audit_duplicates.py](experiments/audit_duplicates.py) | Задача 1. Хэширует последовательность API каждой строки (`seq_hash`), считает дубли, группы дублей и конфликты меток | исходный CSV датасета | `derived/hashes.csv`, `derived/audit_duplicates_table.csv`, `derived/audit_top5_groups.csv`, `experiments/logs/audit_duplicates.txt` |
| [leak_check.py](experiments/leak_check.py) | Задача 2. Вызывает функцию разбиения из `my-GINE-model upgrade 1/run_splits.py` (900 строк на класс в train, остальное — eval, seed 42–46) и считает, сколько eval-строк имеют копию последовательности в train. Модель не обучает | исходный CSV, `derived/hashes.csv` | `derived/leak_check_run_splits.csv`, `experiments/logs/leak_check.txt` |
| [make_splits.py](experiments/make_splits.py) | Задача 3. Строит разбиения A и B для seed 42–46, исключает строки последовательности с конфликтующими метками, проверяет, что в B ни одна последовательность не разорвана между частями. Группы в B раскладываются сбалансированной жадной схемой (`--group-method balanced`, по умолчанию; вариант `sgkf` — `StratifiedGroupKFold`) | `derived/hashes.csv` | `derived/splits/*.json`, `derived/splits/summary.csv`, `experiments/logs/make_splits.txt` |
| [eval_utils.py](experiments/eval_utils.py) | Общие функции задачи 4 (сам не запускается): загрузка данных и разбиений, подбор порога по MCC на val, порог для TPR = 0.95 на val, метрики на test (в том числе на дедуплицированном test), доля OOV, сохранение предсказаний | — | — |
| [baseline_tfidf.py](experiments/baseline_tfidf.py) | Задача 4, модель 1. TF-IDF по n-граммам API + логистическая регрессия; C выбирается по MCC на val. Блок `main` — n-граммы 1–3; блок `ngram1` — проверка только на 1-граммах (без порядка вызовов). `--blocks` выбирает блоки | `derived/splits/*.json`, исходный CSV, `derived/hashes.csv` | `derived/results_tfidf.csv`, `derived/results_tfidf_ngram1.csv`, `derived/predictions/tfidf_*`, `experiments/logs/baseline_tfidf*.txt` |
| [run_gine_splits.py](experiments/run_gine_splits.py) | Задача 4, модель 2. GINE в конфигурации e40 из НИРС (hidden 128, 3 слоя, dropout 0.3, 40 эпох, lr 1e-3, temperature scaling). Код модели импортируется из `my-GINE-model upgrade 1`. Словарь API — по train, эпоха — по MCC на val, температура и пороги — по val | те же | `derived/results_gine.csv`, `derived/predictions/gine_*`, `derived/gine_models/*.pt`, `experiments/logs/run_gine_splits.txt` |
| [h1_table.py](experiments/h1_table.py) | Задача 4, итог. Среднее ± std по seed, разница A − B, t-тест Уэлча, сравнение «все строки / dedup», проверка на 1-граммах | `derived/results_*.csv` | `derived/h1_table.md`, `derived/h1_table.csv`, `derived/h1_diff.csv` |

### experiments/logs/ — текстовые отчёты скриптов

Каждый файл перезаписывается при новом запуске своего скрипта; в каждом есть пояснения к столбцам.

| Файл | Содержание |
|---|---|
| [audit_duplicates.txt](experiments/logs/audit_duplicates.txt) | Сводная таблица дублей и пять самых больших групп |
| [leak_check.txt](experiments/logs/leak_check.txt) | Доля eval-строк с копией в train по каждому seed, среднее и std |
| [make_splits.txt](experiments/logs/make_splits.txt) | Размеры частей, доля malware, утечка и разорванные последовательности по каждому разбиению A и B |
| [baseline_tfidf.txt](experiments/logs/baseline_tfidf.txt) | TF-IDF (1–3-граммы): метрики по каждому протоколу и seed |
| [baseline_tfidf_ngram1.txt](experiments/logs/baseline_tfidf_ngram1.txt) | То же для проверки на 1-граммах |
| [run_gine_splits.txt](experiments/logs/run_gine_splits.txt) | GINE: метрики, лучшая эпоха, время обучения по каждому протоколу и seed |

### derived/ — данные и результаты

Исходный датасет не меняется; всё производное лежит здесь.

| Файл | Создаёт | Содержание |
|---|---|---|
| [hashes.csv](derived/hashes.csv) | `audit_duplicates.py` | Строка на каждую запись датасета (2570): `row_idx` — номер строки в исходном CSV; `sha256_file` — хэш файла из датасета; `label` — 0 benign / 1 malware; `seq_hash` — sha256 последовательности API; `seq_len` — число вызовов. Основа для всех следующих скриптов |
| [audit_duplicates_table.csv](derived/audit_duplicates_table.csv) | `audit_duplicates.py` | Сводка дублей (столбцы `all`, `benign`, `malware`): всего строк; уникальных последовательностей, из них только в одном классе и общих для обоих; строк в группах дублей (группа ≥ 2 строк); лишних копий (строк минус уникальных); последовательностей и строк с конфликтующими метками; строк с повторяющимся sha256 файла |
| [audit_top5_groups.csv](derived/audit_top5_groups.csv) | `audit_duplicates.py` | Пять самых больших групп дублей: `rank`, `seq_hash`, `size` (строк в группе), `benign` / `malware` (сколько строк каждого класса), `seq_len`, `example_row` (пример `row_idx`) |
| [leak_check_run_splits.csv](derived/leak_check_run_splits.csv) | `leak_check.py` | Строка на seed 42–46 плюс строки `mean` и `std`: `train_rows` / `eval_rows`; `eval_with_copy` — eval-строк, чья последовательность есть в train; `share_all` / `share_benign` / `share_malware` — их доля всего и по классам; `share_copy_same_label` — доля eval-строк с копией в train той же метки; `eval_unique_seqs` — уникальных последовательностей в eval; `eval_unique_seqs_with_copy` — из них встречающихся в train |
| [splits/{A,B}_seed{42..46}.json](derived/splits/) (10 файлов) | `make_splits.py` | Одно разбиение: списки `row_idx` в `train`, `val`, `test`; `protocol`, `seed`, `scheme`, `group` (`null` для A, `seq_hash` для B), `group_method`, `excluded_conflict_rows` (12 исключённых строк), `hashes_csv_sha256` — по какой версии `hashes.csv` построено. Все модели задачи 4 берут разбиения отсюда |
| [splits/summary.csv](derived/splits/summary.csv) | `make_splits.py` | Строка на разбиение: `n_train` / `n_val` / `n_test` и доля malware в каждой части; `leak_val` / `leak_test` — доля строк val / test, чья последовательность есть в train; `seqs_in_several_parts` — последовательностей, разорванных между частями (в B всегда 0); `repeated_files_split` / `repeated_files_total` — повторяющихся sha256 файла, оказавшихся в разных частях / всего |
| [results_tfidf.csv](derived/results_tfidf.csv) | `baseline_tfidf.py` (блок `main`) | TF-IDF 1–3-граммы, строка на (протокол, seed). Выбор на val: `C`, `val_mcc`, `thr_mcc` (порог по максимуму MCC), `thr_tpr95` (порог для TPR = 0.95). Модель: `n_features`. Метрики на test: `mcc`, `f1`, `pr_auc`, `roc_auc`, `fpr_at_tpr95`, `tpr_at_tpr95`; `dedup_*` — то же на дедуплицированном test; `n_test` / `n_test_dedup`; `oov_call_share` / `oov_seq_share` — доля вызовов / трасс test с API, которого нет в train |
| [results_tfidf_ngram1.csv](derived/results_tfidf_ngram1.csv) | `baseline_tfidf.py` (блок `ngram1`) | Те же столбцы для TF-IDF только на 1-граммах |
| [results_gine.csv](derived/results_gine.csv) | `run_gine_splits.py` | GINE, строка на (протокол, seed): `best_epoch`, `val_mcc_at_0.5` (MCC на val в лучшую эпоху при пороге 0.5), `temperature`, `vocab_size` (словарь по train, включая `<UNK>`), `thr_mcc`, `thr_tpr95`, `train_sec`; метрики на test и `dedup_*`, `n_test` / `n_test_dedup`, доля OOV — как в `results_tfidf.csv` |
| [predictions/tfidf_{A,B}_seed{42..46}.csv](derived/predictions/) (10 файлов) | `baseline_tfidf.py` | Вероятность malware по каждой строке val и test: `row_idx`, `part` (`val` / `test`), `label`, `seq_hash`, `prob`. Нужны для анализа ошибок и бутстрепа без переобучения |
| [predictions/tfidf_ngram1_{A,B}_seed{42..46}.csv](derived/predictions/) (10 файлов) | `baseline_tfidf.py` | То же для 1-грамм |
| [predictions/gine_{A,B}_seed{42..46}.csv](derived/predictions/) (10 файлов) | `run_gine_splits.py` | То же для GINE (вероятности после temperature scaling) |
| `gine_models/gine_{A,B}_seed{42..46}.pt` (10 файлов) | `run_gine_splits.py` | Веса GINE лучшей эпохи. **В git не хранятся** (`*.pt` в `.gitignore`), воспроизводятся повторным запуском |
| [h1_table.md](derived/h1_table.md) | `h1_table.py` | **Итоговый отчёт по H1**: среднее ± std по 5 seed для каждой модели и протокола (все строки test и дедуплицированный test), сравнение «все строки против dedup», разница A − B, проверка на 1-граммах; пояснения к столбцам внутри |
| [h1_table.csv](derived/h1_table.csv) | `h1_table.py` | Строка на (модель, протокол): `n_seeds` и каждая метрика в виде «среднее ± std» |
| [h1_diff.csv](derived/h1_diff.csv) | `h1_table.py` | Строка на (модель, метрика), числа без округления: `mean_A`, `mean_B`, `diff_A_minus_B`, `std_A`, `std_B`, `diff_to_max_std` (\|разница\| / наибольший std), `A_better`, `welch_p` (p-value t-теста Уэлча) |

Журнал всех запусков этих скриптов — [EXPERIMENTS.csv](EXPERIMENTS.csv) в корне.

</details>

<details>
<summary><b>Неделя 2 (02.11–08.11.2026): файлы в experiments/ и derived/</b></summary>

Протокол **C** — разбиение по исполняемым файлам: строки объединяются в группу, если у них одинаковый `sha256_file` или одинаковый `seq_hash`, включая транзитивные связи (компоненты связности); группа целиком попадает в одну часть. Схема та же, что в A/B: 5 фолдов, фолд 0 → test, фолд 1 → val, фолды 2–4 → train; те же 12 конфликтных строк исключены. Правила разбиения и пилота записаны в docstring `make_split_c.py` и `pilot_c_table.py` и закоммичены до запуска.

**Итоги недели** (подробно — отчёты в [0 - docs/conspects/week2/](<0 - docs/conspects/week2/>)):

- Пункт 1 — интерпретация A/B: таблица MCC / F1 / метрик по уникальным трассам с источниками чисел, ограничения формулировок, пояснение про 12 исключённых строк — [П1_интерпретация_AB.docx](<0 - docs/conspects/week2/П1_интерпретация_AB.docx>).
- Пункт 2 — разбиение C пригодно: все критерии выполнены для seed 42–46, общих файлов и трасс между частями нет; для пилота зафиксирован `C_seed42` — [П2_разбиение_C.docx](<0 - docs/conspects/week2/П2_разбиение_C.docx>).
- Пункт 3 — пилот на `C_seed42`: TF-IDF + LR MCC 0.931 (0.896 по уникальным трассам), GINE 0.887 (0.830); превосходство GINE не показано; одно разбиение, без выводов о значимости — [П3_пилот_C.docx](<0 - docs/conspects/week2/П3_пилот_C.docx>).
- Пункт 4 (техническая часть) — окружение и карта скриптов: [ENVIRONMENT.md](ENVIRONMENT.md), [experiments/COMMANDS.md](experiments/COMMANDS.md).

### experiments/ — новые и изменённые скрипты

| Файл | Что делает / что изменено | Читает | Пишет |
|---|---|---|---|
| [make_split_c.py](experiments/make_split_c.py) | **Новый.** Пункт 2. Строит группы C (union-find по `sha256_file` и `seq_hash`; `sha256_file` нормализуется, некорректные id связываются только по трассе), раскладывает их по фолдам той же жадной схемой, что B, для seed 42–46. Проверяет: каждая группа, трасса и файл — ровно в одной части; группы одного класса; повторный расчёт даёт те же индексы. Считает критерии пригодности К1–К3 и печатает вывод | `derived/hashes.csv` | `derived/splits/C_seed*.json`, `derived/splits/groups_C.csv`, `derived/splits/summary_C.csv`, `experiments/logs/make_split_c.txt` |
| [pilot_c_table.py](experiments/pilot_c_table.py) | **Новый.** Пункт 3, итог. Правила пилота в docstring. Собирает таблицу двух моделей на `C_seed42`: метрики по всем строкам и уникальным трассам, время обучения, что выбрано на val, контекст A/B | `derived/results_pilot_C_*.csv`, `derived/h1_table.csv`, `derived/splits/summary_C.csv` | `derived/pilot_C_table.md`, `derived/pilot_C_table.csv` |
| [collect_env.py](experiments/collect_env.py) | **Новый.** Пункт 4. Окружение (ОС, Python, версии библиотек, CUDA, GPU) и карта скриптов из их docstring. Модели не обучает, данные не читает | docstring скриптов `experiments/` | `ENVIRONMENT.md`, `requirements.txt`, `requirements-freeze.txt`, `experiments/COMMANDS.md` |
| [make_splits.py](experiments/make_splits.py) | **Изменён:** `assign_groups_balanced` принимает имя столбца группы (`group_col`, по умолчанию `seq_hash`), чтобы C использовал ту же раскладку. Разбиения A/B не изменились (проверено побайтовым сравнением) | — | — |
| [baseline_tfidf.py](experiments/baseline_tfidf.py) | **Изменён:** `--protocols C` (только вместе с `--blocks main`, результаты — в отдельные файлы `pilot_C_*`); время обучения `train_sec` (вместе с подбором C); конфигурация запуска в `derived/configs/` | — | `derived/results_pilot_C_tfidf.csv`, `derived/configs/tfidf_*.json` |
| [run_gine_splits.py](experiments/run_gine_splits.py) | **Изменён:** `--protocols C` (результаты — в `pilot_C_*`), конфигурация запуска в `derived/configs/`. Пилот запускается на CPU (`--device cpu`) | — | `derived/results_pilot_C_gine.csv`, `derived/configs/gine_*.json` |
| [eval_utils.py](experiments/eval_utils.py) | **Изменён:** `is_pilot` (C запускается отдельно от A/B, иначе ошибка) и `save_config` (конфигурация запуска в JSON) | — | — |

### experiments/logs/ — текстовые отчёты скриптов

| Файл | Содержание |
|---|---|
| [make_split_c.txt](experiments/logs/make_split_c.txt) | Число групп C, распределение размеров, пять крупнейших групп, критерий К1, таблица по seed (размеры, доли malware, пересечения, крупнейшая группа test, К2, К3), вывод о пригодности |
| [pilot_C_tfidf.txt](experiments/logs/pilot_C_tfidf.txt) | TF-IDF на `C_seed42`: выбранный C, метрики, время обучения |
| [pilot_C_gine.txt](experiments/logs/pilot_C_gine.txt) | GINE на `C_seed42`: лучшая эпоха, метрики, время обучения |

### derived/ — данные и результаты

| Файл | Создаёт | Содержание |
|---|---|---|
| [splits/C_seed{42..46}.json](derived/splits/) (5 файлов) | `make_split_c.py` | Одно разбиение C: списки `row_idx` в `train`, `val`, `test`; `pilot` (true только у seed 42); `group`, `group_method`, `scheme`; `excluded_conflict_rows` (12 строк); `invalid_file_id_rows` (строки с некорректным `sha256_file`, здесь пусто); `criteria` (К1–К3); `hashes_csv_sha256` |
| [splits/groups_C.csv](derived/splits/groups_C.csv) | `make_split_c.py` | Строка на каждую из 2558 строк: `row_idx`, `label`, `seq_hash`, `sha256_file`, `file_key` (нормализованный id, пусто — некорректный), `group_c` (номер группы = наименьший `row_idx` в ней), `group_size` |
| [splits/summary_C.csv](derived/splits/summary_C.csv) | `make_split_c.py` | Строка на seed: `n_*` и `malware_share_*` по частям; `n_test_unique_seqs`; `seqs_in_several_parts`, `files_in_several_parts` (должно быть 0); `largest_test_group`, `largest_test_group_label`, `largest_test_group_share_of_class`; `largest_group_part` — где крупнейшая группа датасета; `K2_sizes`, `K3_balance` |
| [results_pilot_C_tfidf.csv](derived/results_pilot_C_tfidf.csv) | `baseline_tfidf.py --protocols C` | Как `results_tfidf.csv`, плюс `train_sec` |
| [results_pilot_C_gine.csv](derived/results_pilot_C_gine.csv) | `run_gine_splits.py --protocols C` | Как `results_gine.csv` |
| [predictions/{tfidf,gine}_C_seed42.csv](derived/predictions/) (2 файла) | те же | Вероятность malware по каждой строке val и test (`row_idx`, `part`, `label`, `seq_hash`, `prob`) |
| [configs/{tfidf,gine}_C_seed42.json](derived/configs/) (2 файла) | те же | Конфигурация запуска: `split_file` и его `split_sha256`; `settings` — все настройки модели; `selected_on_val` — что выбрано на val (C или эпоха и температура, пороги); `train_sec`; у TF-IDF `n_features`, у GINE `vocab_size` и `model_file` |
| `gine_models/gine_C_seed42.pt` | `run_gine_splits.py --protocols C` | Веса GINE лучшей эпохи. **В git не хранится** |
| [pilot_C_table.md](derived/pilot_C_table.md) | `pilot_c_table.py` | **Итоговый отчёт пилота**: метрики обеих моделей по всем строкам и уникальным трассам, время, что выбрано на val, средние A/B для контекста |
| [pilot_C_table.csv](derived/pilot_C_table.csv) | `pilot_c_table.py` | Те же числа без округления, строка на модель |

### Корень и 0 - docs/

| Файл | Что это |
|---|---|
| [ENVIRONMENT.md](ENVIRONMENT.md), [requirements.txt](requirements.txt), [requirements-freeze.txt](requirements-freeze.txt) | Окружение (создаёт `collect_env.py`) |
| [experiments/COMMANDS.md](experiments/COMMANDS.md) | Карта скриптов в порядке пайплайна (создаёт `collect_env.py`) |
| [0 - docs/conspects/week2/](<0 - docs/conspects/week2/>) | Отчёты по пунктам 1–3 (`.docx` и исходный `.md`) |
| [0 - docs/tools/](<0 - docs/tools/>) | Шаблон Word (`reference.docx`) и `fix_pandoc_docx.py` для сборки отчётов из Markdown через pandoc |

</details>

## Документы

- [0 - docs/conspects/](<0 - docs/conspects/>) — конспекты по неделям (`week1-results.docx`) и отчёты по пунктам заданий (`week2/`)
- [ДОКИ ГАЛАНОВ/](<ДОКИ ГАЛАНОВ/>) — задания руководителя по неделям, план диплома до защиты, литература
- [0 - docs/plan-diploma.md](<0 - docs/plan-diploma.md>) — вопросы исследования RQ1–RQ3, этапы, структура записки
- [0 - docs/datasets-review.md](<0 - docs/datasets-review.md>) — аудит MalBehavD-V1 и выбор нового датасета
- [0 - docs/reports/Датасеты и методы детекции malware.md](<0 - docs/reports/Датасеты и методы детекции malware.md>) — углублённое исследование: датасеты, работы 2024–2026, новизна, план
- [0 - docs/datasets-round2.md](<0 - docs/datasets-round2.md>) — второй раунд поиска датасетов (Fellicious, DataCon 2019, DMBD и др.)
- [0 - docs/datasets-inspection.md](<0 - docs/datasets-inspection.md>) — проверка на реальных файлах: Quo Vadis, DataCon 2019, Fellicious
- [0 - docs/benign-datasets.md](<0 - docs/benign-datasets.md>) — готовые benign-наборы и рецепт собственного benign через CAPE
- [0 - docs/research-models.md](<0 - docs/research-models.md>) — обзор методов и рекомендация основного метода
- [0 - docs/experiments-log.md](<0 - docs/experiments-log.md>) — журнал прогонов на MalBehavD-V1
- [0 - docs/model-comparison/](<0 - docs/model-comparison/>) — сравнения base и upgrade 1 (обучение и классификация синтетики), `.txt` и `.csv`
- [0 - docs/gine-improvements-report.docx](<0 - docs/gine-improvements-report.docx>) — отчёт об улучшении GINE-модели
- [0 - docs/archive/](<0 - docs/archive/>) — черновые копии отчёта и старые заметки

## Что не хранится в git

Правила в [.gitignore](.gitignore): `__pycache__`, чекпоинты (`*.pt`, `*.pth`, …), массивы (`*.npy`, `*.npz`) и папки `runs/` обеих GINE-моделей. Модели и результаты прогонов нужно перегенерировать командами из `COMMANDS.md`.
