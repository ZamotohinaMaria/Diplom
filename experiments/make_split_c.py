"""Пункт 2 (неделя 2–8.11.2026). Протокол C — разбиение по исполняемым файлам.

Цель — оценка на файлах, которых не было в train. Группа C — компонента связности: две строки
связаны, если у них одинаковый sha256_file или одинаковый seq_hash; связи транзитивные (файл X дал
трассы T1 и T2, трасса T2 есть и у файла Y -> X и Y в одной группе). Группа целиком попадает в одну часть.

Правила зафиксированы до запуска (04.11.2026) и по результатам не меняются:
  1. Как в A/B, до группировки исключаются строки последовательностей с конфликтующими метками
     (12 строк). После этого каждая группа должна быть одного класса; если нет — скрипт
     останавливается с ошибкой, метки не исправляются.
  2. sha256_file нормализуется (пробелы по краям, нижний регистр). Корректный id — 64 шестнадцатеричных
     символа. Строки с отсутствующим или некорректным id связываются только по seq_hash; их число — в отчёте.
  3. Схема как в A/B: 5 фолдов, фолд 0 -> test, фолд 1 -> val, 2–4 -> train. Группы раскладываются
     тем же жадным алгоритмом (assign_groups_balanced из make_splits.py) внутри каждого класса.
  4. Разбиение для пилота (пункт 3) — seed --base-seed (42); остальные seed — диагностика устойчивости.
  5. Критерии пригодности, для каждого seed:
       К1  крупнейшая группа класса не больше фолда этого класса (строк класса / 5) — иначе схема невозможна;
       К2  test и val — от 486 до 538 строк (512 ± 5 %);
       К3  доля malware в каждой части — от 45 до 55 %.
     Вывод: К1 не выполнен -> непригоден; seed пилота проходит К2 и К3 -> пригоден (если не все seed —
     с оговоркой); seed пилота не проходит -> непригоден для пилота, сообщить руководителю (seed не менять).
     Метрики моделей здесь не считаются и на вывод не влияют.

Нужен derived/hashes.csv (задача 1: python experiments/audit_duplicates.py).

Результаты:
  derived/splits/C_seed{N}.json     индексы строк (row_idx исходного CSV) для train / val / test
  derived/splits/groups_C.csv       группа C для каждой строки (row_idx, label, seq_hash, sha256_file, group_c, ...)
  derived/splits/summary_C.csv      размеры частей, доли malware, крупнейшая группа в test, критерии
  experiments/logs/make_split_c.txt текстовый отчёт (то же, что на экране)

Запуск из корня репозитория:
  python experiments/make_split_c.py
"""
import argparse
import json
import os
import re
import sys

import numpy as np
import pandas as pd

from log_run import DATASET_CSV, ROOT, file_sha256, tracked_run
from make_splits import (N_FOLDS, PARTS, TEST_FOLD, VAL_FOLD, assign_groups_balanced, drop_conflicts,
                         fold_to_part, load_hashes)

SHA256_RE = re.compile(r"[0-9a-f]{64}")
TEST_VAL_MIN, TEST_VAL_MAX = 486, 538   # К2: 512 ± 5 %
MALWARE_MIN, MALWARE_MAX = 0.45, 0.55   # К3
SIZE_BINS = [(1, 1), (2, 5), (6, 20), (21, 100), (101, 10**9)]


def parse_args():
    p = argparse.ArgumentParser(description="Разбиение C (групповое по файлу и трассе)")
    p.add_argument("--csv", default=DATASET_CSV)
    p.add_argument("--hashes", default=os.path.join(ROOT, "derived", "hashes.csv"))
    p.add_argument("--base-seed", type=int, default=42, help="seed пилота; остальные — base-seed+1, ...")
    p.add_argument("--num-runs", type=int, default=5)
    p.add_argument("--out-dir", default=os.path.join(ROOT, "derived", "splits"))
    p.add_argument("--log", default=os.path.join(ROOT, "experiments", "logs", "make_split_c.txt"))
    return p.parse_args()


def normalize_file_ids(h: pd.DataFrame) -> pd.Series:
    """Нормализованный sha256_file; для отсутствующих и некорректных id — NA (правило 2)."""
    ids = h["sha256_file"].map(lambda v: str(v).strip().lower() if pd.notna(v) else "")
    return ids.where(ids.map(lambda s: SHA256_RE.fullmatch(s) is not None))


def find_components(h: pd.DataFrame) -> np.ndarray:
    """Номер группы C для каждой строки h: компоненты связности по file_key и seq_hash (union-find).

    Номер группы — наименьший row_idx в ней, поэтому он не зависит от порядка обхода.
    """
    parent = np.arange(len(h))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for col in ("seq_hash", "file_key"):
        for idx in h.groupby(col).indices.values():   # позиции строк с одним ключом; NA пропускаются
            root = find(idx[0])
            for j in idx[1:]:
                parent[find(j)] = root
    roots = np.array([find(i) for i in range(len(h))])
    return pd.Series(h["row_idx"].to_numpy()).groupby(roots).transform("min").to_numpy()


def describe_groups(h: pd.DataFrame) -> pd.DataFrame:
    """Таблица групп C: размер, класс, сколько в ней файлов и разных трасс."""
    return (h.groupby("group_c")
             .agg(size=("row_idx", "size"), label=("label", "first"),
                  n_files=("file_key", "nunique"), n_seqs=("seq_hash", "nunique"))
             .sort_values("size", ascending=False, kind="stable"))


def check_and_describe_c(h: pd.DataFrame, part: np.ndarray, seed: int, groups: pd.DataFrame) -> dict:
    """Проверки разбиения C и строка для summary_C.csv."""
    hp = h.assign(part=part)

    # группа, трасса и файл — каждая ровно в одной части (NA в file_key groupby пропускает)
    shared = {}
    for col in ("group_c", "seq_hash", "file_key"):
        shared[col] = int((hp.groupby(col)["part"].nunique() > 1).sum())
        assert shared[col] == 0, f"C seed={seed}: {shared[col]} значений {col} в нескольких частях"

    row = {"protocol": "C", "seed": seed}
    for p in PARTS:
        sub = hp[hp.part == p]
        row[f"n_{p}"] = len(sub)
        row[f"malware_share_{p}"] = sub["label"].mean()
    test = hp[hp.part == "test"]
    row["n_test_unique_seqs"] = test["seq_hash"].nunique()
    row["seqs_in_several_parts"] = shared["seq_hash"]
    row["files_in_several_parts"] = shared["file_key"]

    # крупнейшая группа test и её доля от своего класса в test
    g_test = groups.loc[test["group_c"].unique()].sort_values("size", ascending=False, kind="stable")
    top = g_test.iloc[0]
    row["largest_test_group"] = int(top["size"])
    row["largest_test_group_label"] = int(top["label"])
    row["largest_test_group_share_of_class"] = top["size"] / int((test["label"] == top["label"]).sum())
    row["largest_group_part"] = hp.loc[hp.group_c == groups.index[0], "part"].iloc[0]

    row["K2_sizes"] = all(TEST_VAL_MIN <= row[f"n_{p}"] <= TEST_VAL_MAX for p in ("val", "test"))
    row["K3_balance"] = all(MALWARE_MIN <= row[f"malware_share_{p}"] <= MALWARE_MAX for p in PARTS)
    return row


def verdict(k1: bool, summary: pd.DataFrame, pilot_seed: int) -> str:
    """Вывод о пригодности C по правилу 5."""
    if not k1:
        return "НЕПРИГОДЕН: крупнейшая группа больше фолда (К1) — сообщить руководителю"
    ok = summary["K2_sizes"] & summary["K3_balance"]
    if not ok[summary.seed == pilot_seed].iloc[0]:
        return f"НЕПРИГОДЕН ДЛЯ ПИЛОТА: seed {pilot_seed} не проходит К2/К3 — сообщить руководителю"
    if ok.all():
        return "ПРИГОДЕН: все критерии выполнены для всех seed"
    bad = ", ".join(map(str, summary.loc[~ok, "seed"]))
    return f"ПРИГОДЕН С ОГОВОРКОЙ: seed пилота проходит, но К2/К3 не выполнены для seed {bad}"


def main():
    args = parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    os.makedirs(os.path.dirname(args.log), exist_ok=True)
    seeds = [args.base_seed + i for i in range(args.num_runs)]

    with tracked_run("make_split_c.py", params=vars(args), seed=",".join(map(str, seeds)),
                     log_path=args.log, dataset_path=args.csv) as run:
        h_all = load_hashes(args.hashes, args.csv)
        h, excluded, conflict = drop_conflicts(h_all)                      # правило 1
        h = h.assign(file_key=normalize_file_ids(h))                       # правило 2
        invalid = h[h["file_key"].isna()]
        h = h.assign(group_c=find_components(h))
        hashes_sha = file_sha256(args.hashes)

        n_labels = h.groupby("group_c")["label"].nunique()
        mixed = n_labels.index[n_labels > 1]
        if len(mixed):
            raise ValueError(f"{len(mixed)} групп C содержат оба класса (например, group_c={mixed[0]}); "
                             "по правилу 1 метки не исправляются — разбиение не строится")
        groups = describe_groups(h)
        h = h.assign(group_size=h["group_c"].map(groups["size"]))

        # К1: крупнейшая группа каждого класса помещается в один фолд
        k1_rows = []
        for cls in (0, 1):
            g = groups[groups.label == cls]
            cap = int((h.label == cls).sum()) / N_FOLDS
            k1_rows.append({"label": cls, "rows": int(g["size"].sum()), "groups": len(g),
                            "largest": int(g["size"].max()), "fold_capacity": cap,
                            "K1": bool(g["size"].max() <= cap)})
        k1_table = pd.DataFrame(k1_rows)
        k1 = bool(k1_table["K1"].all())

        rows, files = [], []
        for seed in seeds:
            fold_of = assign_groups_balanced(h, seed, group_col="group_c")
            assert np.array_equal(fold_of, assign_groups_balanced(h, seed, group_col="group_c")), \
                f"C seed={seed}: разбиение не воспроизводится"
            part = fold_to_part(fold_of)
            row = check_and_describe_c(h, part, seed, groups)
            rows.append(row)

            split = {
                "protocol": "C",
                "seed": seed,
                "pilot": seed == args.base_seed,
                "scheme": f"{N_FOLDS} folds: fold {TEST_FOLD} -> test, fold {VAL_FOLD} -> val, rest -> train",
                "group": "connected components by sha256_file or seq_hash",
                "group_method": "balanced",
                "hashes_csv_sha256": hashes_sha,
                "excluded_conflict_rows": sorted(excluded["row_idx"].tolist()),
                "invalid_file_id_rows": sorted(invalid["row_idx"].astype(int).tolist()),
                "criteria": {"K1": k1, "K2_sizes": bool(row["K2_sizes"]), "K3_balance": bool(row["K3_balance"])},
            }
            for p in PARTS:
                split[p] = sorted(h.loc[part == p, "row_idx"].astype(int).tolist())
            assert sum(len(split[p]) for p in PARTS) + len(excluded) == len(h_all), "строки потеряны"
            assert len(set().union(*(split[p] for p in PARTS))) == len(h), "строка в нескольких частях"
            path = os.path.join(args.out_dir, f"C_seed{seed}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(split, f, ensure_ascii=False)
            files.append(path)

        summary = pd.DataFrame(rows)
        summary_csv = os.path.join(args.out_dir, "summary_C.csv")
        summary.to_csv(summary_csv, index=False, encoding="utf-8")
        groups_csv = os.path.join(args.out_dir, "groups_C.csv")
        h[["row_idx", "label", "seq_hash", "sha256_file", "file_key", "group_c", "group_size"]] \
            .to_csv(groups_csv, index=False, encoding="utf-8")
        result = verdict(k1, summary, args.base_seed)

        # сводка по группам
        merged = groups[groups.n_seqs > 1]
        bins = []
        for lo, hi in SIZE_BINS:
            g = groups[(groups["size"] >= lo) & (groups["size"] <= hi)]
            bins.append({"size": f"{lo}" if lo == hi else (f"{lo}+" if hi >= 10**9 else f"{lo}-{hi}"),
                         "groups": len(g), "rows": int(g["size"].sum()),
                         "benign_groups": int((g.label == 0).sum()), "malware_groups": int((g.label == 1).sum())})
        top5 = groups.head(5).reset_index()

        shown = summary.copy()
        for c in [c for c in shown.columns if c.startswith(("malware_share", "largest_test_group_share"))]:
            shown[c] = shown[c].map(lambda v: f"{100 * v:.1f}%")
        report = "\n".join([
            f"Исходных строк: {len(h_all)}",
            f"Исключено строк с конфликтующими метками: {len(excluded)} "
            f"(последовательностей: {len(conflict)}; benign {int((excluded.label == 0).sum())}, "
            f"malware {int((excluded.label == 1).sum())})",
            f"Осталось строк: {len(h)}",
            f"Строк с отсутствующим или некорректным sha256_file: {len(invalid)}"
            + (" (связаны только по seq_hash)" if len(invalid) else ""),
            f"Схема: {N_FOLDS} фолдов, фолд {TEST_FOLD} -> test, фолд {VAL_FOLD} -> val, остальные -> train",
            f"Seed пилота: {args.base_seed}",
            "",
            "Группы C (компоненты связности по sha256_file и seq_hash):",
            f"  групп C: {len(groups)}; для сравнения групп B (по seq_hash): {h['seq_hash'].nunique()}",
            f"  групп C, объединивших несколько разных трасс: {len(merged)} "
            f"(строк в них: {int(merged['size'].sum())})",
            f"  групп C из нескольких файлов: {int((groups.n_files > 1).sum())}",
            "",
            "Распределение размеров групп:",
            pd.DataFrame(bins).to_string(index=False),
            "",
            "Пять крупнейших групп (n_files — разных файлов, n_seqs — разных трасс):",
            top5.to_string(index=False),
            "",
            "К1 — крупнейшая группа класса не больше фолда (fold_capacity = строк класса / 5):",
            k1_table.to_string(index=False),
            "",
            "Пояснение к столбцам:",
            "  n_train / n_val / n_test         — число строк в каждой части",
            "  malware_share_*                  — доля malware в части (К3: 45–55%)",
            "  n_test_unique_seqs               — разных трасс в test",
            "  seqs_in_several_parts            — трасс, встречающихся больше чем в одной части (должно быть 0)",
            "  files_in_several_parts           — файлов (sha256_file) больше чем в одной части (должно быть 0)",
            "  largest_test_group[_label]       — размер (и класс) крупнейшей группы в test",
            "  largest_test_group_share_of_class — её доля от строк этого класса в test",
            "  largest_group_part               — в какую часть попала крупнейшая группа всего датасета",
            f"  K2_sizes                         — test и val от {TEST_VAL_MIN} до {TEST_VAL_MAX} строк",
            "  K3_balance                       — доля malware во всех частях в пределах 45–55%",
            "",
            shown.to_string(index=False),
            "",
            f"ВЫВОД: {result}",
            "",
            f"Сохранено: {len(files)} файлов разбиений в {args.out_dir}",
            f"           {summary_csv}",
            f"           {groups_csv}",
        ])
        print(report)
        with open(args.log, "w", encoding="utf-8") as f:
            f.write(report + "\n")

        run.set(
            metrics={
                "excluded_conflict_rows": len(excluded),
                "invalid_file_id_rows": len(invalid),
                "n_groups_c": len(groups),
                "largest_group": {int(r.label): int(r.largest) for r in k1_table.itertuples()},
                "K1": k1,
                "K2_K3_ok_seeds": summary.loc[summary.K2_sizes & summary.K3_balance, "seed"].tolist(),
                "verdict": result,
            },
            notes=f"outputs: {os.path.relpath(args.out_dir, ROOT)}/C_seed*.json, summary_C.csv, groups_C.csv",
        )


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore  (метод есть у консоли, Pylance его не знает)
    main()
