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

В каждой папке с кодом есть `COMMANDS.md` — готовые команды запуска (обучение, генерация, классификация).

## Как устроен пайплайн

1. **Данные.** `MalbehavD-V1-main/MalBehavD-V1-dataset.csv` — широкий формат: `sha256`, `labels`, колонки `0..N` с именами API.
2. **Детектор.** Обучение GINE: `train_gine.py` → предсказание и метрики: `predict_gine.py`; многократные сплиты: `run_splits.py`.
3. **Генерация.** TextGAN или Diffusion-LM создают синтетические последовательности и сохраняют их в тот же CSV-формат.
4. **Оценка синтетики.** `generation_quality_checks.py` (качество генерации) и классификация синтетики обученным детектором.

Сквозной порядок прогонов — в [0 - docs/experiments-log.md](<0 - docs/experiments-log.md>).

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
