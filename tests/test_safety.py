import pytest
from app.safety import check_emergency

EMERGENCY_QUERIES = [
    "I am having severe chest pain right now",
    "Help me I can't breathe",
    "My father has difficulty breathing",
    "She might be having a stroke",
    "I think my friend had a drug overdose",
    "I am having suicidal thoughts",
    "There is heavy bleeding from my leg",
    "The patient is unconscious on the floor",
    "I am experiencing a severe allergic reaction after eating peanuts",
]

NON_EMERGENCY_QUERIES = [
    "What are your opening hours on Monday?",
    "Do you offer seasonal flu vaccines?",
    "How should I prepare for my upcoming general check-up?",
    "I'd like to book an appointment for next Wednesday",
    "Where is the clinic located?",
]


@pytest.mark.parametrize("query", EMERGENCY_QUERIES)
def test_emergency_keywords_trigger_fixed_message(query):
    resp = check_emergency(query)
    assert resp is not None
    assert resp.intent == "emergency"
    assert resp.source == "Emergencies"
    assert resp.booking_reason is None
    assert "medical emergency" in resp.reply.lower()
    assert "emergency" in resp.reply.lower()


@pytest.mark.parametrize("query", NON_EMERGENCY_QUERIES)
def test_non_emergency_queries_do_not_trigger_safety(query):
    resp = check_emergency(query)
    assert resp is None
