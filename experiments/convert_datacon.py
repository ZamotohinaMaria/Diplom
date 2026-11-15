"""Неделя 5 (второй датасет). Перевод DataCon 2019 Stage1 в формат MalBehavD-V1.

Исходные данные: XML-отчёты песочницы, по одному на файл:
  DataCon 2019 Stage1/train/black/<sha256>.xml   — 10 000 вредоносных
  DataCon 2019 Stage1/train/white/<sha256>.xml   — 20 000 безобидных
  DataCon 2019 Stage1/safe_type_train.csv        — метки (safe_type: 1 = black, 0 = white)
Папка test/ не используется: у неё нет меток (это была выборка для отправки на соревнование).
Исходные файлы скрипт только читает.

Формат результата такой же, как у MalBehavD-V1-dataset.csv:
  sha256, labels, 0, 1, 2, ...  — уникальные имена API в порядке первого вызова, хвост пустой.
labels: 1 = malware, 0 = benign. Вызовы берутся из обоих разделов отчёта по порядку
(сначала start_boot, затем reboot), из всех процессов.

Два варианта:
  raw   — все значения api_name как есть, включая служебные записи песочницы;
  clean — без служебных записей: всё, что начинается с Fake_, и SERVICE_APIS ниже
          (это пометки песочницы, а не вызовы Windows API).
Если в clean у файла не осталось ни одного вызова, строка в CSV не попадает
(audit_duplicates.py не принимает пустые последовательности); она остаётся в meta с kept_clean=0.

Результаты (в --out-dir, по умолчанию derived/datacon/):
  datacon_raw.csv     вариант raw в формате MalBehavD
  datacon_clean.csv   вариант clean в формате MalBehavD
  datacon_meta.csv    строка на файл: метка, размер отчёта, число вызовов, длины raw/clean,
                      есть ли раздел reboot, число процессов, была ли пометка TooManyBehavior, ошибки разбора.
                      Нужна для проверки признаков, которые выдают метку без смысла поведения.
  datacon_vocab.csv   словарь: в скольких файлах каждого класса встречается API,
                      служебный ли он, есть ли он в словаре MalBehavD-V1
  experiments/logs/convert_datacon.txt   текстовый отчёт (то же, что на экране)

Запуск из корня репозитория (полный прогон 23 ГБ, несколько процессов):
  python experiments/convert_datacon.py
Пробный прогон на 50 файлах каждого класса в отдельную папку:
  python experiments/convert_datacon.py --limit 50 --out-dir derived/datacon_test
"""
import argparse
import collections
import os
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ProcessPoolExecutor

import pandas as pd

from log_run import DATASET_CSV, ROOT, tracked_run

DATACON_DIR = os.path.join(ROOT, "DataCon 2019 Stage1")
SERVICE_APIS = {"AnalyzeStart", "AnalyzeStop", "TryToAnalyze", "TooManyBehavior", "UnpackSelf"}
CLASS_DIRS = {"black": 1, "white": 0}  # папка -> labels


def parse_args():
    p = argparse.ArgumentParser(description="DataCon 2019 Stage1 -> формат MalBehavD-V1 (raw и clean)")
    p.add_argument("--datacon-dir", default=DATACON_DIR)
    p.add_argument("--out-dir", default=os.path.join(ROOT, "derived", "datacon"))
    p.add_argument("--log", default=os.path.join(ROOT, "experiments", "logs", "convert_datacon.txt"))
    p.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    p.add_argument("--limit", type=int, default=0, help="взять только N первых файлов каждого класса (проба)")
    return p.parse_args()


def is_service(api: str) -> bool:
    return api.startswith("Fake_") or api in SERVICE_APIS


def parse_report(path: str) -> dict:
    """Один XML -> последовательности raw/clean и описательные поля. Разбор потоковый:
    отчёты бывают по несколько МБ, обработанные узлы сразу удаляются из памяти."""
    raw, seen = [], set()
    n_actions, pids, sections = 0, set(), set()
    error = ""
    try:
        for event, el in ET.iterparse(path, events=("start", "end")):
            if event == "start":
                if el.tag in ("start_boot", "reboot"):
                    sections.add(el.tag)
                continue
            if el.tag == "action":
                api = el.get("api_name") or ""
                n_actions += 1
                pids.add(el.get("call_pid"))
                if api and api not in seen:
                    seen.add(api)
                    raw.append(api)
                el.clear()
    except ET.ParseError as exc:  # оставляем то, что успели прочитать, и помечаем файл
        error = f"ParseError: {exc}"
    clean = [a for a in raw if not is_service(a)]
    return {
        "raw": raw,
        "clean": clean,
        "xml_bytes": os.path.getsize(path),
        "n_actions": n_actions,
        "len_raw": len(raw),
        "len_clean": len(clean),
        "has_reboot": int("reboot" in sections),
        "n_pids": len(pids - {None, "0"}),
        "too_many_behavior": int("TooManyBehavior" in seen),
        "parse_error": error,
    }


def _job(item):
    sha, folder, path = item
    return sha, folder, parse_report(path)


def list_files(datacon_dir: str, limit: int) -> list:
    items = []
    for folder in CLASS_DIRS:
        d = os.path.join(datacon_dir, "train", folder)
        names = sorted(n for n in os.listdir(d) if n.lower().endswith(".xml"))
        if limit:
            names = names[:limit]
        items += [(os.path.splitext(n)[0].lower(), folder, os.path.join(d, n)) for n in names]
    return items


def to_wide(rows: list, key: str) -> pd.DataFrame:
    """Строки [(sha256, labels, seq)] -> широкая таблица как в MalBehavD (колонки 0..max_len-1)."""
    rows = [r for r in rows if r[2][key]]
    width = max((len(r[2][key]) for r in rows), default=0)
    data = [[sha, lab] + r[key] + [""] * (width - len(r[key])) for sha, lab, r in rows]
    return pd.DataFrame(data, columns=["sha256", "labels"] + [str(i) for i in range(width)])


def malbehavd_vocab() -> set:
    try:
        df = pd.read_csv(DATASET_CSV)
    except OSError:
        return set()
    return {v for v in df.iloc[:, 2:].values.ravel() if isinstance(v, str) and v.strip()}


def describe(df: pd.DataFrame, name: str) -> str:
    lens = (df.iloc[:, 2:] != "").sum(axis=1)
    by = df.groupby("labels").size().to_dict()
    seq = df.iloc[:, 2:].apply(lambda r: "|".join(x for x in r if x), axis=1)
    return (f"{name}: строк {len(df)} (malware {by.get(1, 0)}, benign {by.get(0, 0)}), "
            f"длина медиана {lens.median():.0f}, min {lens.min()}, max {lens.max()}, "
            f"уникальных последовательностей {seq.nunique()} ({seq.nunique() / max(len(df), 1):.1%})")


def main():
    args = parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    os.makedirs(os.path.dirname(args.log), exist_ok=True)
    labels_csv = os.path.join(args.datacon_dir, "safe_type_train.csv")
    out = {k: os.path.join(args.out_dir, f"datacon_{k}.csv") for k in ("raw", "clean", "meta", "vocab")}

    with tracked_run("convert_datacon.py", params=vars(args), log_path=args.log,
                     dataset_path=labels_csv) as run:
        labels = pd.read_csv(labels_csv)
        labels["id"] = labels["id"].str.lower()
        label_of = dict(zip(labels["id"], labels["safe_type"].astype(int)))

        items = list_files(args.datacon_dir, args.limit)
        print(f"Файлов к разбору: {len(items)}, процессов: {args.workers}", flush=True)
        results = []
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for i, res in enumerate(pool.map(_job, items, chunksize=16), 1):
                results.append(res)
                if i % 1000 == 0 or i == len(items):
                    print(f"  {i}/{len(items)}", flush=True)

        # метки: из safe_type_train.csv; папка — для сверки
        rows, meta, problems = [], [], collections.Counter()
        for sha, folder, r in results:
            lab = label_of.get(sha)
            if lab is None:
                problems["нет метки в safe_type_train.csv"] += 1
                continue
            if lab != CLASS_DIRS[folder]:
                problems["метка не совпадает с папкой"] += 1
            if r["parse_error"]:
                problems["ошибка разбора XML (взята прочитанная часть)"] += 1
            rows.append((sha, lab, r))
            meta.append({"sha256": sha, "labels": lab, "folder": folder,
                         **{k: v for k, v in r.items() if k not in ("raw", "clean")},
                         "kept_raw": int(r["len_raw"] > 0), "kept_clean": int(r["len_clean"] > 0)})

        raw_df, clean_df, meta_df = to_wide(rows, "raw"), to_wide(rows, "clean"), pd.DataFrame(meta)
        raw_df.to_csv(out["raw"], index=False)
        clean_df.to_csv(out["clean"], index=False)
        meta_df.to_csv(out["meta"], index=False)

        # словарь: в скольких файлах каждого класса встречается API
        mbv = malbehavd_vocab()
        cnt = {0: collections.Counter(), 1: collections.Counter()}
        for _, lab, r in rows:
            cnt[lab].update(r["raw"])
        apis = sorted(set(cnt[0]) | set(cnt[1]))
        n_cls = meta_df.groupby("labels").size().to_dict()
        vocab = pd.DataFrame({
            "api": apis,
            "files_malware": [cnt[1][a] for a in apis],
            "files_benign": [cnt[0][a] for a in apis],
            "service": [int(is_service(a)) for a in apis],
            "in_malbehavd": [int(a in mbv) for a in apis],
        })
        vocab["share_malware"] = (vocab.files_malware / max(n_cls.get(1, 0), 1)).round(4)
        vocab["share_benign"] = (vocab.files_benign / max(n_cls.get(0, 0), 1)).round(4)
        vocab = vocab.sort_values(["files_malware", "files_benign"], ascending=False)
        vocab.to_csv(out["vocab"], index=False)

        real = vocab[vocab.service == 0]
        g = meta_df.groupby("labels")
        side = pd.DataFrame({
            "xml_MB_median": g.xml_bytes.median() / 1e6,
            "n_actions_median": g.n_actions.median(),
            "len_raw_median": g.len_raw.median(),
            "len_clean_median": g.len_clean.median(),
            "has_reboot_share": g.has_reboot.mean(),
            "too_many_behavior_share": g.too_many_behavior.mean(),
            "n_pids_median": g.n_pids.median(),
        }).rename(index={0: "benign", 1: "malware"}).round(3)

        report = "\n".join([
            f"Источник: {args.datacon_dir}" + (f"  (проба: --limit {args.limit})" if args.limit else ""),
            f"Разобрано файлов: {len(results)}, взято с меткой: {len(rows)}",
            "Проблемы: " + (", ".join(f"{k}: {v}" for k, v in problems.items()) or "нет"),
            "",
            describe(raw_df, "raw  "),
            describe(clean_df, "clean"),
            f"Выпало из clean (пустая последовательность): {int((meta_df.kept_clean == 0).sum())}",
            "",
            f"Словарь: всего {len(vocab)}, служебных {int(vocab.service.sum())}, "
            f"настоящих API {len(real)}; из них есть в MalBehavD-V1: {int(real.in_malbehavd.sum())} "
            f"(словарь MalBehavD-V1: {len(mbv)})",
            "Служебные записи: " + ", ".join(vocab[vocab.service == 1].api),
            "",
            "[Признаки, не связанные со смыслом поведения, по классам]",
            side.to_string(),
            "",
            "Сохранено: " + "\n           ".join(out.values()),
        ])
        print(report)
        with open(args.log, "w", encoding="utf-8") as f:
            f.write(report + "\n")

        run.set(metrics={
            "files": len(results), "rows_raw": len(raw_df), "rows_clean": len(clean_df),
            "vocab_all": len(vocab), "vocab_real": len(real),
            "vocab_real_in_malbehavd": int(real.in_malbehavd.sum()),
            "problems": dict(problems),
        }, notes="outputs: " + ", ".join(os.path.relpath(p, ROOT) for p in out.values()))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore  (как в audit_duplicates.py)
    sys.exit(main())
