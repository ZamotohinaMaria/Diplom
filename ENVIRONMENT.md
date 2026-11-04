# Окружение

Собрано `experiments/collect_env.py` 04.11.2026. На этом окружении получены результаты в `derived/` (см. журнал `EXPERIMENTS.csv`).

| Что | Версия |
|---|---|
| ОС | Windows 10 (10.0.19045) |
| Архитектура | AMD64 |
| Python | 3.13.5 |
| Интерпретатор | `C:\Users\Marishka\anaconda3\python.exe` |
| Окружение conda | — |
| `numpy` | 2.1.3 |
| `pandas` | 2.2.3 |
| `scikit-learn` | 1.6.1 |
| `scipy` | 1.15.3 |
| `torch` | 2.7.1+cu118 |
| `torch-geometric` | 2.7.0 |
| `tabulate` | 0.9.0 |
| PyTorch собран с CUDA | 11.8 |
| cuDNN | 90100 |
| CUDA доступна | да |
| Видеокарта | NVIDIA GeForce RTX 3070 Ti Laptop GPU |

## Как воспроизвести

1. Python той же версии (лучше отдельное окружение conda или venv).
2. PyTorch и torch_geometric ставятся отдельно, под свою CUDA или CPU — по инструкциям pytorch.org и pytorch-geometric.readthedocs.io; версии — из таблицы выше.
3. Остальное: `pip install -r requirements.txt`.
4. Команды запуска в порядке пайплайна — [experiments/COMMANDS.md](experiments/COMMANDS.md).

`requirements.txt` — только библиотеки, которые импортируют скрипты; `requirements-freeze.txt` — все пакеты окружения (для точной сверки, ставить целиком не обязательно).

Замечание: GINE на GPU недетерминирован (результат при одном seed может отличаться между запусками); на CPU (`--device cpu`) повторяется точно. Пилот C считался на CPU, протоколы A/B — на GPU.
