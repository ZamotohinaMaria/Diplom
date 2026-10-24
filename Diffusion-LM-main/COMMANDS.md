# Команды: Diffusion-LM на MalBehavD-V1

Подготовка данных и параметры «по умолчанию» описаны в [MALBEHAVD_ADAPTATION.md](MALBEHAVD_ADAPTATION.md).
Ниже — конкретный прогон, использованный для результатов (обучение 2026-05-02, генерация 2026-05-05/06).

Обучение запускается из `Diffusion-LM-main\improved-diffusion`, оценка генерации — из корня репозитория.

## Обучение

Если TensorFlow пишет про oneDNN: это включены оптимизации на CPU, числа могут чуть отличаться из-за порядка вычислений, на обучение это обычно не влияет. Убрать сообщения:

```bat
set TF_ENABLE_ONEDNN_OPTS=0
```

```bat
set APP=--predict_xstart True ^
        --training_mode e2e ^
        --malbehav_train ../../MalbehavD-V1-main/prepared_for_diffusionlm/malbehav_train.txt ^
        --malbehav_valid ../../MalbehavD-V1-main/prepared_for_diffusionlm/malbehav_valid.txt ^
        --malbehav_test ../../MalbehavD-V1-main/prepared_for_diffusionlm/malbehav_test.txt ^
        --cache_mode no ^
        --save_best_model yes ^
        --best_model_filename best_model.pt ^
        --save_optimizer_state yes ^
        --log_interval 10

python scripts/run_train.py ^
  --experiment random --model_arch transformer --modality malbehav ^
  --noise_schedule sqrt --weight_decay 0.01 --image_size 13 ^
  --bsz 16 --hidden_size 64 --in_channel 16 --m 3 --k 32 ^
  --lr_anneal_steps 20000 --lr 5e-5 --diff_steps 1500 ^
  --save_interval 500 --eval_interval 100 --eval_num_batches 8 ^
  --padding_mode pad --seed 101 --dropout 0.2 ^
  --notes malbehav_full_balanced_v1 ^
  --app "%APP%"
```

## Генерация

```bat
python scripts/generate_malbehav_by_label.py ^
  --model_path runs\models\malbehav_full_balanced_v1_trf_ic16_bs16_s101_20260502-202533\best_model.pt ^
  --target_label both --num_samples 1500 --samples_per_round 64 --batch_size 32 ^
  --top_p 0.85 --max_rounds 80 ^
  --out_dir runs\generation_outputs\malbehav_best_20260505
```

## Конвертация сэмплов в CSV-формат MalbehavD-V1

```bat
python scripts/malbehav_samples_to_csv.py ^
  --input_txt runs\generation_outputs\malbehav_best_20260505\merge_malbehav_1500_20260506_223237.txt ^
  --output_csv runs\generation_outputs\malbehav_best_20260505\malbehav_generated_1500.csv ^
  --drop_special_tokens yes --with_sha256_column yes
```

## Оценка качества генерации

Из корня репозитория:

```bat
python .\my-GINE-model\generation_quality_checks.py ^
  --real-csv .\MalbehavD-V1-main\MalBehavD-V1-dataset.csv ^
  --synthetic-csv .\Diffusion-LM-main\improved-diffusion\runs\generation_outputs\malbehav_best_20260505\malbehav_generated_1500.csv ^
  --include-unnamed-api-cols ^
  --seeds 42,43,44,45,46
```

Отчёт сохраняется в `my-GINE-model\runs\generation_quality\gen_quality_<дата>.txt` (прогон 2026-05-06 23:06).
