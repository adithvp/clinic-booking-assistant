from unittest.mock import MagicMock
import pytest
from app.llm import ask_assistant, LLMStructuredOutput
from app.schemas import ChatMessage


class FakeChoice:
    def __init__(self, parsed=None, refusal=None):
        self.message = MagicMock()
        self.message.parsed = parsed
        self.message.refusal = refusal


class FakeCompletion:
    def __init__(self, choice):
        self.choices = [choice]


def setup_mock_openai(monkeypatch, parse_func_or_side_effect):
    mock_client = MagicMock()
    if callable(parse_func_or_side_effect) and not isinstance(parse_func_or_side_effect, MagicMock):
        mock_client.beta.chat.completions.parse = parse_func_or_side_effect
    elif isinstance(parse_func_or_side_effect, MagicMock):
        mock_client.beta.chat.completions.parse = parse_func_or_side_effect
    else:
        mock_client.beta.chat.completions.parse = MagicMock(return_value=parse_func_or_side_effect)
    monkeypatch.setattr("app.llm.OpenAI", lambda *args, **kwargs: mock_client)
    return mock_client.beta.chat.completions.parse


def test_ask_assistant_faq_intent(monkeypatch):
    fake_parsed = LLMStructuredOutput(
        reply="We are open Monday to Friday, 8:00 AM to 5:00 PM.",
        intent="faq",
        source="Hours",
        booking_reason=None,
    )
    mock_parse = MagicMock(return_value=FakeCompletion(FakeChoice(parsed=fake_parsed)))
    setup_mock_openai(monkeypatch, mock_parse)

    messages = [ChatMessage(role="user", content="What are your hours?")]
    resp = ask_assistant(messages, api_key="test-key")

    assert resp.reply == "We are open Monday to Friday, 8:00 AM to 5:00 PM."
    assert resp.intent == "faq"
    assert resp.source == "Hours"
    assert resp.booking_reason is None
    assert mock_parse.call_count == 1


def test_ask_assistant_booking_intent(monkeypatch):
    fake_parsed = LLMStructuredOutput(
        reply="Please fill in the appointment request form below.",
        intent="booking",
        source="Appointments",
        booking_reason="General check-up",
    )
    mock_parse = MagicMock(return_value=FakeCompletion(FakeChoice(parsed=fake_parsed)))
    setup_mock_openai(monkeypatch, mock_parse)

    messages = [ChatMessage(role="user", content="I need a general check-up")]
    resp = ask_assistant(messages, api_key="test-key")

    assert resp.intent == "booking"
    assert resp.booking_reason == "General check-up"
    assert resp.source == "Appointments"


def test_ask_assistant_medical_advice_decline(monkeypatch):
    fake_parsed = LLMStructuredOutput(
        reply="I cannot provide medical advice or evaluate symptoms. Please speak with a licensed clinician.",
        intent="medical_advice",
        source=None,
        booking_reason=None,
    )
    mock_parse = MagicMock(return_value=FakeCompletion(FakeChoice(parsed=fake_parsed)))
    setup_mock_openai(monkeypatch, mock_parse)

    messages = [ChatMessage(role="user", content="What medication should I take for high fever?")]
    resp = ask_assistant(messages, api_key="test-key")

    assert resp.intent == "medical_advice"
    assert "cannot provide medical advice" in resp.reply.lower()


def test_llm_failure_triggers_one_retry_then_fallback(monkeypatch):
    mock_parse = MagicMock(side_effect=Exception("API connection timeout"))
    setup_mock_openai(monkeypatch, mock_parse)

    messages = [ChatMessage(role="user", content="Do you offer vaccines?")]
    resp = ask_assistant(messages, api_key="test-key")

    # Should attempt initial call + 1 retry = 2 attempts total
    assert mock_parse.call_count == 2
    assert "trouble processing your request" in resp.reply
    assert resp.intent == "other"


def test_llm_missing_api_key_raises_error():
    messages = [ChatMessage(role="user", content="Hello")]
    with pytest.raises(ValueError, match="OPENAI_API_KEY is not configured"):
        ask_assistant(messages, api_key="")


def test_autonomous_agent_services_query():
    from app.llm import run_autonomous_agent
    messages = [ChatMessage(role="user", content="What services do you offer?")]
    resp = run_autonomous_agent(messages)
    assert resp.intent == "faq"
    assert resp.source == "Services"
    assert "General check-ups" in resp.reply
    assert "Vaccinations" in resp.reply


def test_autonomous_agent_hours_query():
    from app.llm import run_autonomous_agent
    messages = [ChatMessage(role="user", content="What are your hours?")]
    resp = run_autonomous_agent(messages)
    assert resp.intent == "faq"
    assert resp.source == "Hours"
    assert "7 AM to 8 PM" in resp.reply


def test_autonomous_agent_check_status():
    from app.llm import run_autonomous_agent
    messages = [ChatMessage(role="user", content="Check status of booking B1001")]
    resp = run_autonomous_agent(messages)
    assert resp.intent == "booking"
    assert "B1001" in resp.reply
    assert "Accepted" in resp.reply
