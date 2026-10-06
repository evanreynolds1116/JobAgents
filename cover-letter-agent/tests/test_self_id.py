"""Self-identification answers for demographic and EEO questions: stored locally, never sent
to Claude, matched to a form's options by code, and left for you when nothing matches."""

import pytest

from apply import extract, fill, mapping, self_id
from apply.extract import Field
from storage import self_id as store
from storage.self_id import DECLINE, SelfId
from tests.apply_browser import chrome, open_form, page  # noqa: F401 - pytest fixtures
from tests.fixtures.forms import posting_pages
from tests.test_apply_browser import LabelClient
from tests.test_apply_rules import proposal, sources

# Option wordings as real forms use them.
GH_GENDER = ["Male", "Female", "Decline To Self Identify"]
GH_HISPANIC = ["Yes", "No", "Decline To Self Identify"]
GH_RACE = ["American Indian or Alaskan Native", "Asian", "Black or African American",
           "Hispanic or Latino", "White", "Native Hawaiian or Other Pacific Islander", "Two or More Races",
           "Decline To Self Identify"]
OFCCP_VETERAN = ["I am not a protected veteran",
                 "I identify as one or more of the classifications of protected veteran", "I don't wish to answer"]
LEVER_VETERAN = ["I am a veteran", "I am not a veteran", "Decline to self-identify"]
OFCCP_DISABILITY = ["Yes, I have a disability (or previously had a disability)",
                    "No, I do not have a disability and have not had one in the past", "I do not want to answer"]
DESCRIBED_RACE = ["White - A person having origins in any of the original peoples of Europe, the Middle East, "
                  "or North Africa", "Black or African American - A person having origins in any of the black "
                  "racial groups of Africa", "Middle Eastern or North African", "I prefer not to say"]
ORIENTATION = ["Asexual", "Bisexual", "Gay", "Heterosexual", "Lesbian", "Queer", "I prefer not to answer"]


def test_round_trip_and_bad_values(app_paths):
    assert store.load() == SelfId()
    store.save(SelfId(gender="Woman", veteran="Not a veteran", pronouns=" she/her "))
    assert store.load() == SelfId(gender="Woman", veteran="Not a veteran", pronouns="she/her")
    store.path().write_text("gender: Martian\ndisability: false\n", encoding="utf-8")
    assert store.load() == SelfId(disability="No")


@pytest.mark.parametrize("label, name", [
    ("Gender", "gender"), ("Sex", "gender"), ("Gender identity", "gender"),
    ("Do you identify as transgender?", "transgender"), ("Sexual Orientation", "sexual_orientation"),
    ("Share your Pronouns", "pronouns"), ("Race", "race"), ("Race/Ethnicity", "race"),
    ("Are you Hispanic/Latino?", "hispanic_latino"), ("Ethnicity", "race"), ("Veteran Status", "veteran"),
    ("Protected veteran status", "veteran"), ("Disability Status", "disability"),
    ("Date of birth", None), ("Marital status", None), ("Religion", None),
])
def test_category(label, name):
    assert self_id.category(label) == name


@pytest.mark.parametrize("name, answer, options, expected", [
    ("gender", "Man", GH_GENDER, "Male"),
    ("gender", "Woman", GH_GENDER, "Female"),
    ("gender", DECLINE, GH_GENDER, "Decline To Self Identify"),
    ("gender", "Non-binary", GH_GENDER, None),                     # not offered: left for you
    ("gender", "Non-binary", ["Man", "Woman", "Non-binary", "Prefer not to say"], "Non-binary"),
    ("hispanic_latino", "No", GH_HISPANIC, "No"),
    ("race", "White", GH_RACE, "White"),
    ("race", "Two or more races", GH_RACE, "Two or More Races"),
    ("race", "Middle Eastern or North African", DESCRIBED_RACE, "Middle Eastern or North African"),
    ("race", "White", DESCRIBED_RACE, DESCRIBED_RACE[0]),
    ("race", "Hispanic or Latino", ["White (Not Hispanic or Latino)", "Hispanic or Latino"], "Hispanic or Latino"),
    ("veteran", "Not a veteran", OFCCP_VETERAN, OFCCP_VETERAN[0]),
    ("veteran", "Veteran, not protected", OFCCP_VETERAN, OFCCP_VETERAN[0]),
    ("veteran", "Protected veteran", OFCCP_VETERAN, OFCCP_VETERAN[1]),
    ("veteran", "Not a veteran", LEVER_VETERAN, "I am not a veteran"),
    ("veteran", "Protected veteran", LEVER_VETERAN, "I am a veteran"),
    ("veteran", DECLINE, OFCCP_VETERAN, "I don't wish to answer"),
    ("disability", "No", OFCCP_DISABILITY, OFCCP_DISABILITY[1]),
    ("disability", "Yes", OFCCP_DISABILITY, OFCCP_DISABILITY[0]),
    ("disability", DECLINE, OFCCP_DISABILITY, OFCCP_DISABILITY[2]),
    ("transgender", "No", ["Yes", "No", "I prefer not to answer"], "No"),
    ("sexual_orientation", "Heterosexual or straight", ORIENTATION, "Heterosexual"),
    ("sexual_orientation", "Gay", ORIENTATION, "Gay"),
    ("sexual_orientation", "Gay", ["Gay or Lesbian", "Straight", "Decline"], "Gay or Lesbian"),
    ("sexual_orientation", DECLINE, ORIENTATION, "I prefer not to answer"),
])
def test_pick(name, answer, options, expected):
    assert self_id.pick(name, answer, options) == expected


def test_yes_no_veteran_question_reads_the_label():
    assert self_id.pick("veteran", "Not a veteran", ["Yes", "No"], "Are you a protected veteran?") == "No"
    assert self_id.pick("veteran", "Veteran, not protected", ["Yes", "No"], "Are you a protected veteran?") == "No"
    assert self_id.pick("veteran", "Veteran, not protected", ["Yes", "No"], "Are you a veteran?") == "Yes"


def test_hispanic_only_ethnicity_uses_the_hispanic_answer():
    options = ["Hispanic or Latino", "Not Hispanic or Latino", "Decline to self-identify"]
    assert self_id.pick("race", "White", options, hispanic="No") == "Not Hispanic or Latino"
    assert self_id.pick("race", "White", options) is None  # Hispanic answer not set
    assert self_id.pick("race", "Hispanic or Latino", options) == "Hispanic or Latino"


def test_answer_rules():
    answers = SelfId(gender="Woman", race="Asian", pronouns="she/her")
    assert self_id.answer(Field("f", "select", "Gender", options=GH_GENDER), answers) == ("Female", "")
    multi = Field("f", "checkbox_group", "Race (select all that apply)", options=GH_RACE, multiple=True)
    assert self_id.answer(multi, answers) == (["Asian"], "")
    assert self_id.answer(Field("f", "text", "Pronouns"), answers) == ("she/her", "")
    pronoun_list = Field("f", "select", "Pronouns", options=["He/him/his", "She/her/hers", "They/them/theirs"])
    assert self_id.answer(pronoun_list, answers) == ("She/her/hers", "")
    value, note = self_id.answer(Field("f", "text", "Gender (please describe)"), answers)
    assert value is None and "list of options" in note  # free text other than pronouns is left
    value, note = self_id.answer(Field("f", "select", "Veteran Status", options=OFCCP_VETERAN), answers)
    assert value is None and "Not set" in note
    value, note = self_id.answer(Field("f", "select", "Date of birth", options=["1990"]), answers)
    assert value is None


def test_decide_fills_from_self_id_and_still_leaves_attestations():
    src = sources(self_id=SelfId(gender="Man", veteran="Not a veteran"))
    gender = Field("f1", "combobox", "Gender", options=GH_GENDER)
    d = mapping.decide(gender, proposal("Female", "profile"), src)  # a stray proposal is ignored
    assert (d.action, d.value, d.source, d.confident) == ("fill", "Male", "self_id", True)
    d = mapping.decide(Field("f2", "select", "Disability Status", options=OFCCP_DISABILITY), None, src)
    assert (d.action, d.status) == ("leave", "left_for_you") and "Not set" in d.note
    attest = Field("f3", "radio", "I certify my veteran status is true", options=["Yes", "No"])
    assert mapping.decide(attest, None, src).status == "left_for_you"


def test_self_id_never_reaches_claude():
    src = sources(self_id=SelfId(gender="Woman", race="Asian", veteran="Protected veteran"))
    assert "Asian" not in str(src.blocks()) and "Protected veteran" not in str(src.blocks())
    client = LabelClient({"First Name": ("Jordan", "profile")})
    fields = [Field("f1", "text", "First Name"), Field("f2", "select", "Gender", options=GH_GENDER),
              Field("f3", "select", "Race", options=GH_RACE)]
    decisions = mapping.map_fields(client, "claude-test", fields, src)
    sent = client.requests[0]["messages"][0]["content"]
    assert "Gender" not in sent and "Race" not in sent and "Asian" not in sent and "Woman" not in sent
    assert [d.value for d in decisions] == ["Jordan", "Female", "Asian"]


def test_fills_demographic_dropdowns_in_chrome(page):
    open_form(page, posting_pages.GREENHOUSE_FORM)
    fields = extract.read_fields(page)
    src = sources(self_id=SelfId(gender="Woman", veteran="Not a veteran", pronouns="she/her"))
    decisions = mapping.map_fields(LabelClient({}), "claude-test", fields, src)
    decisions = fill.fill_page(page, fields, decisions, {"resume": None, "cover_letter": None})
    now = {f.label: f.value for f in extract.read_fields(page, open_dropdowns=False)}
    assert now["Gender"] == "Female" and now["Veteran Status"] == "I am not a veteran"
    status = {f.label: d.status for f, d in zip(fields, decisions)}
    assert status["Gender"] == "filled" and status["Veteran Status"] == "filled"
    assert not now.get("I certify that the information I have provided is true and complete.")
    assert page.evaluate("window.__submitted") is None
