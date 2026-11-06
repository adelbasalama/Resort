# Subsystem integration contract · v1 proposal

Only A is implemented. B/C teams implement these endpoints, or adapt the paths in `services/clients.py`. Requests originate from the Python server. Use HTTPS and optional `Authorization: Bearer <token>` per service. Responses must be JSON. Unknown response fields are rejected to expose contract drift early.

Machine-readable JSON schemas are in `docs/schemas/`. Regenerate them with `.venv\Scripts\python.exe scripts/export_schemas.py`. The runtime Pydantic models remain the source of truth; conditional provenance checks are enforced in Python as well.

## C → A: regions

`GET {GUIDANCE_API_URL}/v1/regions`

```json
{"regions": [{"id": "dortmund", "name": "Dortmund", "source_url": "https://www.edg.de/"}]}
```

Return a nonempty list with unique IDs. Cached for five minutes. New regions require no code changes.

## A → B: recognition

`POST {RECOGNITION_API_URL}/v1/recognitions`

Header: `Idempotency-Key: <submission UUID>`.

Multipart fields: `submission_id` (UUID string), `image` (validated binary JPG/JPEG/PNG). Original filename is replaced with `upload.jpg` or `upload.png`. Maximum 10 MiB and 25 megapixels. B owns resizing, metadata stripping, AI calls and item normalization. Do not store or log photos.

```json
{
  "submission_id": "0d258ce9-762e-48f0-b271-3374f926a8aa",
  "status": "recognized",
  "item_key": "beverage_can",
  "item_name": "Beverage can",
  "material": "metal",
  "condition": "clean",
  "confidence": 0.97,
  "special": false
}
```

`status`: `recognized | uncertain | unsupported`. `condition`: `clean | soiled | unknown`. Confidence is 0–1. Return `item_key="unknown"`, `item_name="Unknown item"`, and `material="unknown"` if unknown. For uncertain, unsupported or confidence below 0.60, A shows retry guidance and skips C. B must return the supplied submission ID. Default B request timeout is 15 seconds per HTTP operation; B should enforce its own overall 15-second deadline. No automatic retry.

## A → C: guidance

`POST {GUIDANCE_API_URL}/v1/guidance`

Header: `Idempotency-Key: <submission UUID>`.

```json
{
  "submission_id": "0d258ce9-762e-48f0-b271-3374f926a8aa",
  "region_id": "dortmund",
  "recognition": {
    "submission_id": "0d258ce9-762e-48f0-b271-3374f926a8aa",
    "status": "recognized", "item_key": "beverage_can",
    "item_name": "Beverage can", "material": "metal", "condition": "clean",
    "confidence": 0.97, "special": false
  }
}
```

Illustrative response structure (not an actual Dortmund rule):

```json
{
  "submission_id": "0d258ce9-762e-48f0-b271-3374f926a8aa",
  "region_id": "dortmund",
  "status": "matched",
  "category": "packaging",
  "bin_label": "Collection specified by the verified rule",
  "preparation_steps": ["Follow the verified rule's preparation steps."],
  "explanation": "Approved explanation from the regional service.",
  "source_url": "https://www.edg.de/",
  "reviewed_at": "2026-10-13",
  "rule_version": 1,
  "is_fallback": false
}
```

`status`: `matched | missing_rule | special`. Matched results require a source URL, review date and positive rule version. For missing rules, provenance may be null. C owns the decision, sources, rule versions and approved coach fallback. A never generates local bin advice. Special recognition cannot be paired with ordinary `matched` guidance. Missing-rule results display a warning and explanation without an ordinary bin recommendation. Default C timeout: 10 seconds per HTTP operation.

## Failures and idempotency

A treats timeouts, non-2xx responses, redirects, malformed JSON, contract violations and wrong submission/region IDs as failures. Upstream error bodies are not displayed or logged. The user gets a safe English message. C failure is not replaced with fabricated local advice. De-duplicate the same UUID in downstream services too.

A atomically claims the UUID before calling B. Duplicate calls return the stored record. Processing records older than two minutes are marked failed when queried again; retry starts a new UUID. Keep configured timeouts below this threshold. HTTPX timeouts apply per I/O phase, not to the entire network operation.

## A → D: shared metadata

As proposed in the slides, D reads the shared database; A does not implement D's dashboard or a new unauthenticated HTTP API. Public UI calls to B/C use HTTP. For a separately hosted D, implement an authenticated aggregate service or PostgreSQL repository adapter at this boundary.

| Table | Columns |
| --- | --- |
| `submissions` | `id TEXT PK`, `region_id TEXT`, `status TEXT`, `created_at TEXT UTC ISO`, `updated_at TEXT UTC ISO`, `is_demo INTEGER`, `outcome_json TEXT` |
| `feedback` | `submission_id TEXT PK/FK`, `helpful INTEGER 0/1`, `created_at TEXT UTC ISO` |

`outcome_json` follows `Submission` in `models.py`: nested recognition/guidance, safe error, identity/status/timestamps. No photo or filename. Read saved decisions rather than reapplying today's rule versions. One feedback per submission, updated on a changed answer. A v1 does not collect user-corrected categories.

Example read-only D query:

```sql
SELECT region_id,
       COALESCE(json_extract(outcome_json, '$.guidance.category'), 'Unknown') AS category,
       COUNT(*) AS item_count
FROM submissions
WHERE is_demo = 0 AND status = 'completed'
  AND created_at >= :start_utc AND created_at < :end_utc
GROUP BY region_id, category;
```

Use a read-only SQLite URI (`file:...?...mode=ro`, `uri=True`), parameterized queries and aggregate exports only. D owns access control. Shared writes use `Repository.save()` and `Repository.save_feedback()`.
