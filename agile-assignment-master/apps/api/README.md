# API Foundation

This FastAPI app is a foundation only. It defines the project shape and placeholder contracts for a future backend similar in spirit to `agile-rag`, without implementing any feature pipeline.

## Included

- application entrypoint
- settings
- health route
- placeholder document, query, and voice endpoints
- typed schemas
- provider interface stubs
- tests for startup and health

## Not Included

- retrieval or chunking logic
- embeddings
- vector database integration
- LLM providers
- speech pipelines
- storage, auth, or background jobs

## Commands

```bash
python -m uv sync
python -m uv run uvicorn app.main:app --reload
python -m uv run pytest
```
