"""Small local RAG index with source citations; no embeddings service required."""

import re
import sqlite3
from pathlib import Path

from .core import ForgeError


def index_docs(source, database):
    root = Path(source).resolve()
    paths = sorted(root.rglob("*.md"))
    if not paths:
        raise ForgeError("No Markdown documents found")
    Path(database).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as db:
        db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(source, body)")
        db.execute("DELETE FROM chunks")
        count = 0
        for path in paths:
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                continue
            if path.stat().st_size > 1_000_000:
                continue
            body = path.read_text(encoding="utf-8")
            for offset in range(0, len(body), 1600):
                db.execute(
                    "INSERT INTO chunks VALUES (?, ?)",
                    (f"{path.relative_to(root)}#char-{offset}", body[offset : offset + 1800]),
                )
                count += 1
    return count


def search(database, query, limit=4):
    if not Path(database).is_file():
        return []
    words = re.findall(r"[a-zA-Z0-9_]{3,}", query)[:24]
    if not words:
        return []
    expression = " OR ".join('"' + word + '"' for word in words)
    with sqlite3.connect(f"file:{Path(database).resolve()}?mode=ro", uri=True) as db:
        rows = db.execute(
            "SELECT source, body FROM chunks WHERE chunks MATCH ? ORDER BY bm25(chunks) LIMIT ?",
            (expression, limit),
        ).fetchall()
    return [{"source": source, "text": body} for source, body in rows]
