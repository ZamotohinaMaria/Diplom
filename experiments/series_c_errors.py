"""Задача 12–13.11 (неделя 9–15.11.2026), разбор ошибок полной серии C (TF-IDF и GINE, seed 42–46).

Дополняет series_c_table.py: модели не обучает, читает только сохранённые предсказания test и разбиение.
Порог — по MCC на val (thr_mcc из файлов результатов), как в основной таблице.

Считает:
  1. Совпадение ошибок моделей на уникальных трассах test: ошибаются обе, только TF-IDF, только GINE
     (отдельно ложные тревоги и пропуски).
  2. Ошибки по размеру группы C (сколько строк в датасете у группы, куда входит трасса):
     1, 2–5, 6–20, больше 20 — по всем строкам test.
  3. Крупнейшая группа test в каждом seed: размер, класс, сколько её строк каждая модель
     классифицировала верно, средняя вероятность malware.

Нужны: derived/results_{pilot_C,series_C}_{tfidf,gine}.csv, derived/predictions/{tfidf,gine}_C_seed{N}.csv,
derived/splits/groups_C.csv.

Результаты:
  derived/series_C_errors.md            отчёт с тремя таблицами
  derived/series_C_errors_overlap.csv   совпадение ошибок по seed
  derived/series_C_errors_by_size.csv   ошибки по размеру группы и seed
  derived/series_C_largest_group.csv    крупнейшая группа test по seed

Запуск из корня репозитория:
  python experiments/series_c_errors.py
"""
import argparse
import os
import sys

import pandas as pd

from log_run import ROOT, tracked_run

SEEDS = [42, 43, 44, 45, 46]
PILOT_SEED = 42
MODELS = {"tfidf_logreg": "tfidf", "gine_e40": "gine"}
NAMES = {"tfidf": "TF-IDF", "gine": "GINE"}
SIZE_BINS = [(1, 1, "1"), (2, 5, "2–5"), (6, 20, "6–20"), (21, 10 ** 9, "больше 20")]


def parse_args():
    p = argparse.ArgumentParser(description="Разбор ошибок полной серии C")
    p.add_argument("--derived", default=os.path.join(ROOT, "derived"))
    p.add_argument("--out-dir", default=os.path.join(ROOT, "derived"))
    p.add_argument("--pilot-name", default="pilot_C")
    p.add_argument("--run-name", default="series_C")
    return p.parse_args()


def thresholds(derived: str, pilot_name: str, series_name: str) -> dict:
    """(префикс модели, seed) -> порог по MCC на val, полная точность из файлов результатов."""
    out = {}
    for model, prefix in MODELS.items():
        for name in (pilot_name, series_name):
            r = pd.read_csv(os.path.join(derived, f"results_{name}_{prefix}.csv"))
            for row in r[(r.protocol == "C") & (r.model == model)].itertuples():
                out[(prefix, row.seed)] = row.thr_mcc
    missing = [(p, s) for p in MODELS.values() for s in SEEDS if (p, s) not in out]
    if missing:
        raise ValueError(f"нет порогов для {missing}: сначала series_c_table.py и запуски моделей")
    return out


def test_predictions(derived: str, thr: dict, groups: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Строки test одного seed: метка, группа C, и для каждой модели вероятность и ошибка."""
    frames = []
    for prefix in MODELS.values():
        p = pd.read_csv(os.path.join(derived, "predictions", f"{prefix}_C_seed{seed}.csv"))
        p = p[p.part == "test"].set_index("row_idx")
        frames.append(p[["prob"]].rename(columns={"prob": f"prob_{prefix}"}))
        base = p[["label", "seq_hash"]]
    t = base.join(frames).join(groups[["group_c", "group_size"]])
    for prefix in MODELS.values():
        pred = (t[f"prob_{prefix}"] >= thr[(prefix, seed)]).astype(int)
        t[f"err_{prefix}"] = pred != t["label"]
    return t


def overlap(t: pd.DataFrame, seed: int) -> dict:
    u = t[~t["seq_hash"].duplicated()]   # уникальные трассы, как в eval_utils.evaluate_test
    row = {"seed": seed}
    for kind, label in (("fp", 0), ("fn", 1)):
        s = u[u.label == label]
        a, b = s["err_tfidf"], s["err_gine"]
        row.update({f"{kind}_both": int((a & b).sum()), f"{kind}_only_tfidf": int((a & ~b).sum()),
                    f"{kind}_only_gine": int((~a & b).sum())})
    return row


def by_size(t: pd.DataFrame, seed: int) -> list:
    rows = []
    for lo, hi, name in SIZE_BINS:
        s = t[(t.group_size >= lo) & (t.group_size <= hi)]
        rows.append({"seed": seed, "group_size": name, "rows": len(s),
                     "malware_rows": int((s.label == 1).sum()),
                     "err_tfidf": int(s.err_tfidf.sum()), "err_gine": int(s.err_gine.sum())})
    return rows


def largest_group(t: pd.DataFrame, seed: int) -> dict:
    g = t.groupby("group_c").size().idxmax()
    s = t[t.group_c == g]
    return {"seed": seed, "group_c": int(g), "rows": len(s), "label": "malware" if s.label.iloc[0] == 1 else "benign",
            "distinct_traces": int(s.seq_hash.nunique()),
            "correct_tfidf": int((~s.err_tfidf).sum()), "correct_gine": int((~s.err_gine).sum()),
            "mean_prob_tfidf": float(s.prob_tfidf.mean()), "mean_prob_gine": float(s.prob_gine.mean())}


def main():
    args = parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    md_path = os.path.join(args.out_dir, "series_C_errors.md")
    groups = pd.read_csv(os.path.join(args.derived, "splits", "groups_C.csv")).set_index("row_idx")

    with tracked_run("series_c_errors.py", params={"seeds": SEEDS, "pilot_name": args.pilot_name,
                                                   "run_name": args.run_name},
                     log_path=md_path, dataset_path=os.path.join(args.derived, "splits", "groups_C.csv")) as run:
        thr = thresholds(args.derived, args.pilot_name, args.run_name)
        ov, sz, lg = [], [], []
        for seed in SEEDS:
            t = test_predictions(args.derived, thr, groups, seed)
            ov.append(overlap(t, seed))
            sz.extend(by_size(t, seed))
            lg.append(largest_group(t, seed))
        ov, sz, lg = pd.DataFrame(ov), pd.DataFrame(sz), pd.DataFrame(lg)
        ov.to_csv(os.path.join(args.out_dir, "series_C_errors_overlap.csv"), index=False, encoding="utf-8")
        sz.to_csv(os.path.join(args.out_dir, "series_C_errors_by_size.csv"), index=False, encoding="utf-8")
        lg.to_csv(os.path.join(args.out_dir, "series_C_largest_group.csv"), index=False, encoding="utf-8")

        ov_shown = pd.concat([ov, pd.DataFrame([{"seed": "сумма", **ov.drop(columns="seed").sum().to_dict()}])])
        sz_total = sz.groupby("group_size", sort=False)[["rows", "malware_rows", "err_tfidf", "err_gine"]].sum()
        sz_total["share_err_tfidf"] = (100 * sz_total.err_tfidf / sz_total.rows).map("{:.1f}%".format)
        sz_total["share_err_gine"] = (100 * sz_total.err_gine / sz_total.rows).map("{:.1f}%".format)

        report = "\n".join([
            "# Разбор ошибок полной серии C (seed 42–46)",
            "",
            "Порог — по MCC на val. Источник — сохранённые предсказания test; модели не переобучались.",
            "",
            "## Совпадение ошибок моделей (уникальные трассы test)",
            "",
            "`fp_*` — ложные тревоги (benign отмечен как malware), `fn_*` — пропуски malware; "
            "`both` — ошибаются обе модели, `only_*` — только одна.",
            "",
            ov_shown.to_markdown(index=False),
            "",
            "## Ошибки по размеру группы C (все строки test, сумма по пяти seed)",
            "",
            "`group_size` — сколько строк в датасете у группы C, куда входит строка; `rows` — строк test "
            "в таких группах; `err_*` — ошибочных строк у модели.",
            "",
            sz_total.reset_index().to_markdown(index=False),
            "",
            "## Крупнейшая группа test",
            "",
            "`correct_*` — сколько строк группы модель классифицировала верно; `mean_prob_*` — средняя "
            "вероятность malware.",
            "",
            lg.to_markdown(index=False, floatfmt=".3f"),
            "",
            "По seed: `series_C_errors_overlap.csv`, `series_C_errors_by_size.csv`, `series_C_largest_group.csv`.",
        ])
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        print(report)
        run.set(metrics={k: int(v) for k, v in ov.drop(columns="seed").sum().items()},
                notes=f"суммы по seed {SEEDS}; report {os.path.relpath(md_path, ROOT)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore  (метод есть у консоли, Pylance его не знает)
    main()
