"""Экспорт всех чатов Claude Code для этой папки в Markdown.

Запуск:
    python "0 - docs/export_chats.py"            # только текст диалога
    python "0 - docs/export_chats.py" --tools    # + строки с вызовами инструментов

Результат: 0 - docs/chats/<дата>_<название>.md (по одному файлу на сессию).
"""
import argparse
import json
import re
from pathlib import Path

SRC = Path.home() / ".claude" / "projects" / "c--Users-Marishka-Desktop-code-Diplom"
OUT = Path(__file__).resolve().parent / "chats"

# служебные вставки, которые не нужны в экспорте
NOISE = re.compile(
    r"<(system-reminder|ide_opened_file|ide_selection|command-message|"
    r"local-command-stdout|local-command-caveat)>.*?</\1>",
    re.S,
)


def clean(text: str) -> str:
    return NOISE.sub("", text).strip()


def blocks(content):
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return content or []


def tool_line(b) -> str:
    inp = b.get("input", {}) or {}
    hint = (inp.get("description") or inp.get("file_path") or inp.get("pattern")
            or inp.get("command") or "")
    hint = str(hint).replace("\n", " ")[:120]
    return f"> 🔧 `{b.get('name')}` {hint}".rstrip()


def export(path: Path, with_tools: bool):
    title, msgs, first_ts = None, [], None
    for line in path.open(encoding="utf-8"):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = d.get("type")
        if t == "ai-title":
            title = d.get("aiTitle") or d.get("title") or title
            continue
        if t not in ("user", "assistant") or d.get("isSidechain") or d.get("isMeta"):
            continue
        first_ts = first_ts or d.get("timestamp")
        parts = []
        for b in blocks(d.get("message", {}).get("content")):
            bt = b.get("type")
            if bt == "text":
                txt = clean(b.get("text", ""))
                if txt:
                    parts.append(txt)
            elif bt == "tool_use" and with_tools:
                parts.append(tool_line(b))
            # thinking и tool_result пропускаем
        if parts:
            msgs.append((t, d.get("timestamp", ""), "\n\n".join(parts)))

    if not msgs:
        return None
    date = (first_ts or "")[:10] or "unknown"
    title = title or msgs[0][2].splitlines()[0][:60]
    safe = re.sub(r'[\\/:*?"<>|\n]+', " ", title).strip()[:60] or path.stem
    out = OUT / f"{date}_{safe}.md"

    lines = [f"# {title}", "", f"Сессия: `{path.stem}`  ", f"Начало: {first_ts}", ""]
    prev = None
    for role, ts, text in msgs:
        if role != prev:
            who = "👤 Пользователь" if role == "user" else "🤖 Claude"
            lines += ["---", f"### {who}  <sub>{ts[:16].replace('T', ' ')}</sub>", ""]
            prev = role
        lines += [text, ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    return out, len(msgs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools", action="store_true", help="показывать вызовы инструментов")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for f in sorted(SRC.glob("*.jsonl")):
        res = export(f, args.tools)
        if res:
            print(f"{res[0].name}  ({res[1]} сообщений)")
    print(f"\nГотово: {OUT}")


if __name__ == "__main__":
    main()
