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
