"""flow 結果資料夾名稱 → 原始 yaml 路徑 / tags（generate_report.py、_summarize_results.py 共用）。

Maestro 的結果資料夾名稱 = flow 的 `name:`；沒有 `name:` 時 = 檔名（不含副檔名）。兩種都建索引，
避免沒有 name 的 flow 找不到路徑（找不到路徑時重跑會漏掉 → 假綠）。
tags 支援區塊寫法（`tags:` 換行 `- a`）與行內寫法（`tags: [a, b]`）。
"""
from pathlib import Path


def _parse_header(text: str):
    header = text.split("\n---", 1)[0] if "\n---" in text else ""
    try:
        import yaml  # pyyaml（requirements.txt）
        data = yaml.safe_load(header) or {}
        if isinstance(data, dict):
            tags = data.get("tags") or []
            return data.get("name"), [str(t) for t in (tags if isinstance(tags, list) else [tags])]
    except Exception:
        pass
    name, tags, in_tags = None, [], False
    for line in header.splitlines():
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip().strip('"\''); in_tags = False
        elif line.startswith("tags:"):
            rest = line.split(":", 1)[1].strip()
            if rest.startswith("["):
                tags += [t.strip().strip('"\'') for t in rest.strip("[]").split(",") if t.strip()]
            else:
                in_tags = True
        elif in_tags and line.strip().startswith("-"):
            tags.append(line.strip().lstrip("-").strip().strip('"\''))
        else:
            in_tags = False
    return name, tags


def build_flow_index(root: Path) -> dict:
    index = {}
    for y in root.glob("flows/**/*.yaml"):
        name, tags = _parse_header(y.read_text(encoding="utf-8", errors="ignore"))
        entry = {"path": str(y.relative_to(root)), "tags": tags}
        index.setdefault(y.stem, entry)
        if name:
            index[str(name)] = entry
    return index
