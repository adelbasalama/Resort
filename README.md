# ReSort · Assignment 4 · Exception handling and unit tests

This submission contains the application paths and automated tests used to demonstrate error handling in the four ReSort subsystems.

| Subsystem | Error class | Example |
| --- | --- | --- |
| 1 · Public interface | [`UploadError`](web%20interface/src/waste_sorting/uploads.py) and [`ServiceError`](web%20interface/src/waste_sorting/services/clients.py) | Reject invalid uploads and surface downstream service failures. |
| 2 · Waste recognition | [`RecognitionError`](WasteRecognition/recognition_errors.py) | Return HTTP 400 for invalid input, 413 for oversized uploads, and 504 for provider timeouts. |
| 3 · Regional rules and AI coach | [`SubsystemError` and subclasses](ai-coach/app/domain/errors.py) | Reject invalid guidance or admin requests and report unavailable rule storage. |
| 4 · Municipal dashboard | [`SubmissionStorageError`](subsystem4_dashboard/dashboard/errors.py) | Report unreadable submission storage without treating a database that has yet to be created as an outage. |

## Run the tests

Use Python 3.11 or newer. From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe test_all.py
```

The runner executes 74 tests across four isolated suites, which use Flask test clients, controlled provider responses, and temporary SQLite files. The tests require no API key or MySQL server.

[Public interface tests](web%20interface/tests/) · [Recognition tests](WasteRecognition/tests/) · [AI coach tests](ai-coach/tests/) · [Dashboard tests](subsystem4_dashboard/tests/)

[GitHub submission branch](https://github.com/adelbasalama/Resort/tree/HomeworkAssignment4)
