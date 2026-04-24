from io import BytesIO


def test_ui_language_switcher_persists_russian_cookie(client) -> None:
    response = client.get("/projects?lang=ru")

    assert response.status_code == 200
    assert response.cookies.get("ui_lang") == "ru"
    assert "Проекты" in response.text
    assert "Новый анализ" in response.text

    followup = client.get("/analysis-runs/new")
    assert followup.status_code == 200
    assert "Создать запрос анализа" in followup.text
    assert "Выберите проект" in followup.text


def test_russian_request_gets_russian_clarification_and_final_result(client) -> None:
    project_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Портал клиента",
            "source_type": "github",
            "repository_url": "https://github.com/example/customer-portal",
        },
    )
    project_id = project_response.json()["id"]

    upload_response = client.post(
        "/api/v1/documents/upload",
        data={"kind": "specification"},
        files={
            "file": (
                "ru-note.md",
                BytesIO("Короткая заметка о входе пользователя.".encode("utf-8")),
                "text/markdown",
            )
        },
    )
    document_id = upload_response.json()["id"]

    create_response = client.post(
        "/api/v1/analysis-runs",
        json={
            "project_id": project_id,
            "task_type": "bug",
            "input_type": "text",
            "input_text": "После сброса пароля пользователь иногда не может войти.",
            "query": "Разобрать ошибку входа после сброса пароля",
            "document_ids": [document_id],
            "max_chunks": 2,
        },
    )

    assert create_response.status_code == 201
    run = create_response.json()
    assert run["language"] == "ru"
    assert run["status"] == "needs_clarification"
    assert "Каковы фактическое поведение" in " ".join(run["clarification"]["clarifying_questions"])

    answer_response = client.post(
        f"/api/v1/analysis-runs/{run['id']}/clarifications",
        json={
            "answers": (
                "Фактическое поведение: после перехода из письма вход возвращает 500. "
                "Ожидаемое поведение: пользователь попадает в личный кабинет. "
                "Шаги воспроизведения: сбросить пароль, открыть ссылку из письма, задать пароль и войти. "
                "Критерии приемки: нет 500, пишется audit event, есть регрессионный тест."
            )
        },
    )

    assert answer_response.status_code == 200
    completed = answer_response.json()
    assert completed["status"] == "completed"
    assert completed["language"] == "ru"
    assert "Найден подтвержденный контекст" in completed["feature_summary"]
    assert completed["qa_tasks"][0]["title"].startswith("Добавить покрытие")


def test_server_rendered_end_to_end_workflow_pages(client) -> None:
    project_response = client.post(
        "/projects",
        data={
            "name": "E2E Console",
            "source_type": "github",
            "repository_url": "https://github.com/example/e2e-console",
        },
        follow_redirects=False,
    )
    assert project_response.status_code == 303
    project_location = project_response.headers["location"]

    document_response = client.post(
        "/documents/upload",
        data={"kind": "specification"},
        files={
            "file": (
                "workflow.md",
                BytesIO(
                    b"""
                    Backend API and frontend UI must preserve source references.
                    Acceptance criteria must cover the final result page and export preview.
                    """
                ),
                "text/markdown",
            )
        },
        follow_redirects=False,
    )
    assert document_response.status_code == 303
    document_id = document_response.headers["location"].rsplit("/", 1)[-1]
    project_id = project_location.rsplit("/", 1)[-1]

    create_response = client.post(
        "/analysis-runs",
        data={
            "project_id": project_id,
            "task_type": "feature",
            "input_text": "Create a workflow result with acceptance criteria.",
            "query": "Workflow final result",
            "document_ids": document_id,
            "max_chunks": "4",
        },
        follow_redirects=False,
    )

    assert create_response.status_code == 303
    detail_location = create_response.headers["location"]
    detail_response = client.get(detail_location)
    assert detail_response.status_code == 200
    assert "Generated task sections" in detail_response.text

    results_response = client.get("/results")
    assert results_response.status_code == 200
    assert "Workflow final result" in results_response.text

    export_response = client.get(f"{detail_location}/export")
    assert export_response.status_code == 200
    assert "Manual Jira Export" in export_response.text
