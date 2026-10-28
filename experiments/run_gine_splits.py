"""Задача 4, модель 2: GINE (лучшая конфигурация из НИРС, архитектура без изменений) на разбиениях A/B.

Конфигурация по умолчанию — модель «e40» из my-GINE-model upgrade 1/COMMANDS.md
(по 0 - docs/experiments-log.md она лучше варианта e60): hidden 128, 3 слоя, dropout 0.3, batch 64,
40 эпох, lr 1e-3, weight decay 1e-4, ориентированный граф без skip-рёбер, max_seq_len 400,
temperature scaling.

Для каждого разбиения из задачи 3 (протоколы A и B, seed 42–46):
  1. Словарь API строится только по train (build_vocab), val/test кодируются им же: незнакомые API -> <UNK>.
  2. Обучение на train; лучшая эпоха выбирается по метрике на val (train_model из upgrade 1).
  3. На val: температура калибровки, порог по максимуму MCC и порог для TPR = 0.95.
  4. Только после этого — вероятности на test и метрики (все строки и дедуплицированный test).

Код модели и обучения не копируется, а импортируется из my-GINE-model upgrade 1.
На GPU результаты при одном seed могут слегка отличаться между запусками (недетерминированные
операции агрегации в torch_geometric); на CPU они повторяются точно.

Результаты:
  derived/results_gine.csv                      строка на (protocol, seed)
  derived/predictions/gine_{A,B}_seed{N}.csv    вероятности на val и test
  derived/gine_models/gine_{A,B}_seed{N}.pt     веса лучшей эпохи (в git не попадают)
  experiments/logs/run_gine_splits.txt          текстовый отчёт

Запуск из корня репозитория:
  python experiments/run_gine_splits.py
  python experiments/run_gine_splits.py --protocols A --seeds 42      # один прогон, чтобы оценить время
"""
import argparse
import os
import sys
import time

import numpy as np
import torch
from torch_geometric.loader import DataLoader

from eval_utils import (choose_threshold_mcc, evaluate_test, load_data, load_split, merge_results,
                        oov_stats, rounded, save_predictions, split_path, threshold_at_tpr)
from log_run import DATASET_CSV, ROOT, tracked_run

GINE_DIR = os.path.join(ROOT, "my-GINE-model upgrade 1")
sys.path.insert(0, GINE_DIR)
# путь добавлен через sys.path строкой выше, поэтому Pylance эти модули не видит
from graph_data import build_vocab, sequences_to_graphs  # type: ignore  # noqa: E402
from model import GINEMalwareClassifier  # type: ignore  # noqa: E402
from trainer import (collect_logits_labels, fit_temperature_scaler,  # type: ignore  # noqa: E402
                     probs_from_logits, train_model)
from utils import set_seed  # type: ignore  # noqa: E402


def parse_args():
    p = argparse.ArgumentParser(description="GINE (конфигурация e40) на разбиениях A/B")
    p.add_argument("--protocols", nargs="+", default=["A", "B"], choices=["A", "B"])
    p.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44, 45, 46])
    # конфигурация e40 — не менять без причины, иначе это уже не «лучшая конфигурация из НИРС»
    p.add_argument("--hidden-dim", type=int, default=128)
    p.add_argument("--num-layers", type=int, default=3)
    p.add_argument("--dropout", type=float, default=0.3)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--epochs", type=int, default=40)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--max-seq-len", type=int, default=400)
    p.add_argument("--min-token-freq", type=int, default=1)
    p.add_argument("--undirected", action="store_true")
    p.add_argument("--add-skip-edges", action="store_true")
    p.add_argument("--calibration", choices=["none", "temperature"], default="temperature")
    p.add_argument("--select-metric", choices=["mcc", "f1"], default="mcc",
                   help="метрика на val для выбора эпохи (порог для отчёта всегда по MCC на val)")
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    p.add_argument("--out", default=os.path.join(ROOT, "derived", "results_gine.csv"))
    p.add_argument("--pred-dir", default=os.path.join(ROOT, "derived", "predictions"))
    p.add_argument("--model-dir", default=os.path.join(ROOT, "derived", "gine_models"))
    p.add_argument("--log", default=os.path.join(ROOT, "experiments", "logs", "run_gine_splits.txt"))
    return p.parse_args()


def to_graphs(frame, vocab, args):
    return sequences_to_graphs(list(frame["seq"]), frame["label"].astype(int).tolist(), vocab,
                               max_seq_len=args.max_seq_len, undirected=args.undirected,
                               add_skip_edges=args.add_skip_edges)


def loader(graphs, args, shuffle=False):
    return DataLoader(graphs, batch_size=args.batch_size, shuffle=shuffle)


def run_one(data, protocol: str, seed: int, args) -> dict:
    set_seed(seed)
    device = torch.device(args.device)
    train, val, test = load_split(data, split_path(protocol, seed))

    # словарь — только по train
    vocab = build_vocab(list(train["seq"]), min_token_freq=args.min_token_freq)
    g_tr, g_va, g_te = to_graphs(train, vocab, args), to_graphs(val, vocab, args), to_graphs(test, vocab, args)

    model = GINEMalwareClassifier(num_node_features=g_tr[0].num_node_features, edge_dim=g_tr[0].edge_attr.size(1),
                                  hidden_dim=args.hidden_dim, num_layers=args.num_layers, num_classes=2,
                                  dropout=args.dropout).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    os.makedirs(args.model_dir, exist_ok=True)
    model_path = os.path.join(args.model_dir, f"gine_{protocol}_seed{seed}.pt")

    # обучение: лучшая эпоха — по val (test в train_model не передаётся)
    t0 = time.time()
    best_epoch, best_val = train_model(model=model, train_loader=loader(g_tr, args, shuffle=True),
                                       val_loader=loader(g_va, args), optimizer=optimizer, device=device,
                                       epochs=args.epochs, save_path=model_path, monitor_metric=args.select_metric)
    train_sec = time.time() - t0
    model.load_state_dict(torch.load(model_path, map_location=device))

    # калибровка и пороги — по val
    y_va, logits_va = collect_logits_labels(model, loader(g_va, args), device)
    temperature = fit_temperature_scaler(logits_va, y_va, device) if args.calibration == "temperature" else 1.0
    p_va = probs_from_logits(logits_va, temperature)
    thr = choose_threshold_mcc(y_va, p_va)
    thr_tpr = threshold_at_tpr(y_va, p_va)

    # test — один раз, когда всё выбрано
    y_te, logits_te = collect_logits_labels(model, loader(g_te, args), device)
    assert np.array_equal(y_te, test["label"].to_numpy()), "порядок test нарушен"
    p_te = probs_from_logits(logits_te, temperature)

    row = {"model": "gine_e40", "protocol": protocol, "seed": seed, "best_epoch": best_epoch,
           f"val_{args.select_metric}_at_0.5": best_val, "temperature": temperature, "vocab_size": len(vocab),
           "thr_mcc": thr, "thr_tpr95": thr_tpr, "train_sec": round(train_sec, 1)}
    row.update(evaluate_test(test, p_te, thr, thr_tpr))
    row.update(oov_stats(train["seq"], test["seq"]))

    save_predictions(os.path.join(args.pred_dir, f"gine_{protocol}_seed{seed}.csv"),
                     {"val": (val, p_va), "test": (test, p_te)})
    return row


def main():
    args = parse_args()
    os.makedirs(os.path.dirname(args.log), exist_ok=True)
    data = load_data()
    params = {k: v for k, v in vars(args).items() if k not in ("protocols", "seeds", "out", "pred_dir",
                                                                "model_dir", "log")}
    rows = []
    for protocol in args.protocols:
        for seed in args.seeds:
            print(f"\n=== GINE | protocol {protocol} | seed {seed} ===")
            with tracked_run("run_gine_splits.py", params=params, seed=seed, log_path=args.log,
                             split_file=split_path(protocol, seed), dataset_path=DATASET_CSV,
                             notes=f"protocol={protocol}") as run:
                row = run_one(data, protocol, seed, args)
                rows.append(row)
                run.set(metrics=rounded({k: row[k] for k in ("best_epoch", "mcc", "f1", "pr_auc", "roc_auc",
                                                             "fpr_at_tpr95", "dedup_mcc", "dedup_pr_auc",
                                                             "train_sec")}),
                        notes=f"protocol={protocol}; model={os.path.relpath(args.model_dir, ROOT)}"
                              f"/gine_{protocol}_seed{seed}.pt")
            print(f"{protocol} seed={seed}: best_epoch={row['best_epoch']} test MCC={row['mcc']:.4f} "
                  f"PR-AUC={row['pr_auc']:.4f} FPR@TPR95={row['fpr_at_tpr95']:.4f} | "
                  f"dedup MCC={row['dedup_mcc']:.4f} | {row['train_sec']:.0f} c")

    res = merge_results(args.out, rows)
    cols = ["protocol", "seed", "best_epoch", "mcc", "f1", "pr_auc", "roc_auc", "fpr_at_tpr95", "tpr_at_tpr95",
            "dedup_mcc", "dedup_pr_auc", "n_test", "n_test_dedup", "vocab_size", "oov_seq_share", "train_sec"]
    report = "\n".join([
        f"GINE (конфигурация e40), device={args.device}. Эпоха, температура и пороги выбраны на val; "
        "метрики — на test.",
        "",
        "Пояснение к столбцам:",
        f"  best_epoch     — эпоха с лучшим {args.select_metric.upper()} на val (при пороге 0.5)",
        "  mcc, f1        — при пороге, выбранном по MCC на val",
        "  pr_auc, roc_auc — от порога не зависят",
        "  fpr_at_tpr95   — доля benign в test, ложно отмеченных как malware, при пороге, который на val",
        "                   ловит 95% malware; tpr_at_tpr95 — сколько malware этот порог реально поймал на test",
        "  dedup_*        — те же метрики на test, где каждая последовательность учтена один раз",
        "  n_test / n_test_dedup — строк в test всего / уникальных последовательностей",
        "  vocab_size     — размер словаря API (только по train, включая <UNK>)",
        "  oov_seq_share  — доля трасс test, где есть API, не встречавшийся в train",
        "  train_sec      — время обучения, секунд",
        "",
        res[cols].to_string(index=False, float_format=lambda v: f"{v:.4f}"),
        "",
        f"Сохранено: {args.out}",
    ])
    print("\n" + report)
    with open(args.log, "w", encoding="utf-8") as f:
        f.write(report + "\n")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore  (метод есть у консоли, Pylance его не знает)
    main()
