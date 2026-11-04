"""Пункт 3 (неделя 2–8.11.2026), итог: таблица пилота на разбиении C.

Правила пилота зафиксированы до запуска (04.11.2026) и по результатам не меняются:
  1. Разбиение — только derived/splits/C_seed42.json (выбрано в пункте 2 как разбиение пилота).
     Другие seed C в пилоте не используются.
  2. Модели и настройки — те же, что в A/B, без изменений:
       TF-IDF 1–3 + LogReg (baseline_tfidf.py, блок main): сетка C, max_iter, sublinear_tf — как в A/B;
       GINE e40 (run_gine_splits.py): все параметры по умолчанию.
  3. Словари строятся только по train; C у LogReg, эпоха, температура и оба порога — только по val.
     Test считается один раз, когда всё зафиксировано.
  4. Перезапуск — только при технической ошибке (скрипт упал, не хватило памяти); причина — в EXPERIMENTS.csv.
     Результат на test поводом для перезапуска не является. GINE запускается один раз и на CPU
     (--device cpu): на GPU результат при том же seed заметно плавает (проверка 04.11 на копии B_seed42:
     MCC 0.854 и 0.894 при разных запусках), на CPU два запуска совпали точно. В A/B GINE считался на GPU.
  5. Метрики: MCC, F1, PR-AUC, ROC-AUC, FPR@TPR95, они же по уникальным трассам (dedup_*), время обучения.
  6. Это пилот реализуемости: по одному разбиению выводов о значимости и о превосходстве модели нет.
     Средние A/B даются только для контекста: это другие разбиения и среднее по 5 seed, а не одно значение.

Нужны результаты пилота:
  python experiments/baseline_tfidf.py --protocols C --seeds 42 --blocks main
  python experiments/run_gine_splits.py --protocols C --seeds 42 --device cpu

Результаты:
  derived/pilot_C_table.md    отчёт: таблица пилота, выбранные на val настройки, контекст A/B
  derived/pilot_C_table.csv   числа пилота без округления (строка на модель)

Запуск из корня репозитория:
  python experiments/pilot_c_table.py
"""
import argparse
import os
import sys

import pandas as pd

from log_run import ROOT, tracked_run

METRICS = ["mcc", "f1", "pr_auc", "roc_auc", "fpr_at_tpr95"]
PILOT_SEED = 42


def parse_args():
    p = argparse.ArgumentParser(description="Таблица пилота на разбиении C")
    p.add_argument("--results", nargs="+", default=[os.path.join(ROOT, "derived", "results_pilot_C_tfidf.csv"),
                                                    os.path.join(ROOT, "derived", "results_pilot_C_gine.csv")])
    p.add_argument("--h1-table", default=os.path.join(ROOT, "derived", "h1_table.csv"))
    p.add_argument("--split-summary", default=os.path.join(ROOT, "derived", "splits", "summary_C.csv"))
    p.add_argument("--out-dir", default=os.path.join(ROOT, "derived"))
    return p.parse_args()


def main():
    args = parse_args()
    missing = [p for p in args.results if not os.path.exists(p)]
    if missing:
        raise FileNotFoundError(f"нет результатов пилота: {', '.join(os.path.relpath(p, ROOT) for p in missing)}")
    md_path = os.path.join(args.out_dir, "pilot_C_table.md")

    with tracked_run("pilot_c_table.py", params={"results": [os.path.relpath(p, ROOT) for p in args.results]},
                     seed=PILOT_SEED, log_path=md_path, dataset_path=args.results[0]) as run:
        res = pd.concat([pd.read_csv(p) for p in args.results], ignore_index=True)
        res = res[(res.protocol == "C") & (res.seed == PILOT_SEED)]
        if sorted(res.model) != ["gine_e40", "tfidf_logreg"]:
            raise ValueError(f"ожидалось по одной строке tfidf_logreg и gine_e40 на C seed {PILOT_SEED}, "
                             f"есть: {sorted(res.model)}")
        res.to_csv(os.path.join(args.out_dir, "pilot_C_table.csv"), index=False, encoding="utf-8")

        cols_all = ["model"] + METRICS + ["train_sec"]
        cols_dedup = ["model"] + [f"dedup_{m}" for m in METRICS] + ["n_test", "n_test_dedup"]
        # что выбрано на val: у LogReg — C, у GINE — эпоха и температура
        selected = []
        for r in res.itertuples():
            if r.model == "tfidf_logreg":
                own = f"C = {r.C:g}, признаков (n-грамм) {int(r.n_features)}"
            else:
                own = f"лучшая эпоха {int(r.best_epoch)}, температура {r.temperature:.3f}, словарь API {int(r.vocab_size)}"
            selected.append(f"- `{r.model}`: {own}; порог по MCC {r.thr_mcc:.4f}, порог для TPR = 0.95 "
                            f"{r.thr_tpr95:.4f}; доля трасс test с незнакомыми API {100 * r.oov_seq_share:.1f}%")

        split_block = []
        if os.path.exists(args.split_summary):
            s = pd.read_csv(args.split_summary)
            s = s[s.seed == PILOT_SEED].iloc[0]
            split_block = [
                "",
                f"Разбиение C_seed{PILOT_SEED}: train / val / test = {s.n_train} / {s.n_val} / {s.n_test}, "
                f"уникальных трасс в test {s.n_test_unique_seqs}; крупнейшая группа test — {s.largest_test_group} "
                f"строк ({100 * s.largest_test_group_share_of_class:.1f}% своего класса в test).",
            ]

        context_block = []
        if os.path.exists(args.h1_table):
            h1 = pd.read_csv(args.h1_table)
            context_block = [
                "",
                "## Контекст: средние A и B (пункт 1)",
                "",
                "Только для ориентира: A и B — другие разбиения, значения — среднее ± std по 5 seed; "
                "одно значение C с ними напрямую не сравнивается.",
                "",
                h1[["model", "protocol", "mcc", "f1", "dedup_mcc", "dedup_f1"]].to_markdown(index=False),
            ]

        report = "\n".join([
            f"# Пилот на разбиении C (seed {PILOT_SEED})",
            "",
            f"Источники: {', '.join(f'`{os.path.relpath(p, ROOT)}`' for p in args.results)}. "
            "Настройки и пороги выбраны на val, метрики посчитаны на test один раз. "
            "Пилот реализуемости: одно разбиение, без выводов о значимости.",
            *split_block,
            "",
            "## Метрики: все строки test",
            "",
            "- `mcc`, `f1` — при пороге, выбранном по MCC на val",
            "- `pr_auc`, `roc_auc` — от порога не зависят",
            "- `fpr_at_tpr95` — доля benign, ложно отмеченных как malware, при пороге, который на val "
            "ловит 95% malware (меньше = лучше)",
            "- `train_sec` — время обучения, секунд (у TF-IDF — вместе с подбором C по val, "
            "у GINE — 40 эпох с оценкой на val)",
            "",
            res[cols_all].to_markdown(index=False, floatfmt=".4f"),
            "",
            "## Метрики: уникальные трассы test",
            "",
            "- `dedup_*` — те же метрики на test, где каждая последовательность учтена один раз",
            "- `n_test` / `n_test_dedup` — строк в test / уникальных трасс",
            "",
            res[cols_dedup].to_markdown(index=False, floatfmt=".4f"),
            "",
            "## Что выбрано на val",
            "",
            *selected,
            *context_block,
            "",
            "Конфигурации запусков: `derived/configs/{tfidf,gine}_C_seed42.json`; "
            "предсказания: `derived/predictions/{tfidf,gine}_C_seed42.csv`.",
        ])
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        print(report)

        run.set(metrics={f"{r.model}:{m}": round(float(getattr(r, m)), 4)
                         for r in res.itertuples() for m in ("mcc", "dedup_mcc", "train_sec")},
                notes=f"pilot C seed {PILOT_SEED}; report {os.path.relpath(md_path, ROOT)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore  (метод есть у консоли, Pylance его не знает)
    main()
