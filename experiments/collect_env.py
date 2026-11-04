"""Пункт 4 (неделя 2–8.11.2026). Окружение и карта скриптов — для воспроизводимости.

1. Окружение: ОС, Python, версии библиотек, которые используют скрипты experiments/ и GINE,
   сборка PyTorch (CUDA, cuDNN), видеокарта.
2. Карта скриптов experiments/: собирается из docstring каждого скрипта (первая строка — что делает,
   блок «Результаты» — что пишет, блок «Запуск из корня репозитория» — команды), в порядке пайплайна.
   Поэтому карта не расходится с кодом: при изменении скрипта достаточно перезапустить collect_env.py.

Модели не обучаются, данные не читаются.

Результаты:
  ENVIRONMENT.md            окружение: таблица версий и как воспроизвести
  requirements.txt          точные версии библиотек, которые импортируют скрипты
  requirements-freeze.txt   все установленные пакеты (name==version)
  experiments/COMMANDS.md   карта скриптов experiments/: порядок, назначение, команды, результаты

Запуск из корня репозитория:
  python experiments/collect_env.py
"""
import ast
import os
import platform
import re
import sys
from datetime import date
from importlib import metadata

from log_run import ROOT, tracked_run

# библиотеки, которые импортируют скрипты experiments/ и my-GINE-model upgrade 1 (import-имя -> имя пакета)
PACKAGES = [("numpy", "numpy"), ("pandas", "pandas"), ("sklearn", "scikit-learn"), ("scipy", "scipy"),
            ("torch", "torch"), ("torch_geometric", "torch-geometric"),
            ("tabulate", "tabulate")]   # tabulate нужен pandas.to_markdown в h1_table.py и pilot_c_table.py

# порядок пайплайна: (скрипт, этап). Скрипты, которых здесь нет, попадут в конец карты с пометкой
PIPELINE = [
    ("audit_duplicates.py", "Неделя 1, задача 1 — аудит дублей"),
    ("leak_check.py", "Неделя 1, задача 2 — утечка в схеме НИРС"),
    ("make_splits.py", "Неделя 1, задача 3 — разбиения A и B"),
    ("baseline_tfidf.py", "Неделя 1, задача 4 — TF-IDF + LogReg на A/B; неделя 2 — пилот C"),
    ("run_gine_splits.py", "Неделя 1, задача 4 — GINE на A/B; неделя 2 — пилот C"),
    ("h1_table.py", "Неделя 1, задача 4 — итог H1"),
    ("make_split_c.py", "Неделя 2, пункт 2 — разбиение C"),
    ("pilot_c_table.py", "Неделя 2, пункт 3 — итог пилота C"),
    ("collect_env.py", "Неделя 2, пункт 4 — окружение и карта скриптов"),
    ("log_run.py", "Модуль журнала EXPERIMENTS.csv"),
    ("eval_utils.py", "Общие функции оценки"),
]


def parse_args():
    import argparse
    p = argparse.ArgumentParser(description="Окружение и карта скриптов")
    p.add_argument("--out-dir", default=ROOT, help="куда писать ENVIRONMENT.md и requirements*.txt")
    p.add_argument("--commands", default=os.path.join(ROOT, "experiments", "COMMANDS.md"))
    return p.parse_args()


# ---------- окружение ----------

def package_version(dist: str) -> str:
    try:
        return metadata.version(dist)
    except metadata.PackageNotFoundError:
        return "не установлен"


def torch_info() -> dict:
    """Сборка PyTorch и видеокарта; если torch не установлен — пустой словарь."""
    try:
        import torch
    except ImportError:
        return {}
    info = {"torch_cuda_build": torch.version.cuda or "CPU-сборка",
            "cudnn": str(torch.backends.cudnn.version()) if torch.backends.cudnn.is_available() else "нет",
            "cuda_available": torch.cuda.is_available()}
    info["gpu"] = ", ".join(torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())) or "нет"
    return info


def environment() -> dict:
    return {
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "machine": platform.machine(),
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "conda_env": os.environ.get("CONDA_DEFAULT_ENV", "—"),
        "packages": {dist: package_version(dist) for _, dist in PACKAGES},
        **torch_info(),
    }


def freeze() -> list:
    """Все установленные пакеты name==version, по алфавиту (без вызова pip — работает и в conda)."""
    seen = {}
    for d in metadata.distributions():
        name = d.metadata["Name"]
        if name and name.lower() not in seen:
            seen[name.lower()] = f"{name}=={d.version}"
    return [seen[k] for k in sorted(seen)]


def environment_md(env: dict) -> str:
    rows = [("ОС", env["os"]), ("Архитектура", env["machine"]), ("Python", env["python"]),
            ("Интерпретатор", f"`{env['python_executable']}`"), ("Окружение conda", env["conda_env"])]
    rows += [(f"`{dist}`", ver) for dist, ver in env["packages"].items()]
    if "torch_cuda_build" in env:
        rows += [("PyTorch собран с CUDA", env["torch_cuda_build"]), ("cuDNN", env["cudnn"]),
                 ("CUDA доступна", "да" if env["cuda_available"] else "нет"), ("Видеокарта", env["gpu"])]
    table = "\n".join(f"| {k} | {v} |" for k, v in rows)
    return "\n".join([
        "# Окружение",
        "",
        f"Собрано `experiments/collect_env.py` {date.today():%d.%m.%Y}. На этом окружении получены результаты "
        "в `derived/` (см. журнал `EXPERIMENTS.csv`).",
        "",
        "| Что | Версия |",
        "|---|---|",
        table,
        "",
        "## Как воспроизвести",
        "",
        "1. Python той же версии (лучше отдельное окружение conda или venv).",
        "2. PyTorch и torch_geometric ставятся отдельно, под свою CUDA или CPU — по инструкциям "
        "pytorch.org и pytorch-geometric.readthedocs.io; версии — из таблицы выше.",
        "3. Остальное: `pip install -r requirements.txt`.",
        "4. Команды запуска в порядке пайплайна — [experiments/COMMANDS.md](experiments/COMMANDS.md).",
        "",
        "`requirements.txt` — только библиотеки, которые импортируют скрипты; `requirements-freeze.txt` — "
        "все пакеты окружения (для точной сверки, ставить целиком не обязательно).",
        "",
        "Замечание: GINE на GPU недетерминирован (результат при одном seed может отличаться между запусками); "
        "на CPU (`--device cpu`) повторяется точно. Пилот C считался на CPU, протоколы A/B — на GPU.",
    ])


def requirements_txt(env: dict) -> str:
    lines = ["# Библиотеки, которые импортируют experiments/ и my-GINE-model upgrade 1 (точные версии).",
             "# torch и torch-geometric ставить под свою CUDA/CPU по инструкциям проектов, см. ENVIRONMENT.md.",
             "# Создано experiments/collect_env.py"]
    for dist, ver in env["packages"].items():
        lines.append(f"{dist}=={ver}" if ver != "не установлен" else f"# {dist} — не установлен")
    return "\n".join(lines)


# ---------- карта скриптов ----------

RESULT_PREFIXES = ("derived/", "experiments/", "ENVIRONMENT.md", "requirements")


def docstring_sections(path: str) -> dict:
    """Первая строка docstring, команды (строки «python …») и результаты — строки с отступом,
    начинающиеся с пути к файлу; текст после двух и более пробелов — описание файла."""
    with open(path, encoding="utf-8") as f:
        doc = ast.get_docstring(ast.parse(f.read())) or ""
    lines = doc.splitlines()
    out = {"title": lines[0].strip() if lines else "", "results": [], "commands": []}
    for line in lines[1:]:
        s = line.strip()
        if not line.startswith(" "):
            continue
        if s.startswith("python "):
            out["commands"].append(s)
        elif s.startswith(RESULT_PREFIXES):
            file_part, desc = (re.split(r"\s{2,}", s, maxsplit=1) + [""])[:2]
            # несколько путей через «, » в одной строке (запятые внутри {A,B} без пробела не делят)
            for f in file_part.rstrip(",").split(", "):
                out["results"].append((f, desc.strip()))
    return out


def commands_md() -> str:
    exp_dir = os.path.join(ROOT, "experiments")
    present = sorted(f for f in os.listdir(exp_dir) if f.endswith(".py"))
    known = [s for s, _ in PIPELINE]
    order = [(s, stage) for s, stage in PIPELINE if s in present]
    order += [(s, "не внесён в порядок пайплайна (collect_env.py, PIPELINE)") for s in present if s not in known]

    parts = [
        "# Карта скриптов experiments/",
        "",
        f"Собрано `experiments/collect_env.py` {date.today():%d.%m.%Y} из docstring скриптов — "
        "при изменении скриптов перезапустить. Все команды — из корня репозитория. "
        "Каждый запуск записывается в `EXPERIMENTS.csv`.",
        "",
        "## Порядок запуска",
        "",
        "| № | Скрипт | Этап | Что делает |",
        "|---|---|---|---|",
    ]
    info = {s: docstring_sections(os.path.join(exp_dir, s)) for s, _ in order}
    for i, (s, stage) in enumerate(order, 1):
        parts.append(f"| {i} | [{s}]({s}) | {stage} | {info[s]['title']} |")
    for s, stage in order:
        d = info[s]
        parts += ["", f"## {s}", "", d["title"], ""]
        if d["commands"]:
            parts += ["```", *d["commands"], "```"]
        else:
            parts.append("Модуль, сам не запускается: его импортируют другие скрипты.")
        if d["results"]:
            parts += ["", "Результаты:", ""]
            parts += [f"- `{f}`" + (f" — {desc}" if desc else "") for f, desc in d["results"]]
    return "\n".join(parts)


def write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n")


def main():
    args = parse_args()
    env_md = os.path.join(args.out_dir, "ENVIRONMENT.md")
    with tracked_run("collect_env.py", params={"out_dir": os.path.relpath(args.out_dir, ROOT)},
                     log_path=env_md) as run:
        env = environment()
        write(env_md, environment_md(env))
        write(os.path.join(args.out_dir, "requirements.txt"), requirements_txt(env))
        frozen = freeze()
        write(os.path.join(args.out_dir, "requirements-freeze.txt"), "\n".join(frozen))
        write(args.commands, commands_md())

        print(environment_md(env).split("## Как воспроизвести")[0].rstrip())
        print(f"\nПакетов в окружении: {len(frozen)}")
        print("Сохранено: ENVIRONMENT.md, requirements.txt, requirements-freeze.txt, "
              f"{os.path.relpath(args.commands, ROOT)}")
        run.set(metrics={"python": env["python"], **env["packages"],
                         "torch_cuda_build": env.get("torch_cuda_build"), "gpu": env.get("gpu")},
                notes=f"{len(frozen)} пакетов в requirements-freeze.txt")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore  (метод есть у консоли, Pylance его не знает)
    main()
