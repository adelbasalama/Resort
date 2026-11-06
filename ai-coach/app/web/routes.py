import hmac
import os
from datetime import date
from collections.abc import Mapping

from flask import Blueprint, jsonify, render_template, request
from app.db import MySQLRuleRepository
from app.coach import configured_coach
from app.domain.models import Region, RecyclingRule
from app.domain.services import RegionalGuidanceService, RuleNotFoundError
from app.domain.errors import (
    AdminUnauthorized, InvalidGuidanceRequest, InvalidRuleRequest, SubsystemError,
)

bp = Blueprint("web", __name__)
service = RegionalGuidanceService(MySQLRuleRepository(), educator=configured_coach())

@bp.get("/")
def index():
    try: regions = service.repository.list_regions()
    except SubsystemError: regions = []
    return render_template("index.html", regions=regions)

@bp.post("/api/guidance")
def guidance():
    # Mahdi's recognition service can call this endpoint after it identifies an item.
    payload = request.get_json(silent=True) or request.form
    if not isinstance(payload, Mapping):
        error = InvalidGuidanceRequest("request body must be an object")
        return jsonify({"error": error.code, "message": str(error)}), error.status_code
    region_id = str(payload.get("region_id", "")).strip()
    item_key = str(payload.get("item_key", "")).strip().lower()
    condition = str(payload.get("condition", "unknown")).strip().lower()
    recognition_id = _optional_text(payload, "recognition_id")
    image_ref = _optional_text(payload, "image_ref")
    recognition_confidence = payload.get("recognition_confidence")
    if not region_id or not item_key:
        error = InvalidGuidanceRequest("region_id and item_key are required")
        return jsonify({"error": error.code, "message": str(error)}), error.status_code
    if condition not in {"any", "clean", "soiled", "unknown"}:
        error = InvalidGuidanceRequest("condition must be any, clean, soiled, or unknown")
        return jsonify({"error": error.code, "message": str(error)}), error.status_code
    if recognition_confidence is not None:
        try:
            recognition_confidence = float(recognition_confidence)
        except (TypeError, ValueError):
            error = InvalidGuidanceRequest("recognition_confidence must be a number from 0 to 1")
            return jsonify({"error": error.code, "message": str(error)}), error.status_code
        if not 0 <= recognition_confidence <= 1:
            error = InvalidGuidanceRequest("recognition_confidence must be a number from 0 to 1")
            return jsonify({"error": error.code, "message": str(error)}), error.status_code
    try:
        result = service.decide_and_explain(region_id, item_key, condition)
        rule, explanation = result["rule"], result["explanation"]
        service.record_decision(
            region_id, item_key, condition, rule, recognition_id,
            recognition_confidence, image_ref,
        )
        return jsonify({"region_id": rule.region_id, "item_key": rule.item_key,
            "category": rule.category, "bin_label": rule.bin_label,
            "preparation": rule.preparation, "source_url": rule.source_url,
            "reviewed_on": rule.reviewed_on.isoformat(), "rule_version": rule.version,
            "explanation": explanation.text, "explanation_is_fallback": explanation.is_fallback})
    except RuleNotFoundError as exc:
        return jsonify({"error": "guidance_unavailable", "message": str(exc)}), 404
    except SubsystemError as exc:
        return jsonify({"error": exc.code, "message": str(exc)}), exc.status_code


@bp.post("/api/admin/regions")
def create_region():
    # Adel, Mahdi, and the dashboard can keep using the public guidance endpoint.
    # Only an administrator can change the reviewed regional data.
    if not _is_admin():
        return _unauthorized()
    payload = request.get_json(silent=True)
    if not isinstance(payload, Mapping):
        return _rule_error("request body must be an object")
    try:
        region = Region(
            str(payload.get("id", "")),
            str(payload.get("name", "")),
            str(payload.get("source_url", "")),
        )
        service.repository.create_region(region)
        return jsonify({"id": region.id, "name": region.name,
                        "source_url": region.source_url}), 201
    except ValueError as exc:
        return _rule_error(str(exc))
    except SubsystemError as exc:
        return jsonify({"error": exc.code, "message": str(exc)}), exc.status_code


@bp.post("/api/admin/rules")
def create_rule_revision():
    if not _is_admin():
        return _unauthorized()
    payload = request.get_json(silent=True)
    if not isinstance(payload, Mapping):
        return _rule_error("request body must be an object")
    try:
        rule = RecyclingRule(
            region_id=str(payload.get("region_id", "")),
            item_key=str(payload.get("item_key", "")).strip().lower(),
            category=str(payload.get("category", "")),
            bin_label=str(payload.get("bin_label", "")),
            preparation=str(payload.get("preparation", "")),
            source_url=str(payload.get("source_url", "")),
            reviewed_on=date.fromisoformat(str(payload.get("reviewed_on", ""))),
            condition=str(payload.get("condition", "any")).strip().lower(),
        )
        rule_id, version = service.repository.create_rule_revision(rule)
        return jsonify({"id": rule_id, "region_id": rule.region_id,
                        "item_key": rule.item_key, "condition": rule.condition,
                        "version": version, "active": True}), 201
    except (TypeError, ValueError) as exc:
        return _rule_error(str(exc))
    except SubsystemError as exc:
        return jsonify({"error": exc.code, "message": str(exc)}), exc.status_code


@bp.delete("/api/admin/rules/<int:rule_id>")
def deactivate_rule(rule_id):
    if not _is_admin():
        return _unauthorized()
    try:
        if not service.repository.deactivate_rule(rule_id):
            return jsonify({"error": "rule_not_found", "message": "Rule does not exist"}), 404
        return "", 204
    except SubsystemError as exc:
        return jsonify({"error": exc.code, "message": str(exc)}), exc.status_code


def _is_admin():
    configured_token = os.environ.get("ADMIN_API_TOKEN", "").strip()
    supplied_token = request.headers.get("Authorization", "")
    supplied_token = supplied_token.removeprefix("Bearer ").strip()
    return bool(configured_token) and hmac.compare_digest(supplied_token, configured_token)


def _unauthorized():
    error = AdminUnauthorized("administrator authorization is required")
    return jsonify({"error": error.code, "message": str(error)}), error.status_code


def _rule_error(message):
    error = InvalidRuleRequest(message)
    return jsonify({"error": error.code, "message": str(error)}), error.status_code


def _optional_text(payload, key):
    value = payload.get(key)
    return str(value).strip() if value is not None and str(value).strip() else None
