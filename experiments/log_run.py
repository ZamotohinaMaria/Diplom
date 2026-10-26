"""Журнал запусков: строка в EXPERIMENTS.csv появляется в начале запуска (status=running)
и обновляется в конце (ok / failed / interrupted).

    from log_run import tracked_run
    with tracked_run("train_gine.py", params=cfg, seed=42, dataset_path=csv) as run:
        ...
        run.set(metrics={"mcc": 0.9}, log_path="...")

Ошибки самого журнала (например, файл открыт в Excel) только печатаются и не роняют обучение.
Если процесс убит без возможности перехвата (kill -9, выключение питания), строка остаётся
со статусом running: это и есть признак оборванного запуска.
"""
import csv
import hashlib
import json
import os
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPERIMENTS_CSV = os.path.join(ROOT, "EXPERIMENTS.csv")
DATASET_CSV = os.path.join(ROOT, "MalbehavD-V1-main", "MalBehavD-V1-dataset.csv")
COLUMNS = ["date", "script", "params", "seed", "data_version", "metrics", "log_path", "status", "notes"]


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def data_version(split_file: str = "", dataset_path: str = DATASET_CSV) -> str:
    """sha256 исходного файла данных + имя файла разбиения (если есть)."""
    try:
        version = f"sha256:{file_sha256(dataset_path)}"
    except OSError:
        version = f"sha256:unavailable({os.path.basename(str(dataset_path))})"
    if split_file:
        version += f"|split:{os.path.basename(split_file)}"
    return version


def _cell(value) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return "" if value is None else str(value)


def _warn(msg: str) -> None:
    print(f"[log_run] {msg}", file=sys.stderr)


class _Lock:
    """Простой файловый замок: два ночных запуска не должны затереть записи друг друга."""

    def __init__(self, path: str, timeout: float = 15.0):
        self.path, self.timeout = path + ".lock", timeout

    def __enter__(self):
        deadline = time.time() + self.timeout
        while True:
            try:
                os.close(os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                return self
            except FileExistsError:
                if time.time() > deadline:  # замок завис после падения: забираем
                    return self
                time.sleep(0.1)

    def __exit__(self, *exc):
        try:
            os.remove(self.path)
        except OSError:
            pass


def _read_rows(csv_path: str) -> list:
    if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
        return []
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_rows(csv_path: str, rows: list) -> None:
    tmp = csv_path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, csv_path)


class RunHandle:
    def __init__(self, row: dict, csv_path: str):
        self.row, self.csv_path, self.done = row, csv_path, False

    def set(self, **fields) -> None:
        """Обновляет поля строки (metrics, notes, log_path, params, status ...) в памяти."""
        for k, v in fields.items():
            if k not in COLUMNS:
                raise KeyError(k)
            self.row[k] = _cell(v)

    def flush(self) -> None:
        """Записывает текущее состояние строки в CSV (ищет её по date+script+seed)."""
        key = (self.row["date"], self.row["script"], self.row["seed"])
        try:
            with _Lock(self.csv_path):
                rows = _read_rows(self.csv_path)
                for i in range(len(rows) - 1, -1, -1):
                    if (rows[i]["date"], rows[i]["script"], rows[i]["seed"]) == key:
                        rows[i] = dict(self.row)
                        break
                else:
                    rows.append(dict(self.row))
                _write_rows(self.csv_path, rows)
        except Exception as exc:
            _warn(f"не удалось обновить {self.csv_path}: {exc!r}")

    def finish(self, status: str = "ok", **fields) -> None:
        if self.done:
            return
        self.set(status=status, **fields)
        self.flush()
        self.done = True


def start_run(script, params=None, seed=None, split_file="", log_path="", notes="",
              dataset_path: str = DATASET_CSV, csv_path: str = EXPERIMENTS_CSV) -> RunHandle:
    """Сразу дописывает строку со status=running и возвращает handle."""
    row = {
        "date": datetime.now().isoformat(timespec="seconds"),
        "script": script,
        "params": _cell(params),
        "seed": _cell(seed),
        "data_version": data_version(split_file, dataset_path),
        "metrics": "",
        "log_path": _cell(log_path),
        "status": "running",
        "notes": _cell(notes),
    }
    handle = RunHandle(row, csv_path)
    try:
        with _Lock(csv_path):
            new_file = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0
            with open(csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=COLUMNS)
                if new_file:
                    writer.writeheader()
                writer.writerow(row)
    except Exception as exc:
        _warn(f"не удалось записать начало запуска в {csv_path}: {exc!r}")
    return handle


class tracked_run:
    """Контекст: running при входе; ok при нормальном выходе; failed / interrupted при исключении."""

    def __init__(self, script, **kwargs):
        self.script, self.kwargs = script, kwargs

    def __enter__(self) -> RunHandle:
        self.handle = start_run(self.script, **self.kwargs)
        return self.handle

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.handle.finish("ok")
        elif issubclass(exc_type, KeyboardInterrupt):
            self.handle.finish("interrupted", notes="Ctrl+C")
        else:
            self.handle.finish("failed", notes=repr(exc))
        return False


def log_run(script, params=None, seed=None, split_file="", metrics=None, log_path="",
            status="ok", notes="", dataset_path: str = DATASET_CSV,
            csv_path: str = EXPERIMENTS_CSV) -> None:
    """Разовая запись уже завершённого запуска (для ручного дополнения журнала)."""
    handle = start_run(script, params=params, seed=seed, split_file=split_file,
                       log_path=log_path, notes=notes, dataset_path=dataset_path, csv_path=csv_path)
    handle.finish(status, metrics=metrics)
