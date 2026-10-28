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
| [0 - docs/](<0 - docs/>) | Заметки, план, журнал экспериментов, отчёты |
| [experiments/](experiments/) | Скрипты экспериментов ВКР (аудит, разбиения, протоколы A/B) и их текстовые отчёты в `experiments/logs/` |
| [derived/](derived/) | Производные данные и результаты скриптов из `experiments/`. Исходный датасет не меняется |
| [EXPERIMENTS.csv](EXPERIMENTS.csv) | Журнал всех запусков, включая неудачные |

В каждой папке с кодом есть `COMMANDS.md` — готовые команды запуска (обучение, генерация, классификация).

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

## Документы

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
