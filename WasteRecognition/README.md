# Waste recognition backend

There is no frontend or browser upload form.

## Receive an image from another Python module

```python
from image_recognizer import recognize_waste

result = recognize_waste(image_bytes, submission_id="submission_007")
```

image_bytes must contain the JPEG/PNG image received by your teammate's code. The function returns the shared result dictionary, or a filtered message for confidence below 0.80. It does not start Flask or save to MySQL.

For optional storage:

```python
from hometask1_waste_recognition import attempt_from_dict
from database import RecognitionRepository

if result["status"] != "filtered":
    RecognitionRepository().save(attempt_from_dict(result))
```

## Receive images over HTTP

If the caller runs separately, POST /recognize accepts multipart/form-data fields image and submission_id. Accepted results are saved and returned as JSON. GET /recognize now returns Method Not Allowed.

Other endpoints remain POST /events, POST /recognitions, GET /recognitions and GET /recognitions/<attempt_id>. The home endpoint returns JSON.

## Recognition provider

The current recognize_image() still calls OpenAI and requires OPENAI_API_KEY in the calling process environment, API credits and model access. The .env.local file is not automatically loaded by these modules.

A trained local classifier can replace recognize_image() without requiring OpenAI. It must return the same prediction fields. The rest of the classes, pipeline and database layer can be reused. No local recognition model has been installed yet.

A generic plastic/metal classifier does not establish PET, HDPE or Aluminum. Choose a matching model, train on the required labels, or agree broader material categories with the team. A material classifier also does not automatically provide item identity, cleanliness or special-item detection.

## Setup

Keep all project files together. Use Python 3.11+ and install requirements.txt in the project .venv. Configure the recognition provider in the caller process. Configure DB_HOST, DB_PORT, DB_USER and DB_PASSWORD only when using storage or Flask. Run database.py before app.py.

The existing encrypted local database settings and API-key files are separate from application source. No image or API key should be included when sharing source files.

JPEG/PNG images up to 10 MB are accepted. Preprocessing resizes to a maximum dimension of 1024 pixels and removes EXIF from the model input. No bounding boxes are used. HomeTask2's explicit bounding-box requirement remains omitted at your request.

The original HomeTask1 OOP classes, HomeTask2 processing concepts and HomeTask3 database layer remain. Recognition is currently limited to the small supported catalogue. Model confidence is an estimate, not verified accuracy.
