# Команды: my-GINE-model (базовая версия)

Запускать из корня репозитория (`Diplom`).

## Обучение

Быстрый старт на MalBehavD-V1 (**лучший вариант**):

```bat
python .\my-GINE-model\train_gine.py ^
    --csv .\MalbehavD-V1-main\MalBehavD-V1-dataset.csv ^
    --dataset-format auto --include-unnamed-api-cols --epochs 40 --batch-size 64 ^
    --test-size 0.01 --val-size 0.1
```

Без внутреннего split:

```bat
python .\my-GINE-model\train_gine.py --csv .\my-GINE-model\runs\splits\train_1300.csv --dataset-format auto --include-unnamed-api-cols --no-internal-split
```

Для датасета с одной колонкой последовательности (`single_seq`):

```bat
python .\my-GINE-model\train_gine.py --csv .\data\your_dataset.csv --dataset-format single_seq --label-col label --seq-col api_sequence
```

Полная справка по аргументам:

```bat
python .\my-GINE-model\train_gine.py --help
```

## Предсказание

Одна последовательность:

```bat
python .\my-GINE-model\predict_gine.py --model-path .\my-GINE-model\runs\models\<модель>.pt --vocab-path .\my-GINE-model\runs\vocab\api_vocab.json --input-seq "NtOpenFile NtReadFile NtClose"
```

CSV + метрики (**лучший вариант**):

```bat
python .\my-GINE-model\predict_gine.py ^
    --model-path .\my-GINE-model\runs\models\g_h128l3_b64e40_lr0p001_s42_270b5a10_be22_vf964.pt ^
    --vocab-path .\my-GINE-model\runs\vocab\api_vocab.json ^
    --input-csv .\MalbehavD-V1-main\MalBehavD-V1-generated-5000x2.csv ^
    --dataset-format auto --include-unnamed-api-cols --label-col labels
```

## Multi-split benchmark

```bat
python .\my-GINE-model\run_splits.py --csv .\MalbehavD-V1-main\MalBehavD-V1-dataset.csv --label-col labels --dataset-format auto --include-unnamed-api-cols --train-per-class 650 --num-runs 5 --base-seed 42
```

Разбиение на train/test с заданными именами файлов (один прогон):

```bat
python .\my-GINE-model\run_splits.py --csv .\MalbehavD-V1-main\MalBehavD-V1-dataset.csv --label-col labels --dataset-format auto --include-unnamed-api-cols --train-per-class 650 --num-runs 1 --base-seed 42 --train-filename-template train_custom.csv --eval-filename-template test_custom.csv
```

## Проверка качества генерации

```bat
python .\my-GINE-model\generation_quality_checks.py ^
  --real-csv .\MalbehavD-V1-main\MalBehavD-V1-dataset.csv ^
  --synthetic-csv .\MalbehavD-V1-main\MalBehavD-V1-generated-5000x2.csv ^
  --include-unnamed-api-cols ^
  --seeds 42,43,44,45,46
```

## Прочее

Сохранить историю командной строки cmd:

```bat
doskey /history > .\"History cmd"\history-02-04.txt
```
