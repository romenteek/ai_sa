from io import BytesIO


def test_create_analysis_run_returns_strict_contract_and_persists_run(client) -> None:
    upload_response = client.post(
        "/api/v1/documents/upload",
        data={"kind": "specification"},
        files={
            "file": (
                "analysis.md",
                BytesIO(
                    b"""
                    The analysis API must preserve source references and confidence.
                    Backend services should store analysis runs in PostgreSQL.
                    QA should validate the strict JSON contract for analysis responses.
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
            "query": "Implement analysis run retrieval",
            "document_ids": [document_id],
            "max_chunks": 5,
        },
    )

    assert create_response.status_code == 201
    body = create_response.json()
    assert body["status"] == "completed"
    assert body["review_status"] == "draft"
    assert body["reviewer_note"] == ""
    assert body["document_id"] == document_id
    assert body["feature_summary"]
    assert isinstance(body["backend_tasks"], list)
    assert isinstance(body["frontend_tasks"], list)
    assert isinstance(body["integration_tasks"], list)
    assert isinstance(body["db_changes"], list)
    assert isinstance(body["qa_tasks"], list)
    assert isinstance(body["observability_tasks"], list)
    assert isinstance(body["risks"], list)
    assert isinstance(body["open_questions"], list)
    assert isinstance(body["assumptions"], list)
    assert isinstance(body["source_references"], list)
    assert body["source_references"]
    assert "Vector similarity available: no" in body["validation_notes"]
    assert 0 <= body["confidence"] <= 1

    first_task = body["backend_tasks"][0]
    assert set(first_task) >= {
        "title",
        "description",
        "why_needed",
        "service_or_component",
        "acceptance_criteria",
        "dependencies",
        "assumptions",
        "source_refs",
        "confidence",
    }
    assert first_task["source_refs"]

    get_response = client.get(f"/api/v1/analysis-runs/{body['id']}")
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["id"] == body["id"]
    assert fetched["source_references"] == body["source_references"]

    list_response = client.get("/api/v1/analysis-runs")
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body[0]["id"] == body["id"]
    assert list_body[0]["review_status"] == "draft"


def test_create_analysis_run_keeps_open_questions_when_context_is_insufficient(client) -> None:
    upload_response = client.post(
        "/api/v1/documents/upload",
        data={"kind": "specification"},
        files={"file": ("empty.md", BytesIO(b"Only a short note."), "text/markdown")},
    )
    document_id = upload_response.json()["id"]

    response = client.post(
        "/api/v1/analysis-runs",
        json={
            "query": "Distributed tracing rollout",
            "document_ids": [document_id],
            "max_chunks": 2,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["open_questions"]
    assert body["assumptions"]
    assert body["qa_tasks"]


def test_update_analysis_run_review_status_and_note(client) -> None:
    upload_response = client.post(
        "/api/v1/documents/upload",
        data={"kind": "specification"},
        files={
            "file": (
                "review.md",
                BytesIO(b"Backend endpoint changes need approval before export."),
                "text/markdown",
            )
        },
    )
    document_id = upload_response.json()["id"]

    create_response = client.post(
        "/api/v1/analysis-runs",
        json={"query": "Approval workflow", "document_ids": [document_id], "max_chunks": 3},
    )
    analysis_run_id = create_response.json()["id"]

    review_response = client.patch(
        f"/api/v1/analysis-runs/{analysis_run_id}/review",
        json={
            "review_status": "reviewed",
            "reviewer_note": "Looks grounded. Waiting for PM confirmation on one open question.",
        },
    )

    assert review_response.status_code == 200
    body = review_response.json()
    assert body["review_status"] == "reviewed"
    assert body["reviewer_note"] == "Looks grounded. Waiting for PM confirmation on one open question."

    fetch_response = client.get(f"/api/v1/analysis-runs/{analysis_run_id}")
    assert fetch_response.status_code == 200
    fetched = fetch_response.json()
    assert fetched["review_status"] == "reviewed"
    assert fetched["reviewer_note"] == body["reviewer_note"]
