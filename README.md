# smarthr360-retention

**Retention negotiator chatbot microservice of the SmartHR360 platform
(Module 5).** Detects disengagement signals, opens proactive chatbot
conversations with at-risk employees, identifies their primary need
(LLM or keyword fallback) and proposes retention actions for HR
validation.

Part of [SmartHR360](https://github.com/NawfalRAZOUK7/smarthr360).
Rescued from the never-merged `module-5` branch of the legacy shared
repo and converted to REST APIs with platform identity.

## The flow

```
detect (rules over engagement store)
   └─> Signal ──> Conversation (proactive opening message)
                      └─> employee replies ──> need identified
                                                  └─> Action (pending)
                                                         └─> HR review
```

Detection rules: engagement < 60 · performance < 50 · absences > 8d/90d.
Needs → actions: salary, growth, workload, recognition, flexibility,
general (templated descriptions + priority).

## API

| Endpoint | Who | Purpose |
|---|---|---|
| `POST /api/retention/detect/` | HR | batch detection + auto-open conversations |
| `GET /api/retention/signals/` | HR | unresolved signals |
| `GET /api/retention/conversations/` | HR all; employees their own | chat history |
| `POST /api/retention/conversations/{id}/respond/` | the employee | reply; triggers need extraction + action |
| `GET /api/retention/actions/?status=pending` | HR | proposed actions |
| `POST /api/retention/actions/{id}/review/` | HR | approve / reject / complete |
| `/api/retention/employees/` | HR | engagement store CRUD |

Identity: RS256 JWT from smarthr360-auth; the local Employee row links
to the platform user by `user_id` value (ADR-005), so employees chat
about themselves with their own token.

## Quickstart

```bash
pip install -r requirements.txt && cp .env.example .env
python manage.py migrate && python manage.py runserver 0.0.0.0:8007
```

Tests: `python manage.py test` (6 tests incl. full detect→chat→action→review flow)
