"""Задача 4, модель 1: TF-IDF по n-граммам API (n = 1–3) + логистическая регрессия.

Для каждого разбиения из задачи 3 (протоколы A и B, seed 42–46):
  1. TF-IDF обучается только на train (словарь n-грамм — тоже только по train).
  2. Параметр регуляризации C выбирается по MCC на val (порог для MCC тоже подбирается на val).
  3. На val с выбранным C фиксируются два порога: по максимуму MCC и порог для TPR = 0.95.
  4. Только после этого считаются вероятности на test и метрики (все строки и дедуплицированный test).

Каждое разбиение — отдельная строка в EXPERIMENTS.csv.

Скрипт состоит из двух блоков (--blocks):
  main    основная модель: n-граммы 1–3 (--ngram-max)
  ngram1  проверка: только 1-граммы, то есть «какие API встречались» без порядка вызовов.
          Если MCC почти не падает, сигнал в наборе вызовов, а порядок мало что добавляет.

Результаты блока main:
  derived/results_tfidf.csv                             строка на (protocol, seed)
  derived/predictions/tfidf_{A,B}_seed{N}.csv           вероятности на val и test
  experiments/logs/baseline_tfidf.txt                   текстовый отчёт
Результаты блока ngram1:
  derived/results_tfidf_ngram1.csv
  derived/predictions/tfidf_ngram1_{A,B}_seed{N}.csv
  experiments/logs/baseline_tfidf_ngram1.txt

Запуск из корня репозитория:
  python experiments/baseline_tfidf.py                                 # оба блока
  python experiments/baseline_tfidf.py --blocks ngram1                 # только проверка на 1-граммах
  python experiments/baseline_tfidf.py --protocols B --seeds 42 43     # часть разбиений
"""
import argparse
import os
import sys

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import matthews_corrcoef

from eval_utils import (choose_threshold_mcc, evaluate_test, load_data, load_split, merge_results,
                        oov_stats, rounded, save_predictions, split_path, threshold_at_tpr)
from log_run import DATASET_CSV, ROOT, tracked_run

# C = 1 / сила регуляризации. Сетка широкая: на пробе лучший C оказался 100, то есть на краю прежней сетки
C_GRID = [0.01, 0.1, 1.0, 10.0, 100.0, 1000.0, 10000.0]


def parse_args():
    p = argparse.ArgumentParser(description="TF-IDF (1–3-граммы API) + LogReg на разбиениях A/B")
    p.add_argument("--protocols", nargs="+", default=["A", "B"], choices=["A", "B"])
    p.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44, 45, 46])
    p.add_argument("--blocks", nargs="+", default=["main", "ngram1"], choices=["main", "ngram1"])
    p.add_argument("--ngram-max", type=int, default=3, help="верхняя граница n-грамм для блока main")
    p.add_argument("--pred-dir", default=os.path.join(ROOT, "derived", "predictions"))
    return p.parse_args()


# блок -> (модель, верхняя граница n-грамм, файл результатов, префикс предсказаний, отчёт)
def block_config(block: str, args) -> dict:
    if block == "main":
        return {"model": "tfidf_logreg", "ngram_max": args.ngram_max,
                "out": os.path.join(ROOT, "derived", "results_tfidf.csv"), "pred_prefix": "tfidf",
                "log": os.path.join(ROOT, "experiments", "logs", "baseline_tfidf.txt")}
    return {"model": "tfidf_logreg_ngram1", "ngram_max": 1,
            "out": os.path.join(ROOT, "derived", "results_tfidf_ngram1.csv"), "pred_prefix": "tfidf_ngram1",
            "log": os.path.join(ROOT, "experiments", "logs", "baseline_tfidf_ngram1.txt")}


def make_vectorizer(ngram_max: int) -> TfidfVectorizer:
    # токен = имя API целиком (в именах нет пробелов), регистр сохраняется
    return TfidfVectorizer(token_pattern=r"\S+", lowercase=False, ngram_range=(1, ngram_max), sublinear_tf=True)


def fit_one(train, val, ngram_max: int, seed: int):
    """Обучение на train и выбор C по val. Test сюда не передаётся."""
    vec = make_vectorizer(ngram_max)
    x_tr = vec.fit_transform(" ".join(s) for s in train["seq"])
    x_va = vec.transform(" ".join(s) for s in val["seq"])
    y_tr, y_va = train["label"].to_numpy(), val["label"].to_numpy()

    best = None
    for c in C_GRID:
        clf = LogisticRegression(C=c, max_iter=5000, random_state=seed)
        clf.fit(x_tr, y_tr)
        p_va = clf.predict_proba(x_va)[:, 1]
        val_mcc = matthews_corrcoef(y_va, (p_va >= choose_threshold_mcc(y_va, p_va)).astype(int))
        if best is None or val_mcc > best["val_mcc"]:
            best = {"C": c, "clf": clf, "p_va": p_va, "val_mcc": val_mcc}
    return vec, best


def run_one(data, protocol: str, seed: int, cfg: dict, args) -> dict:
    path = split_path(protocol, seed)
    train, val, test = load_split(data, path)
    vec, best = fit_one(train, val, cfg["ngram_max"], seed)

    # пороги фиксируются по val
    y_va = val["label"].to_numpy()
    thr = choose_threshold_mcc(y_va, best["p_va"])
    thr_tpr = threshold_at_tpr(y_va, best["p_va"])

    # test — один раз, когда всё выбрано
    p_te = best["clf"].predict_proba(vec.transform(" ".join(s) for s in test["seq"]))[:, 1]
    row = {"model": cfg["model"], "protocol": protocol, "seed": seed, "C": best["C"],
           "n_features": len(vec.vocabulary_), "thr_mcc": thr, "thr_tpr95": thr_tpr,
           "val_mcc": best["val_mcc"]}
    row.update(evaluate_test(test, p_te, thr, thr_tpr))
    row.update(oov_stats(train["seq"], test["seq"]))

    save_predictions(os.path.join(args.pred_dir, f"{cfg['pred_prefix']}_{protocol}_seed{seed}.csv"),
                     {"val": (val, best["p_va"]), "test": (test, p_te)})
    return row


def run_block(data, block: str, args) -> None:
    cfg = block_config(block, args)
    os.makedirs(os.path.dirname(cfg["log"]), exist_ok=True)
    print(f"\n##### блок {block}: n-граммы 1–{cfg['ngram_max']} #####")
    rows = []
    for protocol in args.protocols:
        for seed in args.seeds:
            params = {"block": block, "ngram_range": [1, cfg["ngram_max"]], "C_grid": C_GRID,
                      "select": "val MCC", "threshold": "val MCC", "sublinear_tf": True}
            with tracked_run("baseline_tfidf.py", params=params, seed=seed, log_path=cfg["log"],
                             split_file=split_path(protocol, seed), dataset_path=DATASET_CSV,
                             notes=f"protocol={protocol}; block={block}") as run:
                row = run_one(data, protocol, seed, cfg, args)
                rows.append(row)
                run.set(metrics=rounded({k: row[k] for k in ("C", "val_mcc", "mcc", "f1", "pr_auc", "roc_auc",
                                                             "fpr_at_tpr95", "dedup_mcc", "dedup_pr_auc")}))
            print(f"{protocol} seed={seed}: C={row['C']} test MCC={row['mcc']:.4f} PR-AUC={row['pr_auc']:.4f} "
                  f"FPR@TPR95={row['fpr_at_tpr95']:.4f} | dedup MCC={row['dedup_mcc']:.4f}")

    res = merge_results(cfg["out"], rows)
    cols = ["protocol", "seed", "C", "mcc", "f1", "pr_auc", "roc_auc", "fpr_at_tpr95", "tpr_at_tpr95",
            "dedup_mcc", "dedup_pr_auc", "n_test", "n_test_dedup", "oov_seq_share"]
    report = "\n".join([
        "TF-IDF (n-граммы API 1–%d) + LogReg. C и пороги выбраны на val; метрики — на test." % cfg["ngram_max"],
        "",
        "Пояснение к столбцам:",
        "  C              — сила регуляризации LogReg, выбранная по MCC на val",
        "  mcc, f1        — при пороге, выбранном по MCC на val",
        "  pr_auc, roc_auc — от порога не зависят",
        "  fpr_at_tpr95   — доля benign в test, ложно отмеченных как malware, при пороге, который на val",
        "                   ловит 95% malware; tpr_at_tpr95 — сколько malware этот порог реально поймал на test",
        "  dedup_*        — те же метрики на test, где каждая последовательность учтена один раз",
        "  n_test / n_test_dedup — строк в test всего / уникальных последовательностей",
        "  oov_seq_share  — доля трасс test, где есть API, не встречавшийся в train",
        "",
        res[cols].to_string(index=False, float_format=lambda v: f"{v:.4f}"),
        "",
        f"Сохранено: {cfg['out']}",
    ])
    print("\n" + report)
    with open(cfg["log"], "w", encoding="utf-8") as f:
        f.write(report + "\n")


def main():
    args = parse_args()
    data = load_data()
    for block in ("main", "ngram1"):   # порядок фиксирован: сначала основная модель, проверка — в конце
        if block in args.blocks:
            run_block(data, block, args)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore  (метод есть у консоли, Pylance его не знает)
    main()
