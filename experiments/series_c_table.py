"""Задача 12–13.11 (неделя 9–15.11.2026), итог: полная серия C — TF-IDF и GINE на пяти разбиениях C.

Правила серии зафиксированы 15.11.2026 до запуска seed 43–46 (0 - docs/conspects/week3/П1_протокол_серии_C)
и по результатам не меняются:
  1. Разбиения — derived/splits/C_seed{42..46}.json из пункта 2 недели 2–8.11, без пересборки.
  2. Модели и настройки — те же, что в пилоте и в A/B, без изменений:
       TF-IDF 1–3 + LogReg (baseline_tfidf.py, блок main): сетка C = 0.01…10000 не расширяется,
       даже если выбранный C снова окажется на краю;
       GINE e40 (run_gine_splits.py): все параметры по умолчанию, --device cpu.
  3. Словари строятся только по train; C у LogReg, эпоха, температура и оба порога — только по val.
     Test считается один раз, когда всё зафиксировано.
  4. Seed 42 — пилот (04.11): входит в серию без перезапуска, если код и конфигурация совпадают
     (это проверяет скрипт). Seed 43–46 запускаются по одному разу; перезапуск — только при технической
     ошибке, причина — в EXPERIMENTS.csv. Результат на test поводом для перезапуска не является.
  5. В таблицу входят все пять seed; ни один не исключается.
  6. Метрики: MCC, F1, PR-AUC, ROC-AUC, FPR@TPR95 — по всем строкам test и по уникальным трассам;
     ложные тревоги (FP) и пропуски (FN) при пороге MCC с val; время обучения.
     Сводка — среднее ± std (ddof=1) по пяти seed. Модели сравниваются на одних и тех же test:
     разница GINE − TF-IDF считается по каждому seed, затем среднее ± std разниц.

Что скрипт проверяет и при нарушении останавливается:
  - у каждой модели ровно seed 42–46: seed 42 из файла пилота, 43–46 из файла серии;
  - настройки в derived/configs одинаковы для всех seed модели, GINE везде на CPU;
  - хэш файла разбиения в конфигурации совпадает с текущим файлом;
  - test в предсказаниях совпадает с test разбиения, а MCC, пересчитанный по предсказаниям
    при сохранённом пороге, совпадает с записанным в файле результатов.

Нужны результаты:
  пилот  — derived/results_pilot_C_{tfidf,gine}.csv (уже есть)
  серия  — python experiments/baseline_tfidf.py --protocols C --seeds 43 44 45 46 --blocks main --run-name series_C
           python experiments/run_gine_splits.py --protocols C --seeds 43 44 45 46 --device cpu --run-name series_C
  Имена серий — параметры --pilot-name (по умолчанию pilot_C) и --run-name (по умолчанию series_C).

Результаты:
  derived/series_C_table.md       отчёт: таблица по seed, среднее ± std, разница моделей, ошибки, проверки
  derived/series_C_per_seed.csv   строка на (модель, seed), числа без округления, вместе с FP/FN
  derived/series_C_summary.csv    среднее и std по seed для каждой модели и метрики
  derived/series_C_paired.csv     разница GINE − TF-IDF по каждому seed

Запуск из корня репозитория:
  python experiments/series_c_table.py
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, matthews_corrcoef

from log_run import ROOT, file_sha256, tracked_run

SEEDS = [42, 43, 44, 45, 46]
PILOT_SEED = 42
MODELS = {"tfidf_logreg": "tfidf", "gine_e40": "gine"}   # модель -> префикс файлов
NAMES = {"tfidf_logreg": "TF-IDF 1–3 + LR", "gine_e40": "GINE e40"}
METRICS = ["mcc", "f1", "pr_auc", "roc_auc", "fpr_at_tpr95"]
ERRORS = ["fp", "fn"]
PAIRED = ["mcc", "f1", "dedup_mcc", "dedup_f1", "fp", "fn", "dedup_fp", "dedup_fn"]


def parse_args():
    p = argparse.ArgumentParser(description="Сводная таблица полной серии C (5 seed)")
    p.add_argument("--derived", default=os.path.join(ROOT, "derived"))
    p.add_argument("--out-dir", default=os.path.join(ROOT, "derived"))
    p.add_argument("--pilot-name", default="pilot_C", help="имя серии пилота (seed 42) в baseline_tfidf / run_gine_splits")
    p.add_argument("--run-name", default="series_C", help="имя серии seed 43–46 (--run-name при запуске моделей)")
    return p.parse_args()


# ---------- сбор и проверки ----------

def load_results(derived: str, pilot_name: str, series_name: str) -> pd.DataFrame:
    """Строки C по обеим моделям: seed 42 — из пилота, 43–46 — из серии."""
    parts = []
    for model, prefix in MODELS.items():
        pilot_file, series_file = f"results_{pilot_name}_{prefix}.csv", f"results_{series_name}_{prefix}.csv"
        for path, allowed in ((pilot_file, {PILOT_SEED}), (series_file, set(SEEDS) - {PILOT_SEED})):
            full = os.path.join(derived, path)
            if not os.path.exists(full):
                raise FileNotFoundError(f"нет {os.path.relpath(full, ROOT)}: сначала запуск модели (см. docstring)")
            r = pd.read_csv(full)
            r = r[(r.protocol == "C") & (r.model == model)]
            extra = set(r.seed) - allowed
            if extra:
                raise ValueError(f"{path}: лишние seed {sorted(extra)} (ожидались {sorted(allowed)})")
            parts.append(r.assign(source=path))
    res = pd.concat(parts, ignore_index=True)
    for model in MODELS:
        seeds = sorted(res[res.model == model].seed)
        if seeds != SEEDS:
            raise ValueError(f"{model}: seed {seeds}, ожидались {SEEDS} по одному разу")
    return res


def check_configs(derived: str) -> list:
    """Настройки одинаковы по seed, GINE на CPU, разбиение не менялось. Возвращает строки для отчёта."""
    lines = []
    for model, prefix in MODELS.items():
        settings = {}
        for seed in SEEDS:
            path = os.path.join(derived, "configs", f"{prefix}_C_seed{seed}.json")
            with open(path, encoding="utf-8") as f:
                cfg = json.load(f)
            split = os.path.join(ROOT, cfg["split_file"].replace("\\", os.sep))
            if cfg["split_sha256"] != file_sha256(split):
                raise ValueError(f"{os.path.relpath(path, ROOT)}: разбиение {cfg['split_file']} изменилось после запуска")
            settings[seed] = cfg["settings"]
        differ = [s for s in SEEDS if settings[s] != settings[PILOT_SEED]]
        if differ:
            raise ValueError(f"{model}: настройки seed {differ} отличаются от пилота (seed {PILOT_SEED})")
        if model == "gine_e40" and settings[PILOT_SEED].get("device") != "cpu":
            raise ValueError("GINE запускался не на CPU")
        lines.append(f"- `{model}`: настройки всех пяти seed совпадают с пилотом"
                     + (", везде CPU" if model == "gine_e40" else "") + "; файлы разбиений не менялись")
    return lines


def error_counts(derived: str, res: pd.DataFrame) -> pd.DataFrame:
    """FP / FN по предсказаниям test при пороге MCC с val; заодно сверка MCC с файлом результатов."""
    rows = []
    for r in res.itertuples():
        prefix = MODELS[r.model]
        pred = pd.read_csv(os.path.join(derived, "predictions", f"{prefix}_C_seed{r.seed}.csv"))
        test = pred[pred.part == "test"]
        with open(os.path.join(derived, "splits", f"C_seed{r.seed}.json"), encoding="utf-8") as f:
            if sorted(test.row_idx) != sorted(json.load(f)["test"]):
                raise ValueError(f"{prefix}_C_seed{r.seed}: test в предсказаниях не совпадает с разбиением")
        y, p = test["label"].to_numpy(), test["prob"].to_numpy()
        keep = ~test["seq_hash"].duplicated().to_numpy()   # как в eval_utils.evaluate_test
        row = {"model": r.model, "seed": r.seed}
        for tag, mask in (("", np.ones_like(keep)), ("dedup_", keep)):
            yy, pred_y = y[mask], (p[mask] >= r.thr_mcc).astype(int)
            mcc = matthews_corrcoef(yy, pred_y)
            if not np.isclose(mcc, getattr(r, f"{tag}mcc"), atol=1e-9):
                raise ValueError(f"{r.model} seed {r.seed}: {tag}mcc по предсказаниям {mcc:.6f}, "
                                 f"в файле {getattr(r, f'{tag}mcc'):.6f}")
            tn, fp, fn, tp = confusion_matrix(yy, pred_y, labels=[0, 1]).ravel()
            row.update({f"{tag}tn": tn, f"{tag}fp": fp, f"{tag}fn": fn, f"{tag}tp": tp,
                        f"{tag}n_benign": tn + fp, f"{tag}n_malware": fn + tp})
        rows.append(row)
    return pd.DataFrame(rows)


# ---------- таблицы ----------

def summary_table(per_seed: pd.DataFrame, cols: list) -> pd.DataFrame:
    g = per_seed.groupby("model")
    out = []
    for model in MODELS:
        sub = g.get_group(model)
        for c in cols:
            out.append({"model": model, "metric": c, "mean": sub[c].mean(), "std": sub[c].std(ddof=1),
                        "min": sub[c].min(), "max": sub[c].max()})
    return pd.DataFrame(out)


def paired_table(per_seed: pd.DataFrame) -> pd.DataFrame:
    """Разница GINE − TF-IDF на одном и том же test (одинаковый seed)."""
    a = per_seed[per_seed.model == "tfidf_logreg"].set_index("seed")
    b = per_seed[per_seed.model == "gine_e40"].set_index("seed")
    rows = []
    for seed in SEEDS:
        rows.append({"seed": seed, **{f"diff_{m}": b.at[seed, m] - a.at[seed, m] for m in PAIRED}})
    return pd.DataFrame(rows)


def mean_std(sub: pd.Series, nd: int = 4) -> str:
    return f"{sub.mean():.{nd}f} ± {sub.std(ddof=1):.{nd}f}"


def main():
    args = parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    md_path = os.path.join(args.out_dir, "series_C_table.md")

    with tracked_run("series_c_table.py", params={"seeds": SEEDS, "pilot_seed": PILOT_SEED,
                                                  "pilot_name": args.pilot_name, "run_name": args.run_name},
                     log_path=md_path, dataset_path=os.path.join(args.derived, "splits", "summary_C.csv")) as run:
        res = load_results(args.derived, args.pilot_name, args.run_name)
        config_lines = check_configs(args.derived)
        per_seed = res.merge(error_counts(args.derived, res), on=["model", "seed"])
        per_seed["selected"] = [f"C = {r.C:g}" if r.model == "tfidf_logreg" else f"эпоха {int(r.best_epoch)}"
                                for r in per_seed.itertuples()]
        per_seed = per_seed.sort_values(["model", "seed"], key=lambda s: s.map(list(MODELS).index)
                                        if s.name == "model" else s).reset_index(drop=True)

        all_cols = METRICS + [f"dedup_{m}" for m in METRICS] + ERRORS + [f"dedup_{e}" for e in ERRORS] + ["train_sec"]
        summary = summary_table(per_seed, all_cols)
        paired = paired_table(per_seed)
        per_seed.to_csv(os.path.join(args.out_dir, "series_C_per_seed.csv"), index=False, encoding="utf-8")
        summary.to_csv(os.path.join(args.out_dir, "series_C_summary.csv"), index=False, encoding="utf-8")
        paired.to_csv(os.path.join(args.out_dir, "series_C_paired.csv"), index=False, encoding="utf-8")

        # таблица по seed
        shown = per_seed.assign(model=per_seed.model.map(NAMES))
        by_seed = shown[["model", "seed", "mcc", "f1", "dedup_mcc", "dedup_f1", "pr_auc", "fpr_at_tpr95",
                         "selected", "train_sec"]]

        # среднее ± std
        ms_rows = []
        for model in MODELS:
            sub = per_seed[per_seed.model == model]
            ms_rows.append({"модель": NAMES[model], **{m: mean_std(sub[m]) for m in METRICS},
                            "train_sec": mean_std(sub["train_sec"], 1)})
        ms_dedup = [{"модель": NAMES[m], **{f"dedup_{x}": mean_std(per_seed[per_seed.model == m][f"dedup_{x}"])
                                            for x in METRICS}} for m in MODELS]

        # разница моделей
        paired_rows = []
        for m in PAIRED:
            d = paired[f"diff_{m}"]
            lower_better = m.endswith("fp") or m.endswith("fn")
            tfidf_better = int((d > 0).sum() if lower_better else (d < 0).sum())
            fmt = (lambda v: f"{v:+.0f}") if lower_better else (lambda v: f"{v:+.4f}")
            paired_rows.append({"метрика": m, **{f"seed {s}": fmt(v) for s, v in zip(paired.seed, d)},
                                "среднее ± std": f"{d.mean():+.{1 if lower_better else 4}f} ± "
                                                 f"{d.std(ddof=1):.{1 if lower_better else 4}f}",
                                "TF-IDF лучше, seed": f"{tfidf_better} из {len(d)}"})

        # ошибки
        err_rows = []
        for r in shown.itertuples():
            err_rows.append({"модель": r.model, "seed": r.seed,
                             "FP / benign": f"{r.fp} / {r.n_benign}", "FN / malware": f"{r.fn} / {r.n_malware}",
                             "FP / benign (уник.)": f"{r.dedup_fp} / {r.dedup_n_benign}",
                             "FN / malware (уник.)": f"{r.dedup_fn} / {r.dedup_n_malware}"})
        for model in MODELS:
            sub = per_seed[per_seed.model == model]
            err_rows.append({"модель": f"**{NAMES[model]}, сумма**", "seed": "42–46",
                             "FP / benign": f"{sub.fp.sum()} / {sub.n_benign.sum()}",
                             "FN / malware": f"{sub.fn.sum()} / {sub.n_malware.sum()}",
                             "FP / benign (уник.)": f"{sub.dedup_fp.sum()} / {sub.dedup_n_benign.sum()}",
                             "FN / malware (уник.)": f"{sub.dedup_fn.sum()} / {sub.dedup_n_malware.sum()}"})

        # контекст разбиений
        split_block = []
        summary_c = os.path.join(args.derived, "splits", "summary_C.csv")
        if os.path.exists(summary_c):
            s = pd.read_csv(summary_c)
            s = s[s.seed.isin(SEEDS)][["seed", "n_test", "n_test_unique_seqs", "largest_test_group",
                                       "largest_test_group_share_of_class"]].copy()
            s["largest_test_group_share_of_class"] = (100 * s["largest_test_group_share_of_class"]).map("{:.1f}%".format)
            split_block = ["", "## Разбиения", "",
                           "Крупнейшая группа test и её доля в своём классе test: чем она больше, тем сильнее "
                           "метрика по всем строкам зависит от одной группы.", "",
                           s.to_markdown(index=False)]

        report = "\n".join([
            "# Полная серия C (seed 42–46)",
            "",
            "Seed 42 — пилот (04.11), seed 43–46 — серия. Настройки и пороги выбраны на val, test посчитан один "
            "раз. Среднее ± std (ddof=1) по пяти seed.",
            "",
            "## Проверки",
            "",
            *config_lines,
            "- MCC, пересчитанный по сохранённым предсказаниям, совпадает с файлами результатов у всех 10 запусков",
            *split_block,
            "",
            "## Метрики по seed",
            "",
            "- `mcc`, `f1` — при пороге, выбранном по MCC на val; `dedup_*` — по уникальным трассам test",
            "- `fpr_at_tpr95` — доля benign, ложно отмеченных как malware, при пороге, который на val ловит 95% malware",
            "- `selected` — что выбрано на val (C у LogReg, лучшая эпоха из 40 у GINE)",
            "",
            by_seed.to_markdown(index=False, floatfmt=".4f"),
            "",
            "## Среднее ± std: все строки test",
            "",
            pd.DataFrame(ms_rows).to_markdown(index=False),
            "",
            "## Среднее ± std: уникальные трассы test",
            "",
            pd.DataFrame(ms_dedup).to_markdown(index=False),
            "",
            "## Разница GINE − TF-IDF на одних и тех же test",
            "",
            "Для MCC и F1 минус — GINE хуже; для FP и FN (число ошибок) плюс — у GINE ошибок больше. "
            "При пяти seed это описание разброса, а не проверка значимости.",
            "",
            pd.DataFrame(paired_rows).to_markdown(index=False),
            "",
            "## Ложные тревоги и пропуски",
            "",
            "FP — benign, отмеченные как malware; FN — пропущенные malware. Порог — по MCC на val.",
            "",
            pd.DataFrame(err_rows).to_markdown(index=False),
            "",
            "Числа без округления: `series_C_per_seed.csv`, `series_C_summary.csv`, `series_C_paired.csv`. "
            "Конфигурации — `derived/configs/{tfidf,gine}_C_seed{N}.json`, предсказания — "
            "`derived/predictions/{tfidf,gine}_C_seed{N}.csv`.",
        ])
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        print(report)

        run.set(metrics={f"{model}:{m}": round(float(per_seed[per_seed.model == model][m].mean()), 4)
                         for model in MODELS for m in ("mcc", "dedup_mcc", "f1", "dedup_f1")},
                notes=f"среднее по seed {SEEDS}; report {os.path.relpath(md_path, ROOT)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore  (метод есть у консоли, Pylance его не знает)
    main()
