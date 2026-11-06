# ReSort · Waste sorting assistant

A responsive Streamlit implementation of **subsystem A: Public web interface**, based on page 2 of the supplied capstone slides. The requested Streamlit framework supersedes the slides' proposed Flask architecture. Subsystems B (recognition), C (rules/coach), and D (dashboard) remain separate; this project provides contracts and integration points for them.

For a teacher presentation, see the [project explanation and presentation guide](docs/project-explained.md), including architecture, request sequence, a simplified UML diagram and likely questions. The [complete UML class diagram](docs/class-diagram.md) covers all 19 project classes; its editable Mermaid source is [class-diagram.mmd](docs/class-diagram.mmd).

## OOP assignment classes

Subsystem A's three presentation classes are `ImageUpload`, `Submission` and `Feedback`. Each declares an explicit constructor and getter/setter methods. Upload properties encapsulate backing attributes; Pydantic validates submission and feedback initialization and assignments. Constructors initialize state and defaults; upload file checking is a separate `validate()` operation. See the [assignment explanation and examples](docs/project-explained.md#assignment-focus-three-subsystem-a-classes).

```python
from waste_sorting.models import Feedback, Submission

submission = Submission(region_id="dortmund")
print(submission.get_id(), submission.get_status())
submission.set_status("failed")
submission.set_error("Service unavailable")

feedback = Feedback(submission_id=submission.get_id(), helpful=True)
feedback.set_helpful(False)
print(feedback.get_helpful())
```

This snippet demonstrates object access; saving feedback requires a completed submission. Identity and timestamp fields have getters without dedicated setters. The existing JSON contracts and UI attribute access remain supported.

## Run locally

Python 3.12 recommended. From this folder in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open http://localhost:8501. No activation, API key or external service is needed in demo mode. Select **Try an example** to explore results, feedback, download and reset. Uploaded photos are validated and previewed, but demo mode returns an explicit uncertain result because it does not perform recognition. Illustrated examples and their collection advice are fixtures, not verified regional rules.

## Connect your teammates' services

```powershell
Copy-Item .env.example .env
```

Set `SERVICE_MODE=http`, both HTTPS service URLs, and optional server-side bearer tokens in `.env`. Subsystem C supplies the region list. A sends validated photos to B, then sends confident recognition facts to C. No API keys go to the browser. Examples still use isolated fixtures even when live services are configured.

See [API contracts](docs/api-contracts.md) for endpoints, payloads, idempotency, errors and D's storage integration. No OpenAI calls or local recognition/rules algorithms are implemented in A. Service paths are a proposed v1 agreement for the team, not claims about existing APIs.

## Project structure

```text
app.py                       Streamlit composition and session state
.streamlit/config.toml       Theme, upload limit, server protections
assets/                     CSS and original SVG illustration
src/waste_sorting/
  config.py                  Server-only environment configuration
  models.py                  Validated shared JSON contracts / domain classes
  uploads.py                 ImageUpload and actual file validation
  workflow.py                B → C orchestration and request deduplication
  storage.py                 Shared Submission and Feedback storage functions
  ui.py                      Reusable interface components
  services/
    clients.py               Protocols and HTTP adapters for B/C
    demo.py                  Clearly marked interface fixtures
tests/                       Upload, integration, concurrency and UI tests
docs/                        API contract and requirement coverage
Dockerfile, compose.yaml     Container and persistent database volume
```

## Data and privacy

Photos and filenames are never written to the database or application files. Validated photo bytes stay in process memory and are forwarded only in connected upload mode. Streamlit retains uploaded bytes in memory for the active session; resetting replaces the active uploader. A saves UUIDs, region, UTC timestamps, status, demo flag, outcome JSON and optional feedback in `data/waste_sorting.sqlite3`. Hosting and upstream retention policies are outside A's control. Demo outcomes are marked `is_demo=1` so D can exclude them.

SQLite WAL and atomic request claims prevent repeat recognition for the same UUID across sessions/processes sharing that database. Each submission action receives one UUID; explicit retry/reset starts another. There is no automatic upstream retry. Browser sessions are separate; no public submission-history endpoint is exposed.

## Test

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

The suite includes a 50-thread metadata/workflow smoke test with fixtures; this is not a production 50-user browser load benchmark. Tests mock upstream HTTP and make no paid AI calls.

See [local validation](docs/validation.md) for the checks performed. Machine-readable contracts for teammates are in `docs/schemas/`; regenerate them with `python scripts/export_schemas.py`.

## Docker and deployment

```powershell
docker compose up --build
```

Use an HTTPS reverse proxy or managed Streamlit hosting in production. Forward WebSocket connections, use a persistent local database volume, keep secrets out of source control, and leave CORS/XSRF protections enabled. The Compose port binds to localhost for development. `/_stcore/health` supports health checks. Do not share SQLite over a network filesystem or across independent replicas; replace the repository with PostgreSQL for distributed deployments.

The 3-second load, 50 concurrent users, 99% scheduled availability, cross-browser support and WCAG 2.1 AA goals require deployment measurements and an accessibility audit. See [requirement coverage](docs/requirements.md) for implemented behavior and remaining acceptance checks.
