"""Задача 1. Аудит дублей последовательностей API в MalBehavD-V1.

Исходный CSV только читается. Результаты:
  derived/hashes.csv                  row_idx, sha256_file, label, seq_hash, seq_len
  derived/audit_duplicates_table.csv  сводная таблица (всего / benign / malware)
  derived/audit_top5_groups.csv       5 крупнейших групп одинаковых последовательностей
  experiments/logs/audit_duplicates.txt  текстовый отчёт (то же, что на экране)

Запуск из корня репозитория:
  python experiments/audit_duplicates.py
"""
import argparse
import hashlib
import os
import re
import sys

import pandas as pd

from log_run import DATASET_CSV, ROOT, tracked_run

LABEL_NAMES = {0: "benign", 1: "malware"}


def parse_args():
    p = argparse.ArgumentParser(description="Аудит дублей API-последовательностей")
    p.add_argument("--csv", default=DATASET_CSV)
    p.add_argument("--out-dir", default=os.path.join(ROOT, "derived"))
    p.add_argument("--log", default=os.path.join(ROOT, "experiments", "logs", "audit_duplicates.txt"))
    return p.parse_args()


def api_columns(df: pd.DataFrame) -> list:
    # колонки 0..154 и Unnamed: 155..176 — это позиции вызовов (так устроен широкий формат датасета)
    return [c for c in df.columns if re.fullmatch(r"\d+", str(c)) or str(c).startswith("Unnamed")]


def row_sequence(values) -> list:
    """Вызовы API строки без пустых хвостов. Пропусков в середине в датасете нет (проверено)."""
    return [str(v) for v in values if isinstance(v, str) and v.strip() != ""]


def build_hashes(df: pd.DataFrame) -> pd.DataFrame:
    cols = api_columns(df)
    seqs = [row_sequence(row) for row in df[cols].values]
    return pd.DataFrame({
        "row_idx": range(len(df)),
        "sha256_file": df["sha256"].values,
        "label": df["labels"].astype(int).values,
        "seq_hash": [hashlib.sha256(" ".join(s).encode("utf-8")).hexdigest() for s in seqs],
        "seq_len": [len(s) for s in seqs],
    })


def summary_table(h: pd.DataFrame) -> pd.DataFrame:
    group_size = h.groupby("seq_hash")["row_idx"].transform("size")
    in_dup = group_size >= 2
    labels_per_hash = h.groupby("seq_hash")["label"].nunique()
    conflict_hashes = set(labels_per_hash[labels_per_hash > 1].index)
    in_conflict = h["seq_hash"].isin(conflict_hashes)
    file_dup = h["sha256_file"].duplicated(keep=False)

    def by_class(mask=None, func=None):
        """[всего, benign, malware] для маски строк или функции от подтаблицы."""
        out = []
        for part in [h, h[h.label == 0], h[h.label == 1]]:
            if func is not None:
                out.append(int(func(part)))
            else:
                assert mask is not None, "нужно передать mask или func"
                out.append(int(mask.loc[part.index].sum()))
        return out

    rows = [
        ("Всего строк", by_class(func=len)),
        # по классам считаются отдельно, поэтому последовательность из обоих классов
        # входит и в benign, и в malware; две строки ниже разводят это, чтобы суммы сходились
        ("Уникальных последовательностей", by_class(func=lambda p: p.seq_hash.nunique())),
        ("  из них только в этом классе",
         [None] + [len(set(h.loc[h.label == c, "seq_hash"]) - conflict_hashes) for c in (0, 1)]),
        ("  из них общих для обоих классов", [len(conflict_hashes), None, None]),
        ("Строк в группах дублей (группа >= 2 строк)", by_class(mask=in_dup)),
        ("Лишних копий (строк - уникальных)", by_class(func=lambda p: len(p) - p.seq_hash.nunique())),
        ("Последовательностей с разными метками", [len(conflict_hashes), None, None]),
        ("Строк с конфликтующими метками", by_class(mask=in_conflict)),
        ("Строк с повторяющимся sha256 файла", by_class(mask=file_dup)),
    ]
    table = pd.DataFrame([[name] + vals for name, vals in rows], columns=["metric", "all", "benign", "malware"])
    return table.astype({"all": "Int64", "benign": "Int64", "malware": "Int64"})


def top_groups(h: pd.DataFrame, k: int = 5) -> pd.DataFrame:
    g = h.groupby("seq_hash").agg(
        size=("row_idx", "size"),
        benign=("label", lambda s: int((s == 0).sum())),
        malware=("label", lambda s: int((s == 1).sum())),
        seq_len=("seq_len", "first"),
        example_row=("row_idx", "min"),
    )
    g = g.sort_values(["size", "example_row"], ascending=[False, True]).head(k).reset_index()
    g.insert(0, "rank", range(1, len(g) + 1))
    g["seq_hash"] = g["seq_hash"].str[:12]
    return g


def main():
    args = parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    os.makedirs(os.path.dirname(args.log), exist_ok=True)
    hashes_csv = os.path.join(args.out_dir, "hashes.csv")
    table_csv = os.path.join(args.out_dir, "audit_duplicates_table.csv")
    top_csv = os.path.join(args.out_dir, "audit_top5_groups.csv")

    with tracked_run("audit_duplicates.py", params=vars(args), log_path=args.log,
                     dataset_path=args.csv) as run:
        df = pd.read_csv(args.csv)
        h = build_hashes(df)
        if (h.seq_len == 0).any():
            raise ValueError(f"Пустые последовательности: {int((h.seq_len == 0).sum())} строк")
        table = summary_table(h)
        top = top_groups(h)

        h.to_csv(hashes_csv, index=False)
        table.to_csv(table_csv, index=False, encoding="utf-8")
        top.to_csv(top_csv, index=False, encoding="utf-8")

        report = "\n".join([
            f"Датасет: {args.csv}",
            "",
            "[Сводная таблица]",
            table.to_string(index=False),
            "",
            "[5 крупнейших групп одинаковых последовательностей]",
            top.to_string(index=False),
            "",
            f"Сохранено: {hashes_csv}",
            f"           {table_csv}",
            f"           {top_csv}",
        ])
        print(report)
        with open(args.log, "w", encoding="utf-8") as f:
            f.write(report + "\n")

        t = table.set_index("metric")
        run.set(
            metrics={
                "rows": t.loc["Всего строк"].to_dict(),
                "unique": t.loc["Уникальных последовательностей"].to_dict(),
                "rows_in_dup_groups": t.loc["Строк в группах дублей (группа >= 2 строк)"].to_dict(),
                "conflict_sequences": int((h.groupby("seq_hash")["label"].nunique() > 1).sum()),
                "top5_sizes": top["size"].tolist(),
            },
            notes=f"outputs: {os.path.relpath(hashes_csv, ROOT)}, {os.path.relpath(table_csv, ROOT)}, "
                  f"{os.path.relpath(top_csv, ROOT)}",
        )


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore  (метод есть у консоли, Pylance его не знает)
    main()
