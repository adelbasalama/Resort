import hmac
import os
from datetime import date
from pathlib import Path
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
def configured_repository():
    backend = os.getenv("RULES_BACKEND", "mysql")
    if backend == "mysql":
        return MySQLRuleRepository()
    if backend == "sqlite":
        from app.sqlite_db import SQLiteRuleRepository
        path = os.getenv("RULES_DATABASE_PATH", str(Path(__file__).resolve().parents[3] / "data/rules.sqlite3"))
        return SQLiteRuleRepository(path)
    raise ValueError("RULES_BACKEND must be sqlite or mysql")


service = RegionalGuidanceService(configured_repository(), educator=configured_coach())


@bp.get("/v1/regions")
def regions():
    return jsonify({"regions": [{"id": r.id, "name": r.name, "source_url": r.source_url}
                                 for r in sorted(service.repository.list_regions(), key=lambda r: (r.id != "dortmund", r.name))]})


@bp.route("/admin", methods=["GET", "POST"])
def admin_page():
    message, error, status = None, None, 200
    selected = request.values.get("region_id", "dortmund")
    if request.method == "POST":
        token = os.getenv("ADMIN_API_TOKEN", "").strip()
        if not token or not hmac.compare_digest(request.form.get("token", ""), token):
            error, status = "Administrator token is missing or incorrect.", 401
        else:
            try:
                fields = request.form
                if fields["action"] == "region":
                    service.repository.create_region(Region(fields["region_id"], fields["name"], fields["source_url"]))
                    message = "Region added."
                elif fields["action"] == "rule":
                    rule = RecyclingRule(region_id=fields["region_id"], item_key=fields["item_key"].strip().lower(),
                        category=fields["category"], bin_label=fields["bin_label"], preparation=fields["preparation"],
                        source_url=fields["source_url"], reviewed_on=date.fromisoformat(fields["reviewed_on"]),
                        condition=fields["condition"])
                    rule_id, version = service.repository.create_rule_revision(rule)
                    message = f"Saved rule {rule_id}, version {version}. Previous decisions retain their original rule version."
                elif fields["action"] == "deactivate":
                    if not service.repository.deactivate_rule(int(fields["rule_id"])):
                        raise ValueError("Rule ID does not exist.")
                    message = "Rule deactivated."
                else:
                    raise ValueError("Unknown action.")
            except (ValueError, KeyError) as exc:
                error, status = str(exc), 400
            except SubsystemError as exc:
                error, status = str(exc), exc.status_code
    return render_template("admin.html", regions=service.repository.list_regions(),
                           rules=service.repository.list_rules(selected), selected=selected,
                           today=date.today().isoformat(), message=message, error=error), status


@bp.post("/v1/guidance")
def guidance_v1():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("recognition"), dict):
        return jsonify({"error": "invalid_guidance_request"}), 400
    recognition = payload["recognition"]
    submission_id, region_id = payload.get("submission_id"), payload.get("region_id")
    if (not isinstance(submission_id, str) or not 1 <= len(submission_id) <= 100
            or not isinstance(region_id, str) or not 1 <= len(region_id) <= 100
            or recognition.get("submission_id") != submission_id):
        return jsonify({"error": "invalid_guidance_request"}), 400
    item_key = recognition.get("item_key")
    condition = recognition.get("condition", "unknown")
    confidence = recognition.get("confidence")
    special = recognition.get("special", False)
    if (not isinstance(item_key, str) or not 1 <= len(item_key) <= 100
            or not isinstance(condition, str) or condition not in {"clean", "soiled", "unknown"}
            or isinstance(confidence, bool) or not isinstance(confidence, (int, float))
            or not .8 <= confidence <= 1 or recognition.get("status") != "recognized"
            or not isinstance(special, bool)):
        return jsonify({"error": "invalid_recognition_facts"}), 400
    item_key = {"can": "beverage_can", "paper": "paper_bag", "bottle": "glass_bottle"}.get(item_key, item_key)
    if region_id not in {r.id for r in service.repository.list_regions()}:
        return jsonify({"error": "unknown_region"}), 404
    response = {"submission_id": submission_id, "region_id": region_id,
                "status": "missing_rule", "category": "unknown", "bin_label": "Ask your local waste provider",
                "preparation_steps": [], "explanation": "No reviewed rule covers this item. Confirm disposal locally.",
                "source_url": None, "reviewed_at": None, "rule_version": None,
                "is_fallback": True, "is_demo": region_id.startswith("demo-"), "needs_details": []}
    if not special and item_key in {"beverage_can", "plastic_bottle", "glass_bottle"} and not region_id.startswith("demo-"):
        deposit = recognition.get("deposit", "unknown")
        if not isinstance(deposit, str) or deposit not in {"yes", "no", "unknown"}:
            return jsonify({"error": "invalid_deposit_answer"}), 400
        if deposit == "unknown":
            response.update(explanation="Check the deposit/return marking before choosing a bin.", needs_details=["deposit"])
            return jsonify(response)
        if deposit == "yes":
            item_key += "_deposit"
    if not special and item_key in {"paper_bag", "cardboard", "newspaper"} and condition == "unknown" and not region_id.startswith("demo-"):
        response.update(explanation="Is the paper clean and dry, or food-soiled?", needs_details=["condition"])
        return jsonify(response)
    try:
        result = service.decide_and_explain(region_id, item_key, condition)
    except RuleNotFoundError:
        return jsonify(response)
    rule, explanation = result["rule"], result["explanation"]
    if special and rule.category != "special":
        response["explanation"] = "This item needs special handling. Ask an authorized collection point."
        return jsonify(response)
    service.record_decision(region_id, item_key, condition, rule, submission_id, confidence)
    response.update(status="special" if rule.category == "special" else "matched",
                    category=rule.category, bin_label=rule.bin_label,
                    preparation_steps=[rule.preparation], explanation=explanation.text,
                    source_url=rule.source_url, reviewed_at=rule.reviewed_on.isoformat(),
                    rule_version=rule.version, is_fallback=explanation.is_fallback)
    return jsonify(response)

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
