import math

import pytest

from harfix.model import CharLM, default_models
from harfix.normalize import ALPHABET


@pytest.fixture
def tiny_model() -> CharLM:
    return CharLM.train(["كتب الولد الدرس", "قرأ الطالب الكتاب"], order=3)


@pytest.mark.parametrize("history", ["", " ك", "كت", "زظ", "  "])
def test_probabilities_form_a_distribution_for_any_history(tiny_model, history):
    total = sum(tiny_model.prob(ch, history) for ch in ALPHABET)
    assert math.isclose(total, 1.0, rel_tol=1e-9)


def test_seen_text_is_less_surprising_than_shuffled_text(tiny_model):
    seen, _ = tiny_model.bits_per_char("الولد الكتاب")
    shuffled, _ = tiny_model.bits_per_char("دلولا باتكلا")
    assert seen < shuffled


def test_save_load_round_trip_is_reproducible(tiny_model, tmp_path):
    first, second = tmp_path / "a.json.gz", tmp_path / "b.json.gz"
    tiny_model.save(first)
    CharLM.load(first).save(second)
    assert first.read_bytes() == second.read_bytes()
    assert CharLM.load(first).prob("ب", "تا") == tiny_model.prob("ب", "تا")


def test_packaged_models_load():
    models = default_models()
    assert models.spaced.order == models.unspaced.order == 4
