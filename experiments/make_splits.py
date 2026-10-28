"""Задача 3. Разбиения train / val / test для двух протоколов.

  Протокол A — случайное стратифицированное разбиение (StratifiedKFold), как было раньше.
  Протокол B — групповое (группа = seq_hash): одинаковые последовательности целиком попадают в одну часть.
               По умолчанию группы раскладываются по фолдам сбалансированно (--group-method balanced),
               см. assign_groups_balanced. Вариант sklearn StratifiedGroupKFold доступен через
               --group-method sgkf, но на этом датасете он даёт части разного размера
               (test от ~410 до ~720 строк) и долю malware от ~35% до ~68%: из-за очень больших
               групп (до 164 строк) он выравнивает доли классов, но не размеры фолдов.

Схема для обоих протоколов одинакова: 5 фолдов, фолд 0 -> test, фолд 1 -> val, фолды 2–4 -> train
(~60/20/20). Фолды перемешиваются с random_state=seed, поэтому для каждого seed роли достаются разным строкам.
Так A и B отличаются только группировкой.

Перед разбиением исключаются последовательности с конфликтующими метками (одна и та же
последовательность встречается и как benign, и как malware).
Словарь API здесь не строится: он строится при обучении, только по train каждого разбиения.

Нужен derived/hashes.csv (задача 1: python experiments/audit_duplicates.py).

Результаты:
  derived/splits/{A,B}_seed{N}.json   индексы строк (row_idx исходного CSV) для train / val / test
  derived/splits/summary.csv          размеры частей, доли malware, утечка, разнесённые повторы файлов
  experiments/logs/make_splits.txt    текстовый отчёт (то же, что на экране)

Запуск из корня репозитория:
  python experiments/make_splits.py
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold

from log_run import DATASET_CSV, ROOT, file_sha256, tracked_run

N_FOLDS = 5
TEST_FOLD, VAL_FOLD = 0, 1  # остальные фолды — train
PARTS = ("train", "val", "test")


def parse_args():
    p = argparse.ArgumentParser(description="Разбиения A (случайное) и B (групповое по seq_hash)")
    p.add_argument("--csv", default=DATASET_CSV)
    p.add_argument("--hashes", default=os.path.join(ROOT, "derived", "hashes.csv"))
    p.add_argument("--base-seed", type=int, default=42)
    p.add_argument("--num-runs", type=int, default=5)
    p.add_argument("--group-method", choices=["balanced", "sgkf"], default="balanced",
                   help="как раскладывать группы по фолдам в протоколе B")
    p.add_argument("--out-dir", default=os.path.join(ROOT, "derived", "splits"))
    p.add_argument("--log", default=os.path.join(ROOT, "experiments", "logs", "make_splits.txt"))
    return p.parse_args()


def load_hashes(hashes_path: str, csv_path: str) -> pd.DataFrame:
    """hashes.csv из задачи 1; проверяем, что он построен по этому же CSV и в том же порядке строк."""
    if not os.path.exists(hashes_path):
        raise FileNotFoundError(f"{hashes_path} не найден: сначала запусти experiments/audit_duplicates.py")
    h = pd.read_csv(hashes_path)
    df = pd.read_csv(csv_path, usecols=["sha256", "labels"])
    if len(h) != len(df) or not (h["sha256_file"].values == df["sha256"].values).all() \
            or not (h["label"].values == df["labels"].astype(int).values).all():
        raise ValueError(f"{hashes_path} не соответствует {csv_path}: перезапусти audit_duplicates.py")
    return h


def drop_conflicts(h: pd.DataFrame):
    """Убирает все строки последовательностей, которые встречаются с разными метками."""
    n_labels = h.groupby("seq_hash")["label"].nunique()
    conflict = set(n_labels[n_labels > 1].index)
    mask = h["seq_hash"].isin(conflict)
    return h[~mask].reset_index(drop=True), h[mask], conflict


def assign_groups_balanced(h: pd.DataFrame, seed: int) -> np.ndarray:
    """Групповое разбиение с равными размерами фолдов и долями классов.

    После исключения конфликтов каждая группа (seq_hash) целиком одного класса, поэтому классы
    раскладываются независимо. Внутри класса группы идут от больших к меньшим (равные по размеру —
    в случайном порядке по seed), и каждая кладётся в фолд, где строк этого класса пока меньше всего
    (жадный алгоритм LPT). Затем номера фолдов случайно переставляются (по seed), чтобы test/val
    каждый раз доставались разным группам.
    Следствие: 5 крупнейших групп malware всегда оказываются в 5 разных фолдах.
    """
    rng = np.random.default_rng(seed)
    groups = h.groupby("seq_hash").agg(size=("row_idx", "size"), label=("label", "first")).reset_index()
    fold_of_group = {}
    for cls in (0, 1):
        g = groups[groups.label == cls].sample(frac=1, random_state=seed)        # случайный порядок
        g = g.sort_values("size", ascending=False, kind="stable")                # большие первыми
        load = np.zeros(N_FOLDS)
        perm = rng.permutation(N_FOLDS)
        for seq_hash, size in zip(g["seq_hash"], g["size"]):
            k = int(np.argmin(load))
            load[k] += size
            fold_of_group[seq_hash] = int(perm[k])
    return h["seq_hash"].map(fold_of_group).values


def assign_folds(h: pd.DataFrame, protocol: str, seed: int, group_method: str = "balanced") -> np.ndarray:
    """Номер фолда (0..4) для каждой строки h."""
    y = h["label"].values
    if protocol == "B" and group_method == "balanced":
        return assign_groups_balanced(h, seed)
    if protocol == "A":
        splitter = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=seed)
        folds = splitter.split(np.zeros(len(h)), y)
    else:
        splitter = StratifiedGroupKFold(n_splits=N_FOLDS, shuffle=True, random_state=seed)
        folds = splitter.split(np.zeros(len(h)), y, groups=h["seq_hash"].values)
    fold_of = np.full(len(h), -1)
    for k, (_, test_idx) in enumerate(folds):
        fold_of[test_idx] = k
    assert (fold_of >= 0).all(), "строка не попала ни в один фолд"
    return fold_of


def fold_to_part(fold_of: np.ndarray) -> np.ndarray:
    return np.where(fold_of == TEST_FOLD, "test", np.where(fold_of == VAL_FOLD, "val", "train"))


def check_and_describe(h: pd.DataFrame, part: np.ndarray, protocol: str, seed: int) -> dict:
    """Проверки разбиения и строка для summary.csv."""
    hp = h.assign(part=part)
    train_hashes = set(hp.loc[hp.part == "train", "seq_hash"])

    # в B ни одна последовательность не должна встречаться в двух частях
    parts_per_hash = hp.groupby("seq_hash")["part"].nunique()
    shared = int((parts_per_hash > 1).sum())
    if protocol == "B":
        assert shared == 0, f"B seed={seed}: {shared} последовательностей в нескольких частях"

    # повторные запуски одного файла (sha256_file) с разными трассами: попали ли в разные части
    rep = hp[hp["sha256_file"].duplicated(keep=False)]
    files_split = int((rep.groupby("sha256_file")["part"].nunique() > 1).sum())

    row = {"protocol": protocol, "seed": seed}
    for p in PARTS:
        sub = hp[hp.part == p]
        row[f"n_{p}"] = len(sub)
        row[f"malware_share_{p}"] = sub["label"].mean()
    for p in ("val", "test"):
        row[f"leak_{p}"] = hp.loc[hp.part == p, "seq_hash"].isin(train_hashes).mean()
    row["seqs_in_several_parts"] = shared
    row["repeated_files_split"] = files_split
    row["repeated_files_total"] = int(rep["sha256_file"].nunique())
    return row


def main():
    args = parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    os.makedirs(os.path.dirname(args.log), exist_ok=True)
    seeds = [args.base_seed + i for i in range(args.num_runs)]

    with tracked_run("make_splits.py", params=vars(args), seed=",".join(map(str, seeds)),
                     log_path=args.log, dataset_path=args.csv) as run:
        h_all = load_hashes(args.hashes, args.csv)
        h, excluded, conflict = drop_conflicts(h_all)
        hashes_sha = file_sha256(args.hashes)

        rows, files = [], []
        for protocol in ("A", "B"):
            for seed in seeds:
                part = fold_to_part(assign_folds(h, protocol, seed, args.group_method))
                rows.append(check_and_describe(h, part, protocol, seed))

                split = {
                    "protocol": protocol,
                    "seed": seed,
                    "scheme": f"{N_FOLDS} folds: fold {TEST_FOLD} -> test, fold {VAL_FOLD} -> val, rest -> train",
                    "group": "seq_hash" if protocol == "B" else None,
                    "group_method": args.group_method if protocol == "B" else None,
                    "hashes_csv_sha256": hashes_sha,
                    "excluded_conflict_rows": sorted(excluded["row_idx"].tolist()),
                }
                for p in PARTS:
                    split[p] = sorted(h.loc[part == p, "row_idx"].astype(int).tolist())
                path = os.path.join(args.out_dir, f"{protocol}_seed{seed}.json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(split, f, ensure_ascii=False)
                files.append(path)

        summary = pd.DataFrame(rows)
        summary_csv = os.path.join(args.out_dir, "summary.csv")
        summary.to_csv(summary_csv, index=False, encoding="utf-8")

        shown = summary.copy()
        for c in [c for c in shown.columns if c.startswith(("malware_share", "leak"))]:
            shown[c] = shown[c].map(lambda v: f"{100 * v:.1f}%")
        report = "\n".join([
            f"Исходных строк: {len(h_all)}",
            f"Исключено строк с конфликтующими метками: {len(excluded)} "
            f"(последовательностей: {len(conflict)}; benign {int((excluded.label == 0).sum())}, "
            f"malware {int((excluded.label == 1).sum())})",
            f"Осталось строк: {len(h)}",
            f"Протокол B: группы по seq_hash, раскладка по фолдам: {args.group_method}",
            f"Схема: {N_FOLDS} фолдов, фолд {TEST_FOLD} -> test, фолд {VAL_FOLD} -> val, остальные -> train",
            "",
            "Пояснение к столбцам:",
            "  protocol                   — A: случайное разбиение; B: групповое по seq_hash",
            "                               (в A и B одинаковые размеры частей — это и нужно для сравнения)",
            "  seed                       — random_state перемешивания фолдов",
            "  n_train / n_val / n_test   — число строк в каждой части",
            "  malware_share_*            — доля malware в части (в идеале около 50%)",
            "  leak_val / leak_test       — доля строк val / test, у которых точная копия последовательности есть в train",
            "                               (для B должно быть 0.0%)",
            "  seqs_in_several_parts      — сколько разных последовательностей встречается больше чем в одной части",
            "                               (для B должно быть 0)",
            "  repeated_files_split       — сколько файлов (sha256_file), запущенных несколько раз, оказались",
            "                               в разных частях; repeated_files_total — всего таких файлов",
            "",
            shown.to_string(index=False),
            "",
            f"Сохранено: {len(files)} файлов разбиений в {args.out_dir}",
            f"           {summary_csv}",
        ])
        print(report)
        with open(args.log, "w", encoding="utf-8") as f:
            f.write(report + "\n")

        by_proto = summary.groupby("protocol")
        run.set(
            metrics={
                "excluded_conflict_rows": len(excluded),
                "rows_after_exclusion": len(h),
                "leak_test_mean": {k: round(v, 4) for k, v in by_proto["leak_test"].mean().items()},
                "leak_val_mean": {k: round(v, 4) for k, v in by_proto["leak_val"].mean().items()},
                "repeated_files_split_mean": by_proto["repeated_files_split"].mean().round(2).to_dict(),
            },
            notes=f"outputs: {os.path.relpath(args.out_dir, ROOT)}/{{A,B}}_seed*.json, summary.csv",
        )


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
