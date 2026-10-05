"""Answers filled into application forms (spec: Data & storage, filled_answers): every
field's final value, including your edits, kept on the application's record."""

import json

from storage.db import connect


def save_page(app_id: int, page: int, rows: list[dict]) -> None:
    """Replace what's recorded for one page of the form. Each row has label, value,
    source and status."""
    with connect() as conn:
        conn.execute("DELETE FROM filled_answers WHERE application_id = ? AND page = ?", (app_id, page))
        conn.executemany(
            "INSERT INTO filled_answers (application_id, page, field_label, value, source, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(app_id, page, r["label"], json.dumps(r["value"]) if isinstance(r["value"], list) else r["value"],
              r["source"], r["status"]) for r in rows])
    conn.close()


def for_application(app_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM filled_answers WHERE application_id = ? ORDER BY page, id",
                            (app_id,)).fetchall()
    conn.close()
    out = []
    for r in rows:
        row = dict(r)
        if row["value"] and row["value"].startswith("["):
            try:
                row["value"] = ", ".join(json.loads(row["value"]))
            except ValueError:
                pass
        out.append(row)
    return out
