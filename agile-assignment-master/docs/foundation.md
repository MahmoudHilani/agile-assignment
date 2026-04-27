# Foundation Notes

## Backend Layout

- `app/main.py`: FastAPI app factory and router registration
- `app/api/routes`: HTTP and websocket endpoints
- `app/core`: settings and shared response helpers
- `app/services`: provider contracts only
- `app/schemas`: request and response models
- `app/domain`: lightweight domain types for future orchestration
- `tests`: startup and placeholder behavior coverage
