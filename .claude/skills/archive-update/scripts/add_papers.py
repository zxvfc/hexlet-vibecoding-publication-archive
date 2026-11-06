#!/usr/bin/env python3
"""Добавляет новые публикации в data/publications.json и обновляет data/stats.json."""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

FIELDS = ("id", "url", "title_ru", "published", "desc_ru", "category")
REQUIRED = ("id", "url", "title_ru", "category")
DATE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump(path, data):
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def norm(s):
    return " ".join(str(s).lower().split())


def clean(p):
    rec = {k: str(p.get(k) or "").strip() for k in FIELDS}
    rec["id"] = re.sub(r"v\d+$", "", rec["id"])
    if not rec["url"] and rec["id"]:
        rec["url"] = f"https://arxiv.org/abs/{rec['id']}"
    if not rec["desc_ru"]:
        rec["desc_ru"] = str(p.get("summary") or "").strip()
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", help="JSON-файл с массивом новых публикаций ('-' для stdin)")
    ap.add_argument("--data-dir", default="data", help="папка с данными архива")
    ap.add_argument("--dry-run", action="store_true", help="только проверить, ничего не записывать")
    a = ap.parse_args()

    data_dir = Path(a.data_dir)
    pubs_path, stats_path, topics_path = (data_dir / n for n in ("publications.json", "stats.json", "topics.json"))

    new = json.load(sys.stdin) if a.file == "-" else load(a.file)
    if not isinstance(new, list):
        sys.exit("Ошибка: на входе должен быть JSON-массив")

    pubs = load(pubs_path)
    stats = load(stats_path)
    topics = {norm(t): t for t in load(topics_path)}
    known = {p.get("id") for p in pubs}

    added, dupes, errors = [], [], []
    for i, p in enumerate(new):
        if not isinstance(p, dict):
            errors.append(f"#{i}: запись не объект")
            continue
        rec = clean(p)
        missing = [k for k in REQUIRED if not rec[k]]
        if missing:
            errors.append(f"#{i} ({rec['id'] or '?'}): нет полей {', '.join(missing)}")
            continue
        if rec["published"] and not DATE_RE.match(rec["published"]):
            errors.append(f"#{i} ({rec['id']}): published «{rec['published']}» не в формате ДД.ММ.ГГГГ")
            continue
        if norm(rec["category"]) not in topics:
            errors.append(f"#{i} ({rec['id']}): категории «{rec['category']}» нет в {topics_path}")
            continue
        rec["category"] = topics[norm(rec["category"])]
        if rec["id"] in known:
            dupes.append(rec["id"])
            continue
        known.add(rec["id"])
        added.append(rec)

    print(f"Новых: {len(added)}, дубликатов: {len(dupes)}, ошибок: {len(errors)}")
    for rec in added:
        print(f"  + {rec['id']}  [{rec['category']}]  {rec['title_ru']}")
    for d in dupes:
        print(f"  = {d} уже в архиве")
    for e in errors:
        print(f"  ! {e}")
    if errors:
        sys.exit("Ошибка: исправьте записи, ничего не записано")
    if a.dry_run:
        print("Проверка: ничего не записано")
        return

    stats["scans"] = int(stats.get("scans") or 0) + 1
    stats["lastScan"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dump(pubs_path, pubs + added)
    dump(stats_path, stats)
    print(f"Записано: {pubs_path} (+{len(added)}), {stats_path} (scans={stats['scans']}, lastScan={stats['lastScan']})")


if __name__ == "__main__":
    main()
