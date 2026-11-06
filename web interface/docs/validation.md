# Local validation

## OOP assignment update — 6 November 2026

- **39 tests passed**: 38 non-UI tests and the Streamlit AppTest passed in separate runs.
- Added six tests for explicit initialization, getter/setter behavior, invalid assignment rejection, MIME invalidation, UTC/UUID defaults and JSON/database round-trips.
- The UI test passed outside the execution sandbox; inside it, Windows socket-pair initialization stalled before the app ran.
- JSON schema comparison found only new class descriptions for Submission and Feedback; payload fields and requirements are unchanged. Exported schemas and UML diagrams were refreshed.

## Original validation record

- Python 3.12; exact tested direct dependencies pinned in requirements files.
- `python -m pytest -q`: **33 passed**.
- Tests cover real image validation, invalid/oversized/corrupt uploads, mocked multipart HTTP, JSON schemas, upstream failure and timeout, live-client B-to-C orchestration, special handling, missing rules, matching IDs, feedback persistence, repeated submissions and 50 concurrent fixture requests.
- Streamlit AppTest exercises example selection, result, feedback and reset.
- Headless Microsoft Edge / Playwright checks at 1440px desktop, 1024px, 768px tablet and 390px phone: no horizontal overflow or browser runtime errors.
- Browser flow: disabled empty submit, illustrated example, result, saved feedback, valid JSON download, reset, invalid image rejection, valid image preview and explicit uncertainty for a demo upload.
- Desktop and mobile layouts were visually inspected.

These checks do not certify production availability, WCAG conformance, actual AI recognition accuracy, real local rules, or a production 50-user browser workload. No live B/C service was supplied. Docker configuration is included but was not built in this environment. Browser screenshots and the environment-specific smoke script are ignored under `tmp/`.
