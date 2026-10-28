"""Общие функции задачи 4: загрузка данных и разбиений, подбор порогов на val, метрики на test.

Правило: всё, что выбирается (порог, гиперпараметры, эпоха), выбирается только по val.
Test используется один раз — в evaluate_test, когда всё уже зафиксировано.
"""
import json
import math
import os

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, f1_score, matthews_corrcoef, roc_auc_score

from audit_duplicates import api_columns, row_sequence
from log_run import DATASET_CSV, ROOT

SPLITS_DIR = os.path.join(ROOT, "derived", "splits")
HASHES_CSV = os.path.join(ROOT, "derived", "hashes.csv")
TARGET_TPR = 0.95


# ---------- данные ----------

def load_data(csv_path: str = DATASET_CSV, hashes_path: str = HASHES_CSV) -> pd.DataFrame:
    """Таблица по row_idx: seq (список вызовов), label, seq_hash."""
    df = pd.read_csv(csv_path)
    h = pd.read_csv(hashes_path)
    if not np.array_equal(h["sha256_file"].to_numpy(), df["sha256"].to_numpy()):
        raise ValueError(f"{hashes_path} не соответствует {csv_path}: перезапусти audit_duplicates.py")
    cols = api_columns(df)
    h["seq"] = [row_sequence(row) for row in df[cols].values]
    return h.set_index("row_idx")[["seq", "label", "seq_hash"]]


def split_path(protocol: str, seed: int, splits_dir: str = SPLITS_DIR) -> str:
    return os.path.join(splits_dir, f"{protocol}_seed{seed}.json")


def load_split(data: pd.DataFrame, path: str):
    """(train, val, test) — подтаблицы data по индексам из файла разбиения задачи 3."""
    with open(path, encoding="utf-8") as f:
        split = json.load(f)
    parts = [data.loc[split[p]] for p in ("train", "val", "test")]
    ids = [set(p.index) for p in parts]
    assert not (ids[0] & ids[1] or ids[0] & ids[2] or ids[1] & ids[2]), f"{path}: части пересекаются"
    return parts


def oov_stats(train_seqs, test_seqs) -> dict:
    """Насколько test «незнаком» словарю train: доля вызовов и доля трасс с неизвестными API."""
    vocab = {t for s in train_seqs for t in s}
    total = sum(len(s) for s in test_seqs)
    oov_calls = sum(t not in vocab for s in test_seqs for t in s)
    oov_seqs = sum(any(t not in vocab for t in s) for s in test_seqs)
    return {"oov_call_share": oov_calls / max(total, 1), "oov_seq_share": oov_seqs / max(len(test_seqs), 1)}


# ---------- пороги (только по val) ----------

def choose_threshold_mcc(y_val: np.ndarray, p_val: np.ndarray) -> float:
    """Порог с максимальным MCC на val. Кандидаты — все различные вероятности val.
    При равенстве берётся середина диапазона лучших порогов (устойчивее, чем крайний)."""
    cands = np.unique(p_val)
    scores = np.array([matthews_corrcoef(y_val, (p_val >= t).astype(int)) for t in cands])
    best = cands[np.isclose(scores, scores.max())]
    return float((best.min() + best.max()) / 2)


def threshold_at_tpr(y_val: np.ndarray, p_val: np.ndarray, target: float = TARGET_TPR) -> float:
    """Наибольший порог, при котором на val ловится не меньше target доли malware."""
    pos = np.sort(p_val[y_val == 1])[::-1]
    k = math.ceil(target * len(pos))
    return float(pos[k - 1])


# ---------- метрики ----------

def metrics_at(y: np.ndarray, p: np.ndarray, thr: float, thr_tpr: float) -> dict:
    pred = (p >= thr).astype(int)
    pred_tpr = (p >= thr_tpr).astype(int)
    neg, pos = (y == 0), (y == 1)
    return {
        "mcc": matthews_corrcoef(y, pred),
        "f1": f1_score(y, pred, zero_division=0),
        "pr_auc": average_precision_score(y, p),
        "roc_auc": roc_auc_score(y, p),
        "fpr_at_tpr95": float(pred_tpr[neg].mean()),   # доля benign, ложно отмеченных как malware
        "tpr_at_tpr95": float(pred_tpr[pos].mean()),   # реально достигнутый TPR на этих данных
    }


def evaluate_test(test: pd.DataFrame, p_test: np.ndarray, thr: float, thr_tpr: float) -> dict:
    """Метрики на test: по всем строкам и по дедуплицированному test (каждая последовательность один раз).

    Дедупликация: одинаковые трассы дают одинаковый вход и одинаковую вероятность,
    поэтому берём первую строку каждой группы seq_hash."""
    y = test["label"].to_numpy()
    out = metrics_at(y, p_test, thr, thr_tpr)
    keep = ~test["seq_hash"].duplicated().to_numpy()
    out.update({f"dedup_{k}": v for k, v in metrics_at(y[keep], p_test[keep], thr, thr_tpr).items()})
    out["n_test"], out["n_test_dedup"] = int(len(y)), int(keep.sum())
    return out


# ---------- сохранение ----------

def save_predictions(path: str, parts: dict) -> None:
    """Вероятности по строкам val и test — для анализа ошибок и бутстрепа позже."""
    rows = []
    for name, (frame, prob) in parts.items():
        rows.append(pd.DataFrame({"row_idx": frame.index, "part": name, "label": frame["label"].to_numpy(),
                                  "seq_hash": frame["seq_hash"].to_numpy(), "prob": prob}))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pd.concat(rows).to_csv(path, index=False)


def merge_results(path: str, new_rows: list) -> pd.DataFrame:
    """Дописывает строки в файл результатов, заменяя прежние строки с теми же (protocol, seed)."""
    new = pd.DataFrame(new_rows)
    if os.path.exists(path):
        old = pd.read_csv(path)
        key = set(zip(new["protocol"], new["seed"]))
        old = old[[(p, s) not in key for p, s in zip(old["protocol"], old["seed"])]]
        new = pd.concat([old, new], ignore_index=True)
    new = new.sort_values(["protocol", "seed"]).reset_index(drop=True)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new.to_csv(path, index=False)
    return new


def rounded(d: dict, nd: int = 4) -> dict:
    return {k: (round(float(v), nd) if isinstance(v, (float, np.floating)) else v) for k, v in d.items()}
