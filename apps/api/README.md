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

## API Endpoints

### `PUT /documents` — Replace company document

Replaces the document used by the LLM with a newly uploaded file. The old document is deleted immediately and the new one takes effect for all subsequent queries without requiring a restart.

**Authentication:** Bearer token with `Admin` role required.
- No token → `401 Unauthorized`
- Valid token but non-admin role → `403 Forbidden`

**Accepted formats:** `.pdf`, `.docx`, `.txt`

**Constraints:** Maximum file size 10 MB; file must not be empty.

**Success response `200`:**
```json
{ "accepted": true, "filename": "handbook.pdf", "message": "Document 'handbook.pdf' replaced successfully" }
```

**Error responses:** `401`, `403`, `422` (unsupported format / empty file / oversized file)

## Commands

```bash
python -m uv sync
python -m uv run uvicorn app.main:app --reload
python -m uv run pytest
```
