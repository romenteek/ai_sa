from io import BytesIO


def test_dashboard_and_documents_ui_routes_render(client) -> None:
    upload_response = client.post(
        "/documents/upload",
        data={"kind": "architecture"},
        files={"file": ("ui-doc.md", BytesIO(b"UI visible source references"), "text/markdown")},
        follow_redirects=True,
    )

    assert upload_response.status_code == 200
    assert "Create analysis run" in upload_response.text
    assert "ui-doc.md" in upload_response.text

    dashboard_response = client.get("/")
    assert dashboard_response.status_code == 200
    assert "Internal Review Dashboard" in dashboard_response.text
    assert "Recent Documents" in dashboard_response.text


def test_analysis_run_detail_ui_supports_review_updates(client) -> None:
    upload_response = client.post(
        "/api/v1/documents/upload",
        data={"kind": "specification"},
        files={
            "file": (
                "feature.md",
                BytesIO(
                    b"""
                    The backend API should preserve source references.
                    Frontend review pages must show confidence and assumptions.
                    """
                ),
                "text/markdown",
            )
        },
    )
    document_id = upload_response.json()["id"]

    create_response = client.post(
        "/analysis-runs",
        data={
            "query": "Review UI",
            "document_ids": document_id,
            "max_chunks": "4",
        },
        follow_redirects=False,
    )
    assert create_response.status_code == 303
    detail_location = create_response.headers["location"]

    detail_response = client.get(detail_location)
    assert detail_response.status_code == 200
    assert "Structured review output" in detail_response.text
    assert "Source references" in detail_response.text
    assert "Generated task sections" in detail_response.text

    review_response = client.post(
        f"{detail_location}/review",
        data={
            "review_status": "approved",
            "reviewer_note": "Approved for manual Jira preparation once export is implemented.",
        },
        follow_redirects=True,
    )
    assert review_response.status_code == 200
    assert "Review status updated." in review_response.text
    assert "approved" in review_response.text.lower()
    assert "Approved for manual Jira preparation once export is implemented." in review_response.text


def test_export_preview_ui_shows_payload_and_dry_run_confirmation(client) -> None:
    upload_response = client.post(
        "/api/v1/documents/upload",
        data={"kind": "specification"},
        files={
            "file": (
                "export-ui.md",
                BytesIO(
                    b"""
                    Jira exports should preserve assumptions, open questions, source references, and confidence.
                    Review approval must happen before any export execution.
                    """
                ),
                "text/markdown",
            )
        },
    )
    document_id = upload_response.json()["id"]

    create_response = client.post(
        "/analysis-runs",
        data={"query": "Export preview UI", "document_ids": document_id, "max_chunks": "4"},
        follow_redirects=False,
    )
    detail_location = create_response.headers["location"]

    client.post(
        f"{detail_location}/review",
        data={"review_status": "approved", "reviewer_note": "Approved for export preview."},
        follow_redirects=True,
    )

    preview_response = client.get(f"{detail_location}/export")
    assert preview_response.status_code == 200
    assert "Manual Jira Export" in preview_response.text
    assert "Human-readable export payload" in preview_response.text
    assert "Exact Jira payload preview" in preview_response.text

    export_response = client.post(
        f"{detail_location}/export",
        data={"project_key": "AISA", "issue_type": "Task", "confirm": "true"},
        follow_redirects=True,
    )
    assert export_response.status_code == 200
    assert "dry-run preview mode" in export_response.text
