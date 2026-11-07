"""HomeTask3: Flask endpoints connected to the first two homeworks."""

import os
from flask import Flask, jsonify, request
from mysql.connector import Error, IntegrityError
from openai import OpenAIError, APITimeoutError
from pydantic import ValidationError
from image_recognizer import MAX_IMAGE_BYTES, recognize_waste, recognize_contract
from hometask1_waste_recognition import attempt_from_dict
from hometask2_waste_stream import ConfidenceFilter, MaterialTransformer
from database import RecognitionRepository
from recognition_errors import RecognitionError

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 11 * 1024 * 1024
repository = RecognitionRepository()
pipeline = ConfidenceFilter(0.80) + MaterialTransformer()


@app.get("/health")
def health():
    return jsonify({"status": "ok", "recognition_configured": bool(os.getenv("OPENAI_API_KEY"))})


def save_result(data):
    """Both write endpoints use the same domain objects and database layer."""
    attempt = attempt_from_dict(data)
    repository.save(attempt)
    return jsonify(attempt.to_dict()), 201


@app.get("/")
def home():
    return jsonify({
        "message": "Subsystem B: aligned HomeTasks 1, 2 and 3",
        "endpoints": {
            "recognize_photo": "POST /recognize",
            "process_prediction": "POST /events",
            "save_completed_result": "POST /recognitions",
            "list": "GET /recognitions",
            "find": "GET /recognitions/<attempt_id>",
        },
    })


@app.post("/recognize")
@app.post("/v1/recognitions")
def recognize_photo():
    upload = request.files.get("image")
    submission_id = request.form.get("submission_id", "").strip()
    if upload is None:
        raise RecognitionError("An image file is required.")
    if not 1 <= len(submission_id) <= 100:
        raise RecognitionError("A submission_id of 1 to 100 characters is required.")
    image_bytes = upload.read(MAX_IMAGE_BYTES + 1)
    if not image_bytes:
        raise RecognitionError("The image is empty.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise RecognitionError("The image must not exceed 10 MB.", 413)
    try:
        if request.path == "/v1/recognitions":
            return jsonify(recognize_contract(image_bytes, submission_id))
        result = recognize_waste(image_bytes, submission_id)
    except APITimeoutError as error:
        raise RecognitionError("Image recognition timed out. Please try again.", 504) from error
    except OpenAIError as error:
        raise RecognitionError("Image recognition failed. Check the API key, quota and model settings.", 502) from error
    except ValidationError as error:
        raise RecognitionError("The model returned an invalid recognition result.", 502) from error
    except RuntimeError as error:
        raise RecognitionError(str(error), 502) from error
    if result.get("status") == "filtered":
        return jsonify(result)
    return save_result(result)


@app.errorhandler(413)
def upload_too_large(error):
    return jsonify({"error": "The upload is too large. Use an image up to 10 MB."}), 413


@app.post("/events")
def process_event():
    result = pipeline.process(request.get_json(silent=True))
    if result is None:
        return jsonify({"status": "filtered", "message": "Confidence is below 0.80; nothing was saved."})
    return save_result(result)


@app.post("/recognitions")
def save_recognition():
    return save_result(request.get_json(silent=True))


@app.get("/recognitions")
def list_recognitions():
    return jsonify(repository.get_all())


@app.get("/recognitions/<attempt_id>")
def find_recognition(attempt_id):
    result = repository.get_by_id(attempt_id)
    if result is None:
        return jsonify({"error": "Recognition not found."}), 404
    return jsonify(result)


@app.errorhandler(ValueError)
def invalid_input(error):
    return jsonify({"error": str(error)}), 400


@app.errorhandler(RecognitionError)
def recognition_error(error):
    return jsonify({"error": str(error)}), error.status_code


@app.errorhandler(IntegrityError)
def duplicate_attempt(error):
    if error.errno == 1062:
        return jsonify({"error": "This attempt_id already exists. Use a new attempt_id for a new attempt."}), 409
    return database_error(error)


@app.errorhandler(Error)
def database_error(error):
    return jsonify({"error": "Database unavailable. Check MySQL and your settings."}), 503


if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5001")), debug=False)
