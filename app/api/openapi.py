from __future__ import annotations

import inspect
import re

from fastapi import FastAPI
from fastapi.routing import APIRoute

OPENAPI_DESCRIPTION = """
Smart Paper Service OpenAPI documentation.

This service covers OCR recognition, wrong-question maintenance, variant generation,
print export, student and parent relationships, statistics, and admin agent settings.

- Swagger UI: `/docs`
- ReDoc: `/redoc`
- OpenAPI JSON: `/openapi.json`
""".strip()

OPENAPI_TAGS = [
    {"name": "system", "description": "Service-level entry points and discovery endpoints."},
    {"name": "health", "description": "Health checks and liveness probes."},
    {"name": "auth", "description": "Student login configuration and verification APIs."},
    {"name": "ocr", "description": "OCR, diagram extraction, and question analysis APIs."},
    {"name": "variants", "description": "Variant generation APIs based on source text or wrong questions."},
    {"name": "export", "description": "Print and export job creation and status lookup APIs."},
    {"name": "users", "description": "User, student profile, and parent-student relationship APIs."},
    {"name": "metadata", "description": "Metadata dictionaries for subjects, categories, and error reasons."},
    {"name": "wrong-questions", "description": "Wrong-question CRUD and study-record maintenance APIs."},
    {"name": "statistics", "description": "Student wrong-question and study trend aggregation APIs."},
    {"name": "analysis", "description": "Asynchronous trend analysis task APIs."},
    {"name": "admin", "description": "Admin APIs for agent configuration and connectivity testing."},
]

OPERATION_METADATA: dict[tuple[str, str], dict[str, str]] = {
    ("GET", "/"): {
        "summary": "Get Service Info",
        "description": "Return the basic service status and documentation endpoints for quick discovery.",
    },
    ("GET", "/api/health"): {
        "summary": "Health Check",
        "description": "Verify that the backend process is reachable and return the current UTC timestamp.",
    },
    ("GET", "/api/auth/student-login-config"): {
        "summary": "Get Student Login Config",
        "description": "Return the current student login page mode, title text, and preset-account visibility.",
    },
    ("POST", "/api/auth/student-login"): {
        "summary": "Verify Student Login",
        "description": "Validate a preset student account and create a baseline student profile when it does not exist yet.",
    },
    ("GET", "/api/subjects"): {
        "summary": "List Subjects",
        "description": "Query the subject dictionary with pagination and optional active-only filtering.",
    },
    ("POST", "/api/subjects"): {
        "summary": "Create Subject",
        "description": "Create a new subject dictionary entry by code and display name.",
    },
    ("GET", "/api/wrong-question-categories"): {
        "summary": "List Wrong Question Categories",
        "description": "Query wrong-question category definitions with pagination.",
    },
    ("POST", "/api/wrong-question-categories"): {
        "summary": "Create Wrong Question Category",
        "description": "Create a new wrong-question category for later wrong-question classification.",
    },
    ("GET", "/api/error-reasons"): {
        "summary": "List Error Reasons",
        "description": "Query the error-reason dictionary and optionally filter by wrong-question category.",
    },
    ("POST", "/api/error-reasons"): {
        "summary": "Create Error Reason",
        "description": "Create a new error-reason dictionary entry and optionally bind it to a category.",
    },
    ("POST", "/api/ocr/extract"): {
        "summary": "Extract Questions",
        "description": "Upload a paper image, run the full OCR pipeline, persist paper and question assets, and return cropped image URLs.",
    },
    ("POST", "/api/ocr/extract/simple"): {
        "summary": "Extract Questions Without Persistence",
        "description": "Upload an image and run OCR only, without storing paper, question, or image records.",
    },
    ("POST", "/api/ocr/diagram/svg"): {
        "summary": "Generate Diagram SVG",
        "description": "Generate an SVG version of the diagram based on the question text and optional seed images.",
    },
    ("POST", "/api/ocr/analyze-question"): {
        "summary": "Analyze Question",
        "description": "Infer subject, category, error reason, and title for a question by calling the analysis service.",
    },
    ("POST", "/api/variants/generate"): {
        "summary": "Generate Variants",
        "description": "Generate same-type practice variants directly from source text and optional grade or subject context.",
    },
    ("POST", "/api/variants/generate-for-question"): {
        "summary": "Generate Variants For Wrong Question",
        "description": "Generate variants based on an existing wrong-question record and its resolved subject context.",
    },
    ("POST", "/api/export"): {
        "summary": "Create Export Task",
        "description": "Create a PDF export task for single-question or multi-question print packages and return the job result.",
    },
    ("POST", "/api/print-pack/export"): {
        "summary": "Create Print Pack Export",
        "description": "Create a PDF print pack from the frontend-provided ordered question array and return the persisted export record.",
    },
    ("GET", "/api/export/{job_id}"): {
        "summary": "Get Export Status",
        "description": "Look up a previously created export job by job ID and return its current status and download URL.",
    },
    ("POST", "/api/users"): {
        "summary": "Create User",
        "description": "Create a user and optionally create the student profile when the role is `student`.",
    },
    ("GET", "/api/users"): {
        "summary": "List Users",
        "description": "Query users with optional role, status, keyword, and pagination filters.",
    },
    ("GET", "/api/users/{user_id}"): {
        "summary": "Get User",
        "description": "Return a single user and the attached student profile when one exists.",
    },
    ("PUT", "/api/users/{user_id}"): {
        "summary": "Update User",
        "description": "Update a user and reconcile student profile data based on the target role.",
    },
    ("POST", "/api/users/parent-student-links"): {
        "summary": "Create Parent Student Link",
        "description": "Bind a parent user to a student user and store the relationship type.",
    },
    ("DELETE", "/api/users/parent-student-links/{link_id}"): {
        "summary": "Delete Parent Student Link",
        "description": "Remove an existing parent-student relationship by link ID.",
    },
    ("GET", "/api/users/{parent_id}/students"): {
        "summary": "List Students By Parent",
        "description": "Return all student users currently bound to the given parent user.",
    },
    ("GET", "/api/users/{student_id}/parents"): {
        "summary": "List Parents By Student",
        "description": "Return all parent users currently bound to the given student user.",
    },
    ("POST", "/api/wrong-questions"): {
        "summary": "Create Wrong Question",
        "description": "Create a wrong-question record, validate metadata references, and bind error reasons.",
    },
    ("GET", "/api/wrong-questions"): {
        "summary": "List Wrong Questions",
        "description": "Query wrong-question records with filters for student, subject, grade, status, bookmark, category, term, and keyword.",
    },
    ("GET", "/api/wrong-questions/{wrong_question_id}"): {
        "summary": "Get Wrong Question",
        "description": "Return the full wrong-question detail, including subject, category, and error reasons.",
    },
    ("PUT", "/api/wrong-questions/{wrong_question_id}"): {
        "summary": "Update Wrong Question",
        "description": "Update wrong-question content, metadata, and associated error reasons.",
    },
    ("DELETE", "/api/wrong-questions/{wrong_question_id}"): {
        "summary": "Delete Wrong Question",
        "description": "Delete a wrong-question record by ID.",
    },
    ("POST", "/api/wrong-questions/{wrong_question_id}/study-records"): {
        "summary": "Create Study Record",
        "description": "Create a study record for a wrong question and update the wrong-question mastery status.",
    },
    ("GET", "/api/wrong-questions/{wrong_question_id}/study-records"): {
        "summary": "List Study Records",
        "description": "List study records for a wrong question with pagination.",
    },
    ("GET", "/api/statistics/overview"): {
        "summary": "Get Statistics Overview",
        "description": "Return aggregated wrong-question, practice, breakdown, and trend metrics for a student.",
    },
    ("GET", "/api/statistics/by-subject"): {
        "summary": "Get Statistics By Subject",
        "description": "Return wrong-question statistics grouped by subject for a student and optional time range.",
    },
    ("GET", "/api/statistics/by-grade"): {
        "summary": "Get Statistics By Grade",
        "description": "Return wrong-question statistics grouped by grade for a student and optional time range.",
    },
    ("GET", "/api/statistics/by-category"): {
        "summary": "Get Statistics By Category",
        "description": "Return wrong-question statistics grouped by wrong-question category.",
    },
    ("GET", "/api/statistics/by-error-reason"): {
        "summary": "Get Statistics By Error Reason",
        "description": "Return wrong-question statistics grouped by error reason.",
    },
    ("GET", "/api/statistics/trend"): {
        "summary": "Get Statistics Trend",
        "description": "Return day-level study trend statistics for a student and optional time range.",
    },
    ("POST", "/api/analysis/trend"): {
        "summary": "Create Trend Analysis",
        "description": "Create a trend analysis task for a student and dispatch the background job.",
    },
    ("GET", "/api/analysis/trend/latest"): {
        "summary": "Get Latest Trend Analysis",
        "description": "Return the latest completed trend analysis for a student.",
    },
    ("GET", "/api/analysis/trend/{analysis_id}"): {
        "summary": "Get Trend Analysis",
        "description": "Look up a specific trend analysis task by analysis ID.",
    },
    ("GET", "/api/analysis/trend"): {
        "summary": "List Trend Analyses",
        "description": "Return recent trend analysis records for a student, ordered by creation time descending.",
    },
    ("GET", "/api/admin/agents"): {
        "summary": "List Agent Configurations",
        "description": "Return all agent configurations after merging persisted values with defaults.",
    },
    ("GET", "/api/admin/agents/{node_name}"): {
        "summary": "Get Agent Configuration",
        "description": "Return the effective configuration for one admin agent node.",
    },
    ("PUT", "/api/admin/agents/{node_name}"): {
        "summary": "Update Agent Configuration",
        "description": "Create or update an agent configuration and return the resolved effective result.",
    },
    ("POST", "/api/admin/agents/{node_name}/test"): {
        "summary": "Test Agent Configuration",
        "description": "Send a lightweight test prompt through the configured LLM client and return the connectivity result.",
    },
}


def _get_primary_method(route: APIRoute) -> str | None:
    methods = sorted(
        method
        for method in (route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    )
    if not methods:
        return None
    return methods[0]


def _default_summary(route: APIRoute) -> str:
    words = route.name.replace("_", " ").strip().split()
    return " ".join(word.capitalize() for word in words) or "API Operation"


def _build_operation_id(method: str, path: str) -> str:
    if path == "/":
        return f"{method.lower()}Root"

    parts: list[str] = []
    for segment in path.strip("/").split("/"):
        normalized = segment.strip("{}")
        normalized = re.sub(r"[^0-9A-Za-z_]+", "_", normalized)
        if segment.startswith("{") and segment.endswith("}"):
            parts.append("by")
        parts.extend(piece for piece in normalized.split("_") if piece)

    suffix = "".join(part.capitalize() for part in parts)
    return f"{method.lower()}{suffix}"


def apply_openapi_metadata(app: FastAPI) -> None:
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.include_in_schema:
            continue

        method = _get_primary_method(route)
        if method is None:
            continue

        metadata = OPERATION_METADATA.get((method, route.path), {})
        route.summary = metadata.get("summary") or route.summary or _default_summary(route)
        route.description = (
            metadata.get("description")
            or route.description
            or inspect.getdoc(route.endpoint)
            or route.summary
        )
        route.operation_id = metadata.get("operation_id") or _build_operation_id(method, route.path)


def get_openapi_documentation_gaps(app: FastAPI) -> list[str]:
    schema = app.openapi()
    gaps: list[str] = []
    paths = schema.get("paths", {})

    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.include_in_schema:
            continue

        method = _get_primary_method(route)
        if method is None:
            continue

        operation = paths.get(route.path, {}).get(method.lower())
        if operation is None:
            gaps.append(f"{method} {route.path}: missing OpenAPI operation")
            continue

        for field_name in ("summary", "description", "operationId"):
            if not operation.get(field_name):
                gaps.append(f"{method} {route.path}: missing {field_name}")

    return gaps
