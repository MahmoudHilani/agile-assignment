from app.api.routes import tts_routes


def test_get_answer_from_llm_uses_rag_query(monkeypatch):
    calls = []

    def fake_run_rag_query(question: str, top_k: int):
        calls.append((question, top_k))
        return "Company overview answer", ["company.txt#0"]

    monkeypatch.setattr(tts_routes, "run_rag_query", fake_run_rag_query)

    answer = tts_routes.get_answer_from_llm("What services do you offer?")

    assert answer == "Company overview answer"
    assert calls == [("What services do you offer?", 5)]


def test_stream_answer_from_llm_uses_rag_query_stream(monkeypatch):
    calls = []

    async def fake_run_rag_query_stream(question: str, top_k: int):
        calls.append((question, top_k))
        yield "Company "
        yield "overview"

    monkeypatch.setattr(tts_routes, "run_rag_query_stream", fake_run_rag_query_stream)

    chunks = list(tts_routes.stream_answer_from_llm("Tell me about the team"))

    assert chunks == ["Company ", "overview"]
    assert calls == [("Tell me about the team", 5)]
