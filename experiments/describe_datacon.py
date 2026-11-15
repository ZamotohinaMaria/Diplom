"""Неделя 5 (второй датасет). Первичное описание DataCon 2019 Stage1 после convert_datacon.py.

Модели не обучает, читает только результаты конвертации и исходный CSV MalBehavD-V1 (для сравнения).
Дубли и конфликтующие метки считает audit_duplicates.py (запуск — ниже), здесь — остальное:
  1. Длины последовательностей по классам (raw и clean).
  2. Распределение размеров групп одинаковых последовательностей по классам и крупнейшие
     конфликтующие последовательности (одна и та же трасса с метками benign и malware).
  3. Признаки отчёта, не связанные со смыслом поведения (размер XML, число вызовов, процессов,
     раздел reboot, пометка TooManyBehavior, длина): по классам и ROC-AUC каждого признака
     отдельно — насколько хорошо он один разделяет классы. Это описание риска «подсказок»,
     а не модель.
  4. Словарь: служебные записи по классам, самые частые API, API с наибольшей разницей
     между классами, API только одного класса, пересечение со словарём MalBehavD-V1.
  5. Сравнение с MalBehavD-V1 по тем же показателям.

Нужны: derived/datacon/datacon_{raw,clean,meta,vocab}.csv (python experiments/convert_datacon.py).
Дубли (по варианту, в свою папку, исходный аудит MalBehavD не перезаписывается):
  python experiments/audit_duplicates.py --csv derived/datacon/datacon_raw.csv --out-dir derived/datacon/audit_raw --log experiments/logs/audit_datacon_raw.txt
  python experiments/audit_duplicates.py --csv derived/datacon/datacon_clean.csv --out-dir derived/datacon/audit_clean --log experiments/logs/audit_datacon_clean.txt

Результаты:
  derived/datacon/datacon_describe.md   отчёт со всеми таблицами
  experiments/logs/describe_datacon.txt то же, текстом

Запуск из корня репозитория:
  python experiments/describe_datacon.py
"""
import argparse
import os
import sys

import pandas as pd
from sklearn.metrics import roc_auc_score

from audit_duplicates import api_columns, row_sequence
from log_run import DATASET_CSV, ROOT, tracked_run

SIZE_BINS = [(1, 1, "1"), (2, 5, "2–5"), (6, 20, "6–20"), (21, 100, "21–100"), (101, 10 ** 9, "больше 100")]
SIDE = {   # столбец meta -> подпись
    "xml_bytes": "размер XML, байт",
    "n_actions": "число вызовов (с повторами)",
    "n_pids": "число процессов",
    "len_raw": "длина raw (уникальных API)",
    "len_clean": "длина clean",
    "has_reboot": "есть раздел reboot",
    "too_many_behavior": "пометка TooManyBehavior",
}


def parse_args():
    p = argparse.ArgumentParser(description="Первичное описание DataCon 2019 Stage1")
    p.add_argument("--datacon-dir", default=os.path.join(ROOT, "derived", "datacon"))
    p.add_argument("--malbehavd", default=DATASET_CSV)
    p.add_argument("--out", default=os.path.join(ROOT, "derived", "datacon", "datacon_describe.md"))
    p.add_argument("--log", default=os.path.join(ROOT, "experiments", "logs", "describe_datacon.txt"))
    return p.parse_args()


def sequences(path: str) -> pd.DataFrame:
    """Широкий CSV -> sha256, label, seq (список), key (строка для сравнения трасс)."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    seqs = [row_sequence(r) for r in df[api_columns(df)].values]
    return pd.DataFrame({"sha256": df["sha256"], "label": df["labels"].astype(float).astype(int),
                         "seq": seqs, "key": ["|".join(s) for s in seqs]})


def length_table(d: pd.DataFrame, name: str) -> pd.DataFrame:
    lens = d.seq.map(len)
    rows = []
    for lab, cls in ((0, "benign"), (1, "malware")):
        x = lens[d.label == lab]
        rows.append({"вариант": name, "класс": cls, "строк": len(x), "min": x.min(), "25%": x.quantile(.25),
                     "медиана": x.median(), "75%": x.quantile(.75), "max": x.max(), "среднее": round(x.mean(), 1)})
    return pd.DataFrame(rows)


def group_sizes(d: pd.DataFrame, name: str) -> pd.DataFrame:
    """Размер группы одинаковых трасс (в строках) -> сколько групп и строк каждого класса."""
    g = d.groupby(["key", "label"]).size().rename("size").reset_index()
    rows = []
    for lo, hi, title in SIZE_BINS:
        s = g[(g["size"] >= lo) & (g["size"] <= hi)]
        rows.append({"вариант": name, "размер группы": title,
                     "групп benign": int((s.label == 0).sum()), "строк benign": int(s[s.label == 0]["size"].sum()),
                     "групп malware": int((s.label == 1).sum()), "строк malware": int(s[s.label == 1]["size"].sum())})
    return pd.DataFrame(rows)


def conflicts(d: pd.DataFrame, name: str, k: int = 5) -> pd.DataFrame:
    c = d.groupby("key").label.agg(benign=lambda x: int((x == 0).sum()), malware=lambda x: int((x == 1).sum()))
    c = c[(c.benign > 0) & (c.malware > 0)].copy()
    c["строк"] = c.benign + c.malware
    c["длина"] = [len(k_.split("|")) for k_ in c.index]
    c["начало трассы"] = [" → ".join(k_.split("|")[:4]) + (" …" if len(k_.split("|")) > 4 else "") for k_ in c.index]
    c = c.sort_values("строк", ascending=False).head(k).reset_index(drop=True)
    return c.assign(вариант=name)[["вариант", "строк", "benign", "malware", "длина", "начало трассы"]]


def side_table(meta: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col, title in SIDE.items():
        b, m = meta.loc[meta.labels == 0, col], meta.loc[meta.labels == 1, col]
        binary = set(meta[col].unique()) <= {0, 1}
        auc = roc_auc_score(meta.labels, meta[col])
        rows.append({"признак": title,
                     "benign": f"{100 * b.mean():.1f}%" if binary else f"{b.median():g}",
                     "malware": f"{100 * m.mean():.1f}%" if binary else f"{m.median():g}",
                     "что показано": "доля файлов" if binary else "медиана",
                     "ROC-AUC": round(auc, 3)})
    return pd.DataFrame(rows)


def vocab_tables(vocab: pd.DataFrame) -> dict:
    real = vocab[vocab.service == 0].copy()
    real["разница долей"] = (real.share_malware - real.share_benign).round(3)
    cols = ["api", "share_benign", "share_malware", "разница долей", "in_malbehavd"]
    return {
        "service": vocab[vocab.service == 1][["api", "share_benign", "share_malware"]]
        .sort_values("share_malware", ascending=False),
        "top": real.sort_values("files_malware", ascending=False)
        .assign(both=lambda x: x.share_benign + x.share_malware)
        .sort_values("both", ascending=False).head(15)[cols],
        "skew_malware": real.sort_values("разница долей", ascending=False).head(10)[cols],
        "skew_benign": real.sort_values("разница долей").head(10)[cols],
        "only": pd.DataFrame([
            {"где встречается": "только в malware", "API": int(((real.files_benign == 0) & (real.files_malware > 0)).sum())},
            {"где встречается": "только в benign", "API": int(((real.files_malware == 0) & (real.files_benign > 0)).sum())},
            {"где встречается": "в обоих классах", "API": int(((real.files_malware > 0) & (real.files_benign > 0)).sum())},
            {"где встречается": "есть в MalBehavD-V1", "API": int(real.in_malbehavd.sum())},
            {"где встречается": "нет в MalBehavD-V1", "API": int((real.in_malbehavd == 0).sum())},
        ]),
        "real": real,
    }


def dataset_row(d: pd.DataFrame, name: str) -> dict:
    lens = d.seq.map(len)
    c = d.groupby("key").label.nunique()
    conflict_keys = set(c[c > 1].index)
    vocab = {a for s in d.seq for a in s}
    return {"датасет": name, "строк": len(d), "benign / malware": f"{(d.label == 0).sum()} / {(d.label == 1).sum()}",
            "уникальных трасс": f"{d.key.nunique()} ({100 * d.key.nunique() / len(d):.1f}%)",
            "уникальных benign": f"{100 * d[d.label == 0].key.nunique() / max((d.label == 0).sum(), 1):.1f}%",
            "уникальных malware": f"{100 * d[d.label == 1].key.nunique() / max((d.label == 1).sum(), 1):.1f}%",
            "строк с конфликтом меток": int(d.key.isin(conflict_keys).sum()),
            "длина: медиана (min–max)": f"{lens.median():g} ({lens.min()}–{lens.max()})",
            "словарь API": len(vocab)}


def md(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False)


def main():
    args = parse_args()
    paths = {k: os.path.join(args.datacon_dir, f"datacon_{k}.csv") for k in ("raw", "clean", "meta", "vocab")}
    with tracked_run("describe_datacon.py", params={k: os.path.relpath(v, ROOT) for k, v in paths.items()},
                     log_path=args.out, dataset_path=paths["clean"]) as run:
        raw, clean = sequences(paths["raw"]), sequences(paths["clean"])
        meta, vocab = pd.read_csv(paths["meta"]), pd.read_csv(paths["vocab"])
        mbv = sequences(args.malbehavd)

        dropped = meta[meta.kept_clean == 0]
        dropped_lines = [f"- `{r.sha256[:12]}…`, {'malware' if r.labels == 1 else 'benign'}, raw: "
                         + " → ".join(raw.loc[raw.sha256 == r.sha256, "seq"].iloc[0]) for r in dropped.itertuples()]
        v = vocab_tables(vocab)
        side = side_table(meta)

        report = "\n".join([
            "# DataCon 2019 Stage1: первичное описание",
            "",
            f"Источник: `{os.path.relpath(args.datacon_dir, ROOT)}` (convert_datacon.py). raw — все записи песочницы, "
            "clean — без служебных. Метки: 0 = benign, 1 = malware.",
            "",
            "## Сравнение с MalBehavD-V1",
            "",
            md(pd.DataFrame([dataset_row(mbv, "MalBehavD-V1"), dataset_row(raw, "DataCon raw"),
                             dataset_row(clean, "DataCon clean")])),
            "",
            "## Длина последовательности (уникальных API в порядке первого вызова)",
            "",
            md(pd.concat([length_table(raw, "raw"), length_table(clean, "clean")])),
            "",
            "Выпало из clean (не осталось ни одного вызова после удаления служебных записей):",
            *(dropped_lines or ["- нет"]),
            "",
            "## Размеры групп одинаковых трасс",
            "",
            "Группа — строки одного класса с одинаковой последовательностью.",
            "",
            md(pd.concat([group_sizes(raw, "raw"), group_sizes(clean, "clean")])),
            "",
            "## Крупнейшие конфликтующие трассы (одна трасса с метками обоих классов)",
            "",
            md(pd.concat([conflicts(raw, "raw"), conflicts(clean, "clean")])),
            "",
            "## Признаки отчёта, не связанные со смыслом поведения",
            "",
            "ROC-AUC — насколько один признак сам по себе разделяет классы (0.5 — никак, 1.0 — идеально; "
            "больше 0.5 — у malware значения выше).",
            "",
            md(side),
            "",
            "## Служебные записи песочницы (доля файлов класса)",
            "",
            md(v["service"]),
            "",
            "## 15 самых частых API (clean-словарь, доля файлов класса)",
            "",
            md(v["top"]),
            "",
            "## 10 API, которые чаще встречаются у malware",
            "",
            md(v["skew_malware"]),
            "",
            "## 10 API, которые чаще встречаются у benign",
            "",
            md(v["skew_benign"]),
            "",
            "## Словарь: где встречаются API (без служебных)",
            "",
            md(v["only"]),
            "",
            "API DataCon, которых нет в MalBehavD-V1: " + ", ".join(sorted(v["real"][v["real"].in_malbehavd == 0].api)),
        ])
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        os.makedirs(os.path.dirname(args.log), exist_ok=True)
        with open(args.log, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        print(report)
        run.set(metrics={f"auc:{r['признак']}": r["ROC-AUC"] for _, r in side.iterrows()},
                notes=f"report {os.path.relpath(args.out, ROOT)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore  (метод есть у консоли, Pylance его не знает)
    main()
