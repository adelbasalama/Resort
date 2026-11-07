import os
from flask import Flask, jsonify
from app.web.routes import bp
from app.domain.errors import SubsystemError

def create_app():
    app = Flask(__name__)
    app.register_blueprint(bp)
    @app.errorhandler(SubsystemError)
    def handle_subsystem_error(error):
        return jsonify({"error": error.code, "message": str(error)}), error.status_code
    return app

if __name__ == "__main__":
    create_app().run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5002")), debug=False)
