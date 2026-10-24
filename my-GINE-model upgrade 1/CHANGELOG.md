# Что изменено относительно базовой my-GINE-model

Порядок улучшений взят из отчёта [0 - docs/gine-improvements-report.docx](<../0 - docs/gine-improvements-report.docx>).

## План

1. **Устойчивые чекпоинты и инференс.** `predict_gine.py` хардкодил `edge_dim=3` и разбирал архитектуру по имени файла. Это ломает расширения модели. Нужен checkpoint-словарь: `state_dict` + `model_args` + `vocab_size` + `edge_dim` + `threshold` (+ `temperature`).
2. **Operational-слой решения.** Подбор порога на validation, сохранение его в чекпоинт, затем temperature scaling и метрики PR-AUC / MCC / Brier (ECE опционально).
3. **Embedding вместо one-hot.** One-hot в `graph_data.py` — главное узкое место по памяти и обобщению. Минимум: `api_id` → `nn.Embedding`, плюс позиция `i/L` и `log1p(freq)` как числовые признаки.
4. **Более сильный граф.** Multi-scale рёбра (skip-strides вместо одного `i→i+2`) и attention pooling / JK вместо `global_add_pool`. Делать после пп. 1–3, чтобы не усложнять отладку.

## Статус

| Пункт | Статус |
|---|---|
| 1. Checkpoint-формат | сделан |
| 2. Порог, temperature scaling, PR-AUC/MCC/Brier | сделан |
| 3. Embedding вместо one-hot | не сделан |
| 4. Multi-scale рёбра, attention pooling | не сделан |

## Пункт 1: что изменено

- После выбора лучшей модели сохраняется checkpoint-словарь, а не «голый» `state_dict`: `schema_version`, `state_dict`, `model_args` (`num_node_features`, `edge_dim`, `hidden_dim`, `num_layers`, `num_classes`, `dropout`), `vocab_size`, `threshold`.
- В `predict_gine.py` убран хардкод `edge_dim=3`. Сначала читается checkpoint (или legacy-файл), архитектура берётся из `model_args`, иначе выводится из `state_dict`, и только потом идёт fallback на имя файла.
- Порог берётся из checkpoint, если не передан в CLI: `--threshold` теперь `default=None`, итог = CLI → checkpoint → 0.5.
- Добавлена защита от несоответствия словаря: если `vocab_size` из checkpoint не совпадает с переданным `vocab.json`, выдаётся явная ошибка.
- Добавлен `--edge-dim` как ручной fallback для редких случаев.
- Совместимость: старые `.pt` с `state_dict` продолжают работать, новые тренировки сохраняются в новом формате.

## Пункт 2: что добавлено

- Метрики PR-AUC, MCC, Brier в расчёте train/eval.
- Подбор лучшего порога на validation по сетке (`--threshold-grid`) и метрике (`--select-metric f1|mcc`).
- Temperature scaling по validation logits.
- Tuned threshold и temperature сохраняются в checkpoint.
- `predict_gine.py` применяет `softmax(logits / temperature)` и порог из checkpoint (если нет override через CLI).
- Новые CLI-аргументы: `--select-metric`, `--threshold-grid`, `--calibration` (только `none|temperature`); для предсказания — `--temperature` (override).
