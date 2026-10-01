import pytest

from agent import lint


@pytest.mark.parametrize("phrase", lint.load_phrases())
@pytest.mark.parametrize("case", [str.lower, str.upper, str.title])
def test_every_banned_phrase_is_flagged_in_any_case(phrase, case):
    letter = f"Dear Hiring Manager,\n\nHonestly, {case(phrase)} is how I'd put it.\n\nThanks,\nJordan"
    hits = [h for h in lint.lint(letter) if h.kind == "phrase"]
    assert len(hits) == 1
    assert hits[0].text.lower() == phrase.lower()


def test_word_forms_and_curly_apostrophes():
    hits = lint.lint("We leveraged data. In today’s market, I delved in.")
    assert sorted(h.text for h in hits) == ["In today’s", "delve", "leverage"]


def test_no_false_positive_inside_words():
    assert lint.lint("My unthrilled cat sat on a mat.", phrases=["thrilled"]) == []


def test_em_dash_limit():
    assert lint.lint("One — fine.", phrases=[]) == []
    hits = lint.lint("One — two — three.", phrases=[])
    assert [h.kind for h in hits] == ["em_dash"] and "2 em dashes" in hits[0].message


def test_generic_opener():
    hits = lint.lint("Dear Hiring Manager,\n\nI am writing to express my interest in the role.", phrases=[])
    assert [h.kind for h in hits] == ["opener"]


def test_phrase_list_round_trip(tmp_path):
    path = tmp_path / "banned.txt"
    lint.save_phrases(["thrilled", "  synergy ", "", "thrilled"], path)
    assert lint.load_phrases(path) == ["thrilled", "synergy"]
    assert path.read_text(encoding="utf-8").startswith("# One phrase per line")


def test_starting_list_matches_spec():
    assert lint.load_phrases() == [
        "thrilled", "passionate about", "leverage", "delve", "fast-paced environment",
        "proven track record", "I am confident that", "aligns perfectly", "tapestry", "in today's",
    ]
