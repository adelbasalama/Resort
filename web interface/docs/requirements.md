# Subsystem A requirement coverage

Source: supplied capstone slides, page 2, 13 October 2026. The user selects Streamlit instead of the proposed Flask architecture. Presentation instructions do not expand the requested scope to B, C or D.

| Requirement | Implementation / acceptance status |
| --- | --- |
| A-F01 upload | Native Streamlit photo uploader |
| A-F02 formats | JPG/JPEG/PNG extension and actual decoded format checks |
| A-F03 preview | Preview before submit, illustrated examples |
| A-F04 region | C's dynamic catalogue; fixtures in demo mode |
| A-F05 invalid images | Byte validation, decoded verification, format and pixel limits |
| A-F06 recognition | Multipart B client, configurable auth, no automatic retry |
| A-F07 item/category | Result item, material, category and confidence |
| A-F08 regional advice | C response with bin, preparation, explanation and provenance |
| A-F09 uncertainty | Explicit uncertain/unsupported states, low confidence skips C, reset to retry |
| A-F10 start again | Reset clears result and replaces photo uploader |
| A-N01 main page <3s | Local artwork, cached resources/regions; measure on target host |
| A-N02 50 users | SQLite WAL, atomic claims, no global network lock; 50-thread fixture test; full browser load test pending |
| A-N03 responsive | Stacked mobile columns, fluid headings, full-width controls |
| A-N04 browsers | Standard Streamlit controls; full browser matrix pending |
| A-N05 HTTPS | HTTPS required for B/C; public HTTPS needs production proxy/managed hosting |
| A-N06 10MB | Streamlit limit plus application 10 MiB limit |
| A-N07 messages | Plain-English upload, API, timeout and uncertainty messages |
| A-N08 99% availability | Health check and restart policy; deployment monitoring pending |
| A-N09 WCAG AA | Labeled controls, keyboard focus, meaningful alt text, textual states; independent audit pending |
| A-N10 one active call | Atomic SQLite UUID claim, HTTP idempotency headers, stable session request ID |

Domain classes: `Submission` and `Feedback` in `models.py`; `ImageUpload` in `uploads.py`. Pydantic validates shared JSON contracts. Photos stay in memory. UUID/enums are text, booleans integers, timestamps UTC ISO strings.

Only A persists submissions and feedback. Rule authoring, AI recognition, coach generation, dashboard analytics and their acceptance metrics belong to the other subsystems.
