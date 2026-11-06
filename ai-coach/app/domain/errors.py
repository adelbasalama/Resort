"""Subsystem C error types and safe API response mapping."""
class SubsystemError(Exception):
    code = "subsystem_error"
    status_code = 500

class InvalidGuidanceRequest(SubsystemError):
    code = "invalid_guidance_request"
    status_code = 400

class InvalidRuleRequest(SubsystemError):
    code = "invalid_rule_request"
    status_code = 400

class AdminUnauthorized(SubsystemError):
    code = "admin_unauthorized"
    status_code = 401

class GuidanceUnavailable(SubsystemError):
    code = "guidance_unavailable"
    status_code = 404

class PersistenceError(SubsystemError):
    code = "persistence_error"
    status_code = 503
