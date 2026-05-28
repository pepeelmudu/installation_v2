# tests/test_mood_machine.py
from mood_machine import (
    AnnoyanceState,
    classify_user_input,
    detect_expression,
    LEVEL_PROMPTS,
    LEVEL_EXPRESSIONS,
    LEVEL_TO_MOOD,
)


def test_initial_state_is_friendly():
    a = AnnoyanceState()
    assert a.points == 0
    assert a.level == 0
    assert a.mood_id == "friendly"


def test_prompt_contains_base_and_level_fragment():
    a = AnnoyanceState()
    prompt = a.get_prompt()
    assert "entidad digital" in prompt
    assert "español" in prompt
    assert LEVEL_PROMPTS[0] in prompt


def test_single_insult_instantly_reaches_enraged():
    a = AnnoyanceState()
    delta, reason = classify_user_input("Eres un gilipollas")
    assert delta == 10
    assert reason == "insulto a la entidad"
    level_change = a.apply(delta, reason)
    assert a.level == 3
    assert level_change == 3
    assert a.mood_id == "hostile"


def test_sexual_also_instantly_enraged():
    a = AnnoyanceState()
    delta, _ = classify_user_input("chuparme la polla")
    assert delta == 10
    a.apply(delta, "sexual")
    assert a.level == 3


def test_apology_drops_one_level_from_max():
    a = AnnoyanceState()
    a.apply(*classify_user_input("Eres tonto"))        # +10 → level 3 (points=10)
    assert a.level == 3
    a.apply(*classify_user_input("Lo siento mucho"))   # -2  → points=8, level 2
    assert a.level == 2


def test_politeness_decrements_from_max():
    a = AnnoyanceState()
    a.apply(*classify_user_input("Eres tonto"))   # +10 → 10
    a.apply(*classify_user_input("Por favor"))    # -1  → 9 (still level 3)
    assert a.points == 9
    assert a.level == 3


def test_points_clamped_to_range():
    a = AnnoyanceState()
    for _ in range(10):
        a.apply(3, "x")
    assert a.points == 10
    for _ in range(20):
        a.apply(-2, "x")
    assert a.points == 0


def test_reset_returns_to_zero():
    a = AnnoyanceState()
    a.apply(5, "x")
    assert a.points > 0
    a.reset()
    assert a.points == 0
    assert a.level == 0


def test_level_to_mood_mapping_covers_all_levels():
    for lvl in range(4):
        assert lvl in LEVEL_TO_MOOD
        assert lvl in LEVEL_PROMPTS
        assert lvl in LEVEL_EXPRESSIONS


def test_neutral_input_no_change():
    a = AnnoyanceState()
    d, r = classify_user_input("Hola, ¿cómo estás?")
    assert d == 0
    assert r == "neutral"


def test_detect_expression_returns_dict():
    # Empty for normal responses (level expression takes over)
    assert detect_expression("Hola.") == {}
    # Philosophical bonus when content matches
    long_phil = "Pienso mucho en la existencia y el tiempo y el sentido de todo."
    out = detect_expression(long_phil)
    assert 'browInnerUp' in out
