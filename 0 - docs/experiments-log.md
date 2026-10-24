# Журнал экспериментов

Сквозной порядок прогонов на MalBehavD-V1. Точные команды для каждого компонента лежат в `COMMANDS.md` его папки.
Пути к результатам ниже записаны как в оригинальной заметке; сами файлы результатов в этот репозиторий не переносились.

## 1. Генерация TextGAN (RelGAN)

Использованные модели (`gen_ADV_best.pt`, запуски от 2026-04-12):
- goodware: `save/20260412/MalbehavD-V1_goodware/…T0412_1811_20`
- malware: `save/20260412/MalbehavD-V1_malware/…T0412_2011_17`

```bat
python .\tools\generate_relgan_samples.py --dataset MalbehavD-V1_goodware ^
    --checkpoint save/20260412/MalbehavD-V1_goodware/relgan_vanilla_dt-Ra_lt-rsgan_mt-ra_et-Ra_sl153_temp40_lfd0.0_T0412_1811_20/models/gen_ADV_best.pt ^
    --output_txt .\generated\goodware_5000.txt --num_samples 5000 --batch_size 32
python .\tools\generate_relgan_samples.py --dataset MalbehavD-V1_malware ^
    --checkpoint save/20260412/MalbehavD-V1_malware/relgan_vanilla_dt-Ra_lt-rsgan_mt-ra_et-Ra_sl175_temp40_lfd0.0_T0412_2011_17/models/gen_ADV_best.pt ^
    --output_txt .\generated\malware_5000.txt --num_samples 5000 --batch_size 32
```

Результат генерации: `MalbehavD-V1-main\MalBehavD-V1-generated-5000x2.csv`

## 2. Обучение GINE на реальном MalBehavD-V1

```bat
python .\my-GINE-model\train_gine.py ^
    --csv .\MalbehavD-V1-main\MalBehavD-V1-dataset.csv ^
    --dataset-format auto --include-unnamed-api-cols --epochs 40 --batch-size 64 ^
    --test-size 0.01 --val-size 0.1
```

- Модель: `my-GINE-model\runs\models\g_h128l3_b64e40_lr0p001_s42_270b5a10_be22_vf964.pt`
- Лог обучения: `MalBehavD-V1-dataset+e40+b64+00-11__02-05-2026.txt`

## 3. Классификация синтетики TextGAN

```bat
python .\my-GINE-model\predict_gine.py ^
    --model-path .\my-GINE-model\runs\models\g_h128l3_b64e40_lr0p001_s42_270b5a10_be22_vf964.pt ^
    --vocab-path .\my-GINE-model\runs\vocab\api_vocab.json ^
    --input-csv .\MalbehavD-V1-main\MalBehavD-V1-generated-5000x2.csv ^
    --dataset-format auto --include-unnamed-api-cols --label-col labels
```

- Метрики: `metrics_g_h128l3_b64e40_lr0p001_s42_270b5a10_be22_vf964_MalBehavD-V1-generated-5000x2_2e232814.txt`
- Лог классификации: `log pred 5000.txt`

## 4. Качество генерации (5000×2)

- `my-GINE-model\runs\generation_quality\gen_quality_20260502_163608.json`
- `my-GINE-model\runs\generation_quality\gen_quality_20260502_163608.txt`

## 5. Diffusion-LM

Все команды (обучение, генерация, конвертация в CSV, оценка) — в [Diffusion-LM-main/COMMANDS.md](../Diffusion-LM-main/COMMANDS.md).

Классификация синтетики Diffusion-LM:

```bat
python .\my-GINE-model\predict_gine.py ^
    --model-path .\my-GINE-model\runs\models\g_h128l3_b64e40_lr0p001_s42_270b5a10_be22_vf964.pt ^
    --vocab-path .\my-GINE-model\runs\vocab\api_vocab.json ^
    --input-csv .\Diffusion-LM-main\improved-diffusion\runs\generation_outputs\malbehav_best_20260505\malbehav_generated_1500.csv ^
    --dataset-format auto --include-unnamed-api-cols --label-col labels
```

Метрики:
- `my-GINE-model\runs\predictions\0-metrics_g_h128l3_b64e40_lr0p001_s42_270b5a10_be22_vf964_malbehav_generated_1500_fff55b25.txt` (запуск чата)
- `my-GINE-model\runs\predictions\metrics_g_h128l3_b64e40_lr0p001_s42_270b5a10_be22_vf964_malbehav_generated_1500_fff55b25.txt` (свой прогон)

## 6. Сплиты по модели

```bat
python ".\my-GINE-model\run_splits.py" ^
  --csv ".\MalbehavD-V1-main\MalBehavD-V1-dataset.csv" ^
  --label-col labels --dataset-format auto --include-unnamed-api-cols ^
  --train-per-class 900 --num-runs 5 --base-seed 42 ^
  --device cpu --epochs 50 --batch-size 32 --lr 0.0005 --dropout 0.2
```

## 7. Сравнение моделей base и upgrade 1

Сводки лежат в [model-comparison/](model-comparison/):

| Файл | Что сравнивается |
|---|---|
| 01-обучение-base-vs-upgrade | результаты обучения base и upgrade 1 (тест 26 объектов) |
| 02-классификация-TextGAN-base-vs-upgrade | классификация TextGAN-синтетики (10000 строк) |
| 03-классификация-TextGAN-upgrade-e40-vs-e60 | две модели upgrade 1 (e40, seed 42 и e60, seed 23) на той же синтетике |
| 04-классификация-DiffusionLM-base-vs-upgrade | классификация Diffusion-LM-синтетики (3000 строк) |
| 05-классификация-DiffusionLM-upgrade-e60-vs-e40 | две модели upgrade 1 на синтетике Diffusion-LM |

Все сравнения от 2026-05-11. Выводы по ним:
- TextGAN: upgrade 1 (e40) лучше base по F1 (0.9760 против 0.9727), но чуть хуже по precision.
- Diffusion-LM: base чуть лучше upgrade 1 (e40) по F1 (0.9829 против 0.9817); upgrade 1 лучше по recall и ROC-AUC.
- Из двух моделей upgrade 1 на обоих наборах лучше вариант e40 (seed 42), а не e60 (seed 23).
