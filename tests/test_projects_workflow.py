from io import BytesIO


def test_project_creation_and_listing(client) -> None:
    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Customer Portal",
            "description": "Primary customer-facing project",
            "source_type": "github",
            "repository_url": "https://github.com/example/customer-portal",
        },
    )

    assert create_response.status_code == 201
    body = create_response.json()
    assert body["name"] == "Customer Portal"
    assert body["source_type"] == "github"
    assert body["ingestion_status"] == "not_started"
    assert "future ingestion boundary" in body["ingestion_note"]

    list_response = client.get("/api/v1/projects")
    assert list_response.status_code == 200
    projects = list_response.json()
    assert projects[0]["id"] == body["id"]
    assert projects[0]["analysis_count"] == 0


def test_request_requires_project_and_task_type(client) -> None:
    response = client.post(
        "/api/v1/analysis-runs",
        json={
            "query": "Missing project",
            "document_ids": [],
        },
    )

    assert response.status_code == 422


def test_clarification_round_can_repeat_then_complete_and_appear_in_results(client) -> None:
    project_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Ops Console",
            "source_type": "github",
            "repository_url": "https://github.com/example/ops-console",
        },
    )
    project_id = project_response.json()["id"]
    upload_response = client.post(
        "/api/v1/documents/upload",
        data={"kind": "specification"},
        files={"file": ("note.md", BytesIO(b"Only a short note."), "text/markdown")},
    )
    document_id = upload_response.json()["id"]

    create_response = client.post(
        "/api/v1/analysis-runs",
        json={
            "project_id": project_id,
            "task_type": "bug",
            "input_type": "text",
            "input_text": "Login occasionally fails.",
            "query": "Investigate login failure",
            "document_ids": [document_id],
            "max_chunks": 2,
        },
    )
    assert create_response.status_code == 201
    run = create_response.json()
    assert run["status"] == "needs_clarification"
    assert len(run["clarification_rounds"]) == 1

    unclear_response = client.post(
        f"/api/v1/analysis-runs/{run['id']}/clarifications",
        json={"answers": "Unknown reproduction steps. TBD owner and expected behavior."},
    )
    assert unclear_response.status_code == 200
    unclear_body = unclear_response.json()
    assert unclear_body["status"] == "needs_clarification"
    assert len(unclear_body["clarification_rounds"]) == 2

    final_response = client.post(
        f"/api/v1/analysis-runs/{run['id']}/clarifications",
        json={
            "answers": (
                "Actual: login returns 500 after password reset. Expected: user reaches the dashboard. "
                "Repro: reset password, follow email link, submit new password, then sign in. "
                "Acceptance: no 500s, audit event is recorded, and regression coverage exists."
            )
        },
    )
    assert final_response.status_code == 200
    completed = final_response.json()
    assert completed["status"] == "completed"
    assert completed["qa_tasks"]

    results_response = client.get("/api/v1/analysis-runs/results")
    assert results_response.status_code == 200
    results = results_response.json()
    assert results[0]["id"] == run["id"]
    assert results[0]["project_name"] == "Ops Console"
    assert results[0]["task_type"] == "bug"
