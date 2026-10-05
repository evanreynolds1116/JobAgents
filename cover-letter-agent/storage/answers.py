"""Saved answers to past application questions (spec: Data & storage, saved_answers;
Phase 2, Milestone 6).

Each answer is one you approved. The application agent looks up the closest saved
question when a form asks something similar (Milestone 8) and records each reuse.
"""

import re
from datetime import datetime
from difflib import SequenceMatcher

from storage.db import connect

# Words that don't help tell two questions apart.
STOPWORDS = {
    "a", "an", "the", "you", "your", "are", "is", "do", "does", "did", "have", "has", "will", "would", "can",
    "to", "of", "in", "on", "for", "at", "by", "with", "this", "that", "or", "and", "be", "we", "our", "us",
    "please", "if", "any", "what", "which", "how", "currently", "describe",
}
MATCH_THRESHOLD = 0.6


class AnswerError(ValueError):
    """A saved answer couldn't be stored; the message is for you."""


def question_key(question: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", question.lower()).strip()


def _words(question: str) -> set[str]:
    return set(question_key(question).split()) - STOPWORDS


def similarity(a: str, b: str) -> float:
    """0 to 1: the higher of word overlap (ignoring filler words) and character similarity."""
    wa, wb = _words(a), _words(b)
    overlap = len(wa & wb) / len(wa | wb) if wa and wb else 0.0
    return max(overlap, SequenceMatcher(None, question_key(a), question_key(b)).ratio())


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def list_answers() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM saved_answers ORDER BY question COLLATE NOCASE").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count() -> int:
    with connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM saved_answers").fetchone()[0]
    conn.close()
    return n


def save(question: str, answer: str, answer_id: int | None = None) -> int:
    """Add an answer, or update `answer_id`. Saving a question that's already saved
    (ignoring case and punctuation) replaces that answer instead of adding a second one."""
    question, answer = question.strip(), answer.strip()
    if not question or not answer:
        raise AnswerError("Add both the question and your answer.")
    key = question_key(question)
    with connect() as conn:
        clash = conn.execute("SELECT id FROM saved_answers WHERE question_key = ?", (key,)).fetchone()
    conn.close()
    if answer_id and clash and clash["id"] != answer_id:
        raise AnswerError("Another saved answer already has that question.")
    target = answer_id or (clash["id"] if clash else None)
    with connect() as conn:
        if target:
            conn.execute("UPDATE saved_answers SET question = ?, question_key = ?, answer = ?, updated_at = ? "
                         "WHERE id = ?", (question, key, answer, _now(), target))
        else:
            target = conn.execute("INSERT INTO saved_answers (question, question_key, answer) VALUES (?, ?, ?)",
                                  (question, key, answer)).lastrowid
    conn.close()
    return target


def delete(answer_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM saved_answers WHERE id = ?", (answer_id,))
    conn.close()


def find_similar(question: str, limit: int = 3, threshold: float = MATCH_THRESHOLD) -> list[dict]:
    """Saved answers whose question is close to this one, best first, each with a `score`."""
    scored = [{**row, "score": round(similarity(question, row["question"]), 2)} for row in list_answers()]
    matches = [row for row in scored if row["score"] >= threshold]
    return sorted(matches, key=lambda r: (-r["score"], -r["times_used"]))[:limit]


def record_use(answer_id: int) -> None:
    with connect() as conn:
        conn.execute("UPDATE saved_answers SET times_used = times_used + 1, last_used_at = ? WHERE id = ?",
                     (_now(), answer_id))
    conn.close()
