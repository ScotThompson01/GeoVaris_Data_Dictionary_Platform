"""Inventory of API routes requiring an authentication decision.

This test does not enforce authentication. It makes new application
routes visible during development so their security requirements
can be reviewed explicitly.
"""

from app.main import app


PUBLIC_PATHS = {
    "/api/v1/health",
    "/api/v1/auth/sign-in",
}

PROTECTED_PATHS = {
    "/api/v1/auth/logout",
    "/api/v1/auth/me",
    "/api/v1/clients",
    "/api/v1/clients/{client_id}",
    "/api/v1/projects",
    "/api/v1/projects/{project_id}",
    "/api/v1/data-sources",
    "/api/v1/data-sources/{data_source_id}",
    "/api/v1/scans",
    "/api/v1/scans/{scan_id}",
    "/api/v1/source-objects",
    "/api/v1/source-objects/{source_object_id}",
    "/api/v1/data-fields",
    "/api/v1/data-fields/{data_field_id}",
    "/api/v1/discovery/csv",
    "/api/v1/discovery/excel",
    "/api/v1/discovery/postgresql",
    "/api/v1/discovery/sqlserver",
    "/api/v1/profiling-results",
    "/api/v1/profiling-results/{profiling_result_id}",
    "/api/v1/dictionary",
    "/api/v1/field-governance/{data_field_id}",
}


def test_all_application_routes_have_security_classification():
    actual_paths = {
        route.path
        for route in app.routes
        if route.path.startswith("/api/v1/")
    }

    classified_paths = PUBLIC_PATHS | PROTECTED_PATHS

    assert actual_paths == classified_paths, (
        "Application route inventory changed. Review the security "
        "requirements of added or removed routes."
    )


def test_public_and_protected_routes_do_not_overlap():
    assert PUBLIC_PATHS.isdisjoint(PROTECTED_PATHS)


def test_only_approved_routes_are_public():
    assert PUBLIC_PATHS == {
        "/api/v1/health",
        "/api/v1/auth/sign-in",
    }