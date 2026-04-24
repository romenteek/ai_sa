from io import BytesIO


def test_upload_document_creates_chunked_document(client) -> None:
    response = client.post(
        "/api/v1/documents/upload",
        data={"kind": "architecture"},
        files={"file": ("architecture.md", BytesIO(b"# Service A\nHandles orders"), "text/markdown")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "architecture.md"
    assert body["kind"] == "architecture"
    assert body["chunk_count"] >= 1
    assert len(body["chunks"]) >= 1
