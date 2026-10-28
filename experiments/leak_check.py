"""Задача 2. Утечка в текущей схеме run_splits.py.

Для схемы run_splits.py (train-per-class=900, seed 42–46) считаем долю eval-строк,
у которых точная копия последовательности API (тот же seq_hash) есть в train.

Разбиение не воспроизводится вручную: импортируется сама функция split_raw_dataset
из my-GINE-model upgrade 1/run_splits.py, поэтому строки в train/eval те же, что у run_splits.py.

Нужен derived/hashes.csv (задача 1: python experiments/audit_duplicates.py).

Результаты:
  derived/leak_check_run_splits.csv     по строке на seed + mean/std
  experiments/logs/leak_check.txt       текстовый отчёт (то же, что на экране)

Запуск из корня репозитория:
  python experiments/leak_check.py
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

from log_run import DATASET_CSV, ROOT, tracked_run

GINE_DIR = os.path.join(ROOT, "my-GINE-model upgrade 1")
sys.path.insert(0, GINE_DIR)
# путь добавлен через sys.path строкой выше, поэтому Pylance этот модуль не видит; импорт тянет torch
from run_splits import split_raw_dataset  # type: ignore  # noqa: E402

ROW_COL = "_row_idx"  # номер строки исходного CSV; split_raw_dataset сбрасывает индекс, а столбец сохраняет


def parse_args():
    p = argparse.ArgumentParser(description="Доля eval-строк с точной копией в train (схема run_splits.py)")
    p.add_argument("--csv", default=DATASET_CSV)
    p.add_argument("--hashes", default=os.path.join(ROOT, "derived", "hashes.csv"))
    p.add_argument("--label-col", default="labels")
    p.add_argument("--train-per-class", type=int, default=900)
    p.add_argument("--base-seed", type=int, default=42)
    p.add_argument("--num-runs", type=int, default=5)
    p.add_argument("--out", default=os.path.join(ROOT, "derived", "leak_check_run_splits.csv"))
    p.add_argument("--log", default=os.path.join(ROOT, "experiments", "logs", "leak_check.txt"))
    return p.parse_args()


def load_hashes(path: str, df: pd.DataFrame) -> pd.DataFrame:
    """hashes.csv из задачи 1; проверяем, что он построен по этому же CSV и в том же порядке строк."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} не найден: сначала запусти experiments/audit_duplicates.py")
    h = pd.read_csv(path)
    # np.array_equal сам вернёт False и при разной длине
    if not np.array_equal(h["sha256_file"].to_numpy(), df["sha256"].to_numpy()) \
            or not np.array_equal(h["label"].to_numpy(), df["labels"].astype(int).to_numpy()):
        raise ValueError(f"{path} не соответствует {DATASET_CSV}: перезапусти audit_duplicates.py")
    return h.set_index("row_idx")


def leak_for_seed(df: pd.DataFrame, h: pd.DataFrame, label_col: str, train_per_class: int, seed: int) -> dict:
    train_df, eval_df = split_raw_dataset(df=df, label_col=label_col, train_per_class=train_per_class, seed=seed)

    # проверка: лишний столбец _row_idx не меняет разбиение (sample выбирает по индексу, а не по столбцам)
    ref_train, _ = split_raw_dataset(df=df.drop(columns=[ROW_COL]), label_col=label_col,
                                     train_per_class=train_per_class, seed=seed)
    if not (ref_train["sha256"].values == train_df["sha256"].values).all():
        raise AssertionError(f"seed={seed}: разбиение не совпадает с run_splits.py")

    tr = h.loc[train_df[ROW_COL].values]
    ev = h.loc[eval_df[ROW_COL].values]
    assert len(set(tr.index) & set(ev.index)) == 0, "строка попала и в train, и в eval"

    train_hashes = set(tr["seq_hash"])
    train_pairs = set(zip(tr["seq_hash"], tr["label"]))
    has_copy = ev["seq_hash"].isin(train_hashes)                              # копия есть в train
    same_label = pd.Series([p in train_pairs for p in zip(ev["seq_hash"], ev["label"])], index=ev.index)

    row = {"seed": seed, "train_rows": len(tr), "eval_rows": len(ev),
           "eval_with_copy": int(has_copy.sum()),
           "share_all": has_copy.mean(),
           "share_benign": has_copy[ev.label == 0].mean(),
           "share_malware": has_copy[ev.label == 1].mean(),
           "share_copy_same_label": same_label.mean(),   # копия в train с той же меткой: ответ «подсмотрен»
           "eval_unique_seqs": ev["seq_hash"].nunique(),
           "eval_unique_seqs_with_copy": ev.loc[has_copy, "seq_hash"].nunique()}
    return row


def main():
    args = parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    os.makedirs(os.path.dirname(args.log), exist_ok=True)
    seeds = [args.base_seed + i for i in range(args.num_runs)]

    with tracked_run("leak_check.py", params=vars(args), seed=",".join(map(str, seeds)),
                     log_path=args.log, dataset_path=args.csv) as run:
        df = pd.read_csv(args.csv)
        df[ROW_COL] = range(len(df))
        h = load_hashes(args.hashes, df)

        res = pd.DataFrame([leak_for_seed(df, h, args.label_col, args.train_per_class, s) for s in seeds])
        share_cols = [c for c in res.columns if c.startswith("share")]
        summary = pd.DataFrame([{"seed": "mean", **res[share_cols].mean().to_dict()},
                                {"seed": "std", **res[share_cols].std(ddof=1).to_dict()}])
        out = pd.concat([res, summary], ignore_index=True)
        out.to_csv(args.out, index=False, encoding="utf-8")

        shown = out.copy()
        for c in out.columns.difference(["seed"] + share_cols):
            shown[c] = shown[c].astype("Int64")  # без «.0» в строках mean/std
        for c in share_cols:
            shown[c] = shown[c].map(lambda v: f"{100 * v:.1f}%")
        shown = shown.astype(object).where(shown.notna(), "")  # пустые ячейки в строках mean/std
        report = "\n".join([
            f"Схема run_splits.py: train-per-class={args.train_per_class}, seeds={seeds}",
            "",
            "Пояснение к столбцам:",
            "  seed                        — seed разбиения; последние две строки: mean и std (ddof=1) по seed",
            "  train_rows / eval_rows      — число строк в train и в eval",
            "  eval_with_copy              — сколько eval-строк имеют точную копию последовательности в train",
            "  share_all                   — eval_with_copy / eval_rows: доля eval-строк с копией в train",
            "                                (это и есть искомые 5 чисел задачи 2)",
            "  share_benign, share_malware — та же доля отдельно среди benign- и malware-строк eval",
            "  share_copy_same_label       — доля eval-строк, у которых копия в train есть и с той же меткой",
            "                                (модель может просто «вспомнить» ответ)",
            "  eval_unique_seqs            — число разных последовательностей в eval",
            "  eval_unique_seqs_with_copy  — сколько из них встречается и в train",
            "  Во всех share_* стоят проценты; mean/std посчитаны по пяти seed.",
            "  Копией считается точное совпадение seq_hash; близкие последовательности не учитываются.",
            "",
            shown.to_string(index=False, na_rep=""),
            "",
            f"Сохранено: {args.out}",
        ])
        print(report)
        with open(args.log, "w", encoding="utf-8") as f:
            f.write(report + "\n")

        run.set(metrics={"share_all_by_seed": {int(s): round(float(v), 4) for s, v in zip(res["seed"], res["share_all"])},
                         "share_all_mean": round(res.share_all.mean(), 4),
                         "share_all_std": round(res.share_all.std(ddof=1), 4),
                         "share_malware_mean": round(res.share_malware.mean(), 4),
                         "share_benign_mean": round(res.share_benign.mean(), 4)},
                notes=f"output: {os.path.relpath(args.out, ROOT)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore  (метод есть у консоли, Pylance его не знает)
    main()
