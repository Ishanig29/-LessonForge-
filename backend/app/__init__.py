"""LessonForge Flask application factory."""
from __future__ import annotations

import logging
import os
import sys

from flask import Flask, jsonify
from flask_cors import CORS
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from .config.settings import Settings
from .models import SessionLocal, init_db
from .utils.errors import AppError


def _configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        stream=sys.stdout,
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def create_app(settings: Settings | None = None) -> Flask:
    _configure_logging()
    settings = settings or Settings()
    app = Flask(__name__)
    app.config["SETTINGS"] = settings
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2 MB request bodies
    app.json.sort_keys = False
    CORS(app, resources={r"/api/*": {"origins": [o.strip() for o in settings.cors_origins.split(",")]}})

    init_db(settings.database_url)

    from .routes.lessons import bp as lessons_bp
    from .routes.system import bp as system_bp

    app.register_blueprint(system_bp, url_prefix="/api")
    app.register_blueprint(lessons_bp, url_prefix="/api")

    @app.teardown_appcontext
    def _remove_session(_exc):
        SessionLocal.remove()

    @app.errorhandler(AppError)
    def _app_error(err: AppError):
        return jsonify(err.to_dict()), err.status_code

    @app.errorhandler(ValidationError)
    def _validation_error(err: ValidationError):
        details = [{"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in err.errors()]
        return jsonify({"error": {"code": "validation_error", "message": "Some fields are invalid.",
                                  "details": details}}), 422

    @app.errorhandler(SQLAlchemyError)
    def _db_error(err: SQLAlchemyError):
        logging.getLogger("lessonforge").exception("database error")
        SessionLocal.rollback()
        return jsonify({"error": {"code": "database_error",
                                  "message": "A database error occurred. Your previously saved work is intact."}}), 500

    @app.errorhandler(404)
    def _not_found(_err):
        return jsonify({"error": {"code": "not_found", "message": "Resource not found."}}), 404

    @app.errorhandler(405)
    def _method(_err):
        return jsonify({"error": {"code": "method_not_allowed", "message": "Method not allowed."}}), 405

    @app.errorhandler(413)
    def _too_large(_err):
        return jsonify({"error": {"code": "payload_too_large", "message": "Request body is too large."}}), 413

    @app.errorhandler(Exception)
    def _unexpected(err: Exception):
        # Never leak stack traces or environment details to the client.
        logging.getLogger("lessonforge").exception("unhandled error")
        return jsonify({"error": {"code": "internal_error",
                                  "message": "Unexpected server error. Details are in the server log."}}), 500

    return app
