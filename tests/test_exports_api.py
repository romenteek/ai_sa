from io import BytesIO


def _create_analysis_run(client):
    project_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Export Project",
            "source_type": "github",
            "repository_url": "https://github.com/example/export-project",
        },
    )
    project_id = project_response.json()["id"]
    upload_response = client.post(
        "/api/v1/documents/upload",
        data={"kind": "specification"},
        files={
            "file": (
                "export.md",
                BytesIO(
                    b"""
                    Backend work must preserve source references and confidence.
                    Acceptance criteria should remain explicit in review outputs.
                    Open questions should be visible before any Jira export.
                    """
                ),
                "text/markdown",
            )
        },
    )
    document_id = upload_response.json()["id"]
    create_response = client.post(
        "/api/v1/analysis-runs",
        json={
            "project_id": project_id,
            "task_type": "technical_task",
            "input_type": "text",
            "input_text": "Prepare Jira export preview with explicit acceptance criteria.",
            "query": "Prepare Jira export",
            "document_ids": [document_id],
            "max_chunks": 4,
        },
    )
    return create_response.json()


def test_jira_export_preview_includes_payload_and_dry_run_mode(client) -> None:
    run = _create_analysis_run(client)

    review_response = client.patch(
        f"/api/v1/analysis-runs/{run['id']}/review",
        json={"review_status": "approved", "reviewer_note": "Approved for manual export preview."},
    )
    assert review_response.status_code == 200

    preview_response = client.post(
        "/api/v1/exports/jira/preview",
        json={"analysis_run_id": run["id"], "project_key": "AISA", "issue_type": "Task"},
    )

    assert preview_response.status_code == 200
    body = preview_response.json()
    assert body["status"] == "preview"
    assert body["export_allowed"] is True
    assert body["export_mode"] == "dry_run"
    assert body["payload"]["project_key"] == "AISA"
    assert body["payload"]["issue_type"] == "Task"
    assert body["payload"]["review_status"] == "approved"
    assert body["payload"]["reviewer_note"] == "Approved for manual export preview."
    assert body["payload"]["source_references"]
    assert body["payload"]["confidence"] >= 0
    assert body["jira_payload"]["fields"]["summary"]


def test_jira_export_is_blocked_until_review_is_approved(client) -> None:
    run = _create_analysis_run(client)

    response = client.post(
        "/api/v1/exports/jira",
        json={
            "analysis_run_id": run["id"],
            "project_key": "AISA",
            "issue_type": "Task",
            "confirm": True,
        },
    )

    assert response.status_code == 400
    assert "Only approved analysis runs can be exported to Jira." in response.json()["detail"]


def test_jira_export_confirmed_run_stays_dry_run_without_live_config(client) -> None:
    run = _create_analysis_run(client)
    client.patch(
        f"/api/v1/analysis-runs/{run['id']}/review",
        json={"review_status": "approved", "reviewer_note": "Ready for export."},
    )

    response = client.post(
        "/api/v1/exports/jira",
        json={
            "analysis_run_id": run["id"],
            "project_key": "AISA",
            "issue_type": "Task",
            "confirm": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "dry_run"
    assert body["export_allowed"] is True
    assert body["export_mode"] == "dry_run"
    assert body["payload"]["review_status"] == "approved"
    assert "Jira is not fully configured" in body["message"]
