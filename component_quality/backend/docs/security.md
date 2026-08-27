# Security Documentation

## Current Security State

This project is currently a local development/prototype system. It does not implement authentication, authorization, user isolation, encrypted storage, CSRF protection, rate limiting, audit logging, or production secret management.

## Authentication and Authorization

| Mechanism | Implemented? | Notes |
| --- | --- | --- |
| JWT | No | No token issuing or verification exists. |
| OAuth | No | No identity provider integration exists. |
| Sessions | No | No server-side or cookie sessions are implemented. |
| API keys | No | No API key validation exists. |
| RBAC/permissions | No | All endpoints are publicly callable from allowed origins. |
| Middleware auth | No | Only CORS middleware is configured. |

## Input Validation

Implemented:

- Pydantic request schemas.
- `Field(min_length=1)` for base text request bodies.
- `clean_text()` whitespace rejection.
- Research-proposal validation in `document_validator.py`.
- URL validation for resource links.
- Score clamping for semantic grading.

Not implemented:

- Request size limits at the application layer.
- Malware scanning for uploaded files. PDF parsing is browser-side; backend receives extracted text.
- HTML sanitization because the API primarily returns JSON/PDF, but text is still displayed by React and should stay escaped by React defaults.

## CORS

`app.py` configures `CORSMiddleware` with `ALLOWED_ORIGINS`. Defaults include localhost/127.0.0.1 ports `3000` and `5173`; `.env.example` includes Vite origins.

Production risk: permissive origin changes could expose the unauthenticated API to unintended browser clients.

## Pickle Security

The backend loads pickle files:

- `models/weakness_svm_model.pkl`
- `models/feedback_embeddings.pkl`
- `models/semantic_grading_model.pkl`

Pickle loading can execute arbitrary code if artifacts are malicious. Only load artifacts generated locally or from a trusted build pipeline. Do not accept uploaded pickle files.

## File Persistence Risks

Runtime history is stored in JSON files under `data/`.

Risks:

- No per-user isolation.
- No encryption at rest.
- No concurrent write locking.
- Analysis text may contain sensitive research data or personal data.
- Corrupted JSON backups may retain historical sensitive content.

Recommended improvements:

- Move history into a real database with access control.
- Add file/database encryption policies where required.
- Add retention and deletion rules.
- Add structured audit logging.

## Injection and Web Risks

| Risk | Current mitigation | Gaps |
| --- | --- | --- |
| SQL injection | PostgreSQL is accessed through SQLAlchemy parameterized statements/ORM metadata. | Keep all DB access parameterized; do not build SQL from user input. |
| XSS | React escapes text by default. | Avoid `dangerouslySetInnerHTML`; sanitize any future HTML rendering. |
| CSRF | No cookie auth exists. | If sessions/cookies are added, add CSRF protection. |
| CORS abuse | Origin allowlist. | No authentication means CORS is not sufficient protection. |
| Rate limiting | None. | Add rate limiting before network exposure. |
| Secrets | `.env` ignored by Git. | No centralized secret manager. |

## Recommended Security Roadmap

1. Add authentication and role-based authorization for students/supervisors/admins.
2. Add per-user ownership checks around PostgreSQL-backed histories.
3. Add request size limits and server-side file upload validation if uploads move to backend.
4. Add rate limiting and abuse monitoring.
5. Add model artifact signing/checksum verification.
6. Add privacy policy and retention handling for proposal text.
7. Add deployment TLS and secure headers through a reverse proxy.

