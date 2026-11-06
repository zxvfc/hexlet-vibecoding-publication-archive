#!/usr/bin/env python3
"""Отправляет подборку публикаций в Telegram (HTML-разметка, разбиение по лимиту)."""
import argparse
import html
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

TG_LIMIT = 4096


def shorten(text, limit):
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


def format_paper(n, p, desc_limit):
    e = html.escape
    title = p.get("title_ru") or p.get("title") or p.get("id", "")
    desc = shorten(p.get("desc_ru") or p.get("abstract") or "", desc_limit)
    meta = " · ".join(x for x in (p.get("category"), p.get("published")) if x)
    lines = [f'<b>{n}. <a href="{e(p["url"], quote=True)}">{e(title)}</a></b>']
    if meta:
        lines.append(f"<i>{e(meta)}</i>")
    if desc:
        lines.append(e(desc))
    return "\n".join(lines)


def build_messages(papers, header, desc_limit):
    if not papers:
        return [f"<b>{html.escape(header)}</b>\n\nНовых публикаций нет."]
    blocks = [format_paper(i, p, desc_limit) for i, p in enumerate(papers, 1)]
    messages, cur = [], f"<b>{html.escape(header)}</b> ({len(papers)})"
    for b in blocks:
        if len(cur) + 2 + len(b) > TG_LIMIT:
            messages.append(cur)
            cur = b
        else:
            cur += "\n\n" + b
    messages.append(cur)
    return messages


def send(token, chat_id, text):
    data = urllib.parse.urlencode({
        "chat_id": chat_id, "text": text,
        "parse_mode": "HTML", "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as err:
        return json.load(err)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", help="JSON-файл с массивом публикаций ('-' для stdin)")
    ap.add_argument("--title", default="Новые публикации")
    ap.add_argument("--desc-limit", type=int, default=300)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    src = sys.stdin if a.file == "-" else open(a.file, encoding="utf-8")
    papers = json.load(src)
    bad = [i for i, p in enumerate(papers) if not p.get("url")]
    if bad:
        sys.exit(f"Ошибка: у записей {bad} нет поля url")

    messages = build_messages(papers, a.title, a.desc_limit)
    if a.dry_run:
        for i, m in enumerate(messages, 1):
            print(f"--- сообщение {i}/{len(messages)} ({len(m)} симв.)\n{m}\n")
        return

    token, chat = os.environ.get("TG_BOT_TOKEN"), os.environ.get("CHAT_ID")
    missing = [n for n, v in (("TG_BOT_TOKEN", token), ("CHAT_ID", chat)) if not v]
    if missing:
        sys.exit(f"Ошибка: не заданы переменные окружения: {', '.join(missing)}")

    for i, m in enumerate(messages, 1):
        res = send(token, chat, m)
        if not res.get("ok"):
            sys.exit(f"Ошибка Telegram на сообщении {i}/{len(messages)}: {res.get('description')}")
    print(f"Отправлено: {len(papers)} публикаций, {len(messages)} сообщений")


if __name__ == "__main__":
    main()
