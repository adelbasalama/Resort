"""Flask endpoint for photo recognition."""

import os
from flask import Flask, jsonify, request
from openai import OpenAIError, APITimeoutError
from pydantic import ValidationError
from image_recognizer import MAX_IMAGE_BYTES, recognize_contract
from recognition_errors import RecognitionError

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 11 * 1024 * 1024


@app.post('/v1/recognitions')
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
        return jsonify(recognize_contract(image_bytes, submission_id))
    except APITimeoutError as error:
        raise RecognitionError("Image recognition timed out. Please try again.", 504) from error
    except OpenAIError as error:
        raise RecognitionError("Image recognition failed. Check the API key, quota and model settings.", 502) from error
    except ValidationError as error:
        raise RecognitionError("The model returned an invalid recognition result.", 502) from error
    except RuntimeError as error:
        raise RecognitionError(str(error), 502) from error

@app.errorhandler(413)
def upload_too_large(error):
    return jsonify({"error": "The upload is too large. Use an image up to 10 MB."}), 413


@app.errorhandler(ValueError)
def invalid_input(error):
    return jsonify({"error": str(error)}), 400


@app.errorhandler(RecognitionError)
def recognition_error(error):
    return jsonify({"error": str(error)}), error.status_code


if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5001")), debug=False)
