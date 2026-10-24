# Команды: my-GINE-model upgrade 1

Запускать из корня репозитория (`Diplom`). Пути к папке с пробелами берутся в кавычки.

Две обученные модели, использованные в сравнениях (`0 - docs/model-comparison/`):

| Модель | Параметры | Файл |
|---|---|---|
| **A (e40)** | 40 эпох, lr 0.001, seed 42, порог 0.40, T=1.073 | `g_h128l3_b64e40_lr0p001_s42_270b5a10_be14_vf968.pt` |
| **B (e60)** | 60 эпох, lr 0.0005, seed 23, `--undirected --add-skip-edges`, порог 0.42, T=2.431 | `g_h128l3_b64e60_lr0p0005_s23_40b0098e_be32_vf931.pt` |

## 1. Обучение

### Модель A (e40)

```bat
python ".\my-GINE-model upgrade 1\train_gine.py" ^
  --csv ".\MalbehavD-V1-main\MalBehavD-V1-dataset.csv" ^
  --dataset-format auto --include-unnamed-api-cols ^
  --epochs 40 --batch-size 64 --device cpu ^
  --test-size 0.01 --val-size 0.1
```

### Модель B (e60)

```bat
python ".\my-GINE-model upgrade 1\train_gine.py" ^
  --csv ".\MalbehavD-V1-main\MalBehavD-V1-dataset.csv" ^
  --dataset-format auto --include-unnamed-api-cols ^
  --epochs 60 --batch-size 64 --lr 0.0005 --weight-decay 0.0003 --dropout 0.25 ^
  --undirected --add-skip-edges ^
  --select-metric mcc --threshold-grid 0.10:0.90:161 ^
  --test-size 0.1 --val-size 0.1 --seed 23 --device cpu
```

Результаты сохраняются в `my-GINE-model upgrade 1\runs\models\` (веса) и `runs\results\` (сводка прогона).

## 2. Классификация синтетики

Для модели B добавляются флаги `--undirected --add-skip-edges`, а в `--model-path` указывается её файл.

### TextGAN

```bat
python ".\my-GINE-model upgrade 1\predict_gine.py" ^
  --model-path ".\my-GINE-model upgrade 1\runs\models\g_h128l3_b64e40_lr0p001_s42_270b5a10_be14_vf968.pt" ^
  --vocab-path ".\my-GINE-model upgrade 1\runs\vocab\api_vocab.json" ^
  --input-csv ".\MalbehavD-V1-main\MalBehavD-V1-generated-5000x2.csv" ^
  --dataset-format auto --include-unnamed-api-cols --label-col labels --device cpu
```

### Diffusion-LM

```bat
python ".\my-GINE-model upgrade 1\predict_gine.py" ^
  --model-path ".\my-GINE-model upgrade 1\runs\models\g_h128l3_b64e40_lr0p001_s42_270b5a10_be14_vf968.pt" ^
  --vocab-path ".\my-GINE-model upgrade 1\runs\vocab\api_vocab.json" ^
  --input-csv ".\Diffusion-LM-main\improved-diffusion\runs\generation_outputs\malbehav_best_20260505\malbehav_generated_1500.csv" ^
  --dataset-format auto --include-unnamed-api-cols --label-col labels --device cpu
```

Метрики сохраняются в `runs\predictions\metrics_<модель>_<набор>_<hash>.txt`.

## 3. Сплиты

```bat
python ".\my-GINE-model upgrade 1\run_splits.py" ^
  --csv ".\MalbehavD-V1-main\MalBehavD-V1-dataset.csv" ^
  --label-col labels --dataset-format auto --include-unnamed-api-cols ^
  --train-per-class 650 --num-runs 5 --base-seed 42 ^
  --device cpu --epochs 30 --batch-size 64 --lr 0.001 --dropout 0.3 --threshold 0.5
```
