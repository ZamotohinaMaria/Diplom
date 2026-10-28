"""Задача 4, итог: таблица «модель × протокол» (среднее ± std по seed) и разница A − B для проверки H1.

H1: при протоколе A (случайное разбиение) метрики выше, чем при B (групповое).
Скрипт только считает числа; вывод о том, подтверждается ли H1, делается вручную.

Читает derived/results_tfidf.csv и derived/results_gine.csv (то, что есть).

Результаты:
  derived/h1_table.md    отчёт: таблицы среднее ± std, разница A − B и пояснения к столбцам
  derived/h1_table.csv   среднее ± std (для дальнейшей обработки)
  derived/h1_diff.csv    разница A − B по каждой модели и метрике (числа без округления)

Запуск из корня репозитория:
  python experiments/h1_table.py
"""
import argparse
import os
import sys

import pandas as pd
from scipy.stats import ttest_ind

from log_run import ROOT, tracked_run

METRICS = ["mcc", "pr_auc", "roc_auc", "f1", "fpr_at_tpr95"]
LOWER_IS_BETTER = {"fpr_at_tpr95"}


def parse_args():
    p = argparse.ArgumentParser(description="Сводная таблица H1")
    p.add_argument("--results", nargs="+", default=[os.path.join(ROOT, "derived", "results_tfidf.csv"),
                                                    os.path.join(ROOT, "derived", "results_gine.csv")])
    p.add_argument("--out-dir", default=os.path.join(ROOT, "derived"))
    return p.parse_args()


def mean_std_table(res: pd.DataFrame, metrics: list) -> pd.DataFrame:
    g = res.groupby(["model", "protocol"])
    out = g.size().rename("n_seeds").to_frame()
    for m in metrics:
        out[m] = [f"{a:.4f} ± {s:.4f}" for a, s in zip(g[m].mean(), g[m].std(ddof=1))]
    return out.reset_index()


def diff_table(res: pd.DataFrame, metrics: list) -> pd.DataFrame:
    rows = []
    for model, sub in res.groupby("model"):
        a, b = sub[sub.protocol == "A"], sub[sub.protocol == "B"]
        if a.empty or b.empty:
            continue
        for m in metrics:
            diff = a[m].mean() - b[m].mean()
            rows.append({
                "model": model, "metric": m,
                "mean_A": a[m].mean(), "mean_B": b[m].mean(),
                "diff_A_minus_B": diff,
                "std_A": a[m].std(ddof=1), "std_B": b[m].std(ddof=1),
                # во сколько раз разница больше наибольшего разброса по seed
                "diff_to_max_std": abs(diff) / max(a[m].std(ddof=1), b[m].std(ddof=1), 1e-12),
                "A_better": (diff < 0) if m.replace("dedup_", "") in LOWER_IS_BETTER else (diff > 0),
                "welch_p": ttest_ind(a[m], b[m], equal_var=False).pvalue,
            })
    return pd.DataFrame(rows)


def main():
    args = parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    md_path = os.path.join(args.out_dir, "h1_table.md")
    paths = [p for p in args.results if os.path.exists(p)]
    if not paths:
        raise FileNotFoundError("нет файлов результатов: сначала запусти baseline_tfidf.py и run_gine_splits.py")

    with tracked_run("h1_table.py", params={"results": [os.path.relpath(p, ROOT) for p in paths]},
                     log_path=md_path, dataset_path=paths[0]) as run:
        res = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
        warnings = [f"- {m} / {p}: seed {sorted(s.seed)} (ожидалось 5)"
                    for (m, p), s in res.groupby(["model", "protocol"]) if len(s) != 5]

        all_metrics = METRICS + [f"dedup_{m}" for m in METRICS]
        table = mean_std_table(res, all_metrics)
        diff = diff_table(res, all_metrics)
        table.to_csv(os.path.join(args.out_dir, "h1_table.csv"), index=False, encoding="utf-8")
        diff.to_csv(os.path.join(args.out_dir, "h1_diff.csv"), index=False, encoding="utf-8")

        shown_diff = diff.copy()
        for c in ["mean_A", "mean_B", "diff_A_minus_B", "std_A", "std_B"]:
            shown_diff[c] = shown_diff[c].map(lambda v: f"{v:+.4f}" if c == "diff_A_minus_B" else f"{v:.4f}")
        shown_diff["diff_to_max_std"] = shown_diff["diff_to_max_std"].map(lambda v: f"{v:.2f}")
        shown_diff["welch_p"] = shown_diff["welch_p"].map(lambda v: f"{v:.3f}")

        report = "\n".join([
            "# Проверка H1",
            "",
            "**H1:** при протоколе A (случайное разбиение) метрики выше, чем при B (групповое).",
            "",
            f"Источники: {', '.join(f'`{os.path.relpath(p, ROOT)}`' for p in paths)}. "
            "Среднее ± стандартное отклонение (ddof=1) по seed. Метрики посчитаны на test, порог выбран на val.",
            *(["", "**ВНИМАНИЕ: не у всех моделей 5 seed:**", "", *warnings] if warnings else []),
            "",
            "## Метрики",
            "",
            "- `mcc`, `f1` — при пороге, выбранном по MCC на val",
            "- `pr_auc`, `roc_auc` — от порога не зависят",
            "- `fpr_at_tpr95` — доля benign, ложно отмеченных как malware, при пороге, который на val "
            "ловит 95% malware (меньше = лучше)",
            "- `dedup_*` — те же метрики на test, где каждая последовательность учтена один раз",
            "- `n_seeds` — сколько разбиений (seed) усреднено",
            "",
            "## Все строки test",
            "",
            table[["model", "protocol", "n_seeds"] + METRICS].to_markdown(index=False),
            "",
            "## Дедуплицированный test",
            "",
            table[["model", "protocol"] + [f"dedup_{m}" for m in METRICS]].to_markdown(index=False),
            "",
            "## Разница A − B",
            "",
            "- `diff_A_minus_B` — среднее A минус среднее B (для `fpr_at_tpr95` меньше = лучше)",
            "- `std_A` / `std_B` — разброс по seed в каждом протоколе",
            "- `diff_to_max_std` — |разница| / наибольший из двух разбросов; меньше 1 — разница "
            "укладывается в разброс по seed",
            "- `A_better` — метрика лучше при протоколе A",
            "- `welch_p` — p-value t-теста Уэлча (A и B — независимые выборки по 5 seed); "
            "при 5 значениях на группу тест слабый, это ориентир, а не доказательство",
            "",
            shown_diff.to_markdown(index=False),
            "",
            "Числа без округления: `h1_table.csv`, `h1_diff.csv` в той же папке.",
        ])
        # print(report)  # полный отчёт в консоль — при необходимости раскомментировать
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        print(f"Прочитано: {', '.join(os.path.relpath(p, ROOT) for p in paths)} "
              f"({len(res)} строк, моделей: {res['model'].nunique()})")
        if warnings:
            print("ВНИМАНИЕ: не у всех моделей 5 seed:\n" + "\n".join(warnings))
        print(f"Отчёт: {os.path.relpath(md_path, ROOT)}")
        print(f"Числа без округления: {os.path.relpath(os.path.join(args.out_dir, 'h1_table.csv'), ROOT)}, "
              f"{os.path.relpath(os.path.join(args.out_dir, 'h1_diff.csv'), ROOT)}")

        run.set(metrics={f"{r.model}:{r.metric}": round(float(r.diff_A_minus_B), 4)
                         for r in diff.itertuples() if not r.metric.startswith("dedup_")},
                notes="значения — разница A − B по средним")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore  (метод есть у консоли, Pylance его не знает)
    main()
