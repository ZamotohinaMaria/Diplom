# Команды: TextGAN (RelGAN) на MalBehavD-V1

Запускать из `TextGAN-PyTorch-master`. Подробности — в [README.md](README.md).

## 1. Подготовка датасета (один раз)

```bat
python .\tools\prepare_malbehavd_relgan.py --input_csv ..\MalbehavD-V1-main\MalBehavD-V1-dataset.csv --output_root dataset --dataset_prefix MalbehavD-V1 --test_ratio 0.2 --seed 42
```

## 2. Обучение двух моделей (goodware и malware)

```bat
cd .\run
python .\run_relgan.py 0 0   # goodware
python .\run_relgan.py 1 0   # malware
cd ..
```

## 3. Последний чекпоинт генератора (PowerShell)

```powershell
$good_ckpt = (Get-ChildItem -Recurse -File .\save | Where-Object { $_.Name -like 'gen_ADV_*.pt' -and $_.FullName -like '*MalbehavD-V1_goodware*' } | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
$mal_ckpt  = (Get-ChildItem -Recurse -File .\save | Where-Object { $_.Name -like 'gen_ADV_*.pt' -and $_.FullName -like '*MalbehavD-V1_malware*' }  | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
```

## 4. Генерация

Основной вариант: по 5000 строк на класс, финальные запуски от 2026-04-12.

```bat
python .\tools\generate_relgan_samples.py --dataset MalbehavD-V1_goodware ^
    --checkpoint save/20260412/MalbehavD-V1_goodware/relgan_vanilla_dt-Ra_lt-rsgan_mt-ra_et-Ra_sl153_temp40_lfd0.0_T0412_1811_20/models/gen_ADV_best.pt ^
    --output_txt .\generated\goodware_5000.txt --num_samples 5000 --batch_size 32
python .\tools\generate_relgan_samples.py --dataset MalbehavD-V1_malware ^
    --checkpoint save/20260412/MalbehavD-V1_malware/relgan_vanilla_dt-Ra_lt-rsgan_mt-ra_et-Ra_sl175_temp40_lfd0.0_T0412_2011_17/models/gen_ADV_best.pt ^
    --output_txt .\generated\malware_5000.txt --num_samples 5000 --batch_size 32
```

Вариант от 2026-04-01 (по 200 строк, `gen_MLE_best.pt`, на GPU):

```bat
python -m tools.generate_relgan_samples --dataset MalbehavD-V1_goodware --checkpoint ".\save\20260401\MalbehavD-V1_goodware\relgan_vanilla_dt-Ra_lt-rsgan_mt-ra_et-Ra_sl153_temp40_lfd0.0_T0401_1259_06\models\gen_MLE_best.pt" --output_txt ".\generated\goodware_200.txt" --num_samples 200 --batch_size 64 --cuda 1 --device 0

python -m tools.generate_relgan_samples --dataset MalbehavD-V1_malware --checkpoint ".\save\20260401\MalbehavD-V1_malware\relgan_vanilla_dt-Ra_lt-rsgan_mt-ra_et-Ra_sl175_temp40_lfd0.0_T0401_1458_03\models\gen_MLE_best.pt" --output_txt ".\generated\malware_200.txt" --num_samples 200 --batch_size 64 --cuda 1 --device 0
```

## 5. Возврат в CSV-формат MalbehavD

```bat
python .\tools\export_relgan_samples_to_csv.py ^
    --samples_txt .\generated\goodware_5000.txt ^
    --template_csv ..\MalbehavD-V1-main\MalBehavD-V1-dataset.csv ^
    --output_csv .\generated\goodware_5000.csv --label 0
python .\tools\export_relgan_samples_to_csv.py ^
    --samples_txt .\generated\malware_5000.txt ^
    --template_csv ..\MalbehavD-V1-main\MalBehavD-V1-dataset.csv ^
    --output_csv .\generated\malware_5000.csv --label 1
```

## 6. Объединение в один CSV

```bat
python .\tools\merge_generated_csv.py ^
    --goodware_csv .\generated\goodware_5000.csv ^
    --malware_csv .\generated\malware_5000.csv ^
    --output_csv ..\MalbehavD-V1-main\MalBehavD-V1-generated-5000x2.csv ^
    --shuffle-seed 142
```

Второй вариант объединения из старых заметок (`generated\MalBehavD-V1-generated-200x2.csv` + реальный датасет в аргументе `--malware_csv`; выглядит как эксперимент, перед повтором проверить):

```bat
python .\tools\merge_generated_csv.py ^
    --goodware_csv .\generated\MalBehavD-V1-generated-200x2.csv ^
    --malware_csv ..\MalbehavD-V1-main\MalBehavD-V1-dataset.csv ^
    --output_csv ..\MalbehavD-V1-main\MalBehavD-V1-merged_200.csv
```
