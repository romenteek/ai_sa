from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.retrieval import RetrievalService


def test_search_chunks_ranks_text_matches_and_filters_by_metadata(db_session) -> None:
    checkout_doc = Document(
        filename="checkout.md",
        kind="architecture",
        content_type="text/markdown",
        storage_path="storage/checkout.md",
        checksum="checksum-a",
        source_metadata={"extension": ".md", "domain": "payments"},
        extracted_text="Checkout API handles payment authorization and order capture.",
        chunk_count=2,
    )
    checkout_doc.chunks = [
        DocumentChunk(
            chunk_index=0,
            text="The Checkout API handles payment authorization and order capture.",
            token_estimate=12,
            chunk_metadata={"kind": "architecture", "filename": "checkout.md"},
        ),
        DocumentChunk(
            chunk_index=1,
            text="Observability for checkout logs failed authorization attempts.",
            token_estimate=9,
            chunk_metadata={"kind": "architecture", "filename": "checkout.md"},
        ),
    ]
    auth_doc = Document(
        filename="auth.md",
        kind="architecture",
        content_type="text/markdown",
        storage_path="storage/auth.md",
        checksum="checksum-b",
        source_metadata={"extension": ".md", "domain": "identity"},
        extracted_text="Authentication service issues tokens.",
        chunk_count=1,
    )
    auth_doc.chunks = [
        DocumentChunk(
            chunk_index=0,
            text="Authentication service issues tokens for internal APIs.",
            token_estimate=8,
            chunk_metadata={"kind": "architecture", "filename": "auth.md"},
        )
    ]
    db_session.add_all([checkout_doc, auth_doc])
    db_session.commit()

    service = RetrievalService(db_session)
    results = service.search_chunks(
        query="payment authorization",
        metadata_filters={"domain": "payments"},
        limit=5,
    )

    assert len(results) == 2
    assert results[0].filename == "checkout.md"
    assert "payment authorization" in results[0].text.lower()
    assert all(result.filename == "checkout.md" for result in results)


def test_search_chunks_falls_back_to_filtered_chunks_when_query_has_no_match(db_session) -> None:
    spec_doc = Document(
        filename="analysis.md",
        kind="specification",
        content_type="text/markdown",
        storage_path="storage/analysis.md",
        checksum="checksum-c",
        source_metadata={"extension": ".md", "domain": "analytics"},
        extracted_text="Analysis API returns source references and confidence.",
        chunk_count=1,
    )
    spec_doc.chunks = [
        DocumentChunk(
            chunk_index=0,
            text="Analysis API returns source references and confidence.",
            token_estimate=8,
            chunk_metadata={"kind": "specification", "filename": "analysis.md"},
        )
    ]
    db_session.add(spec_doc)
    db_session.commit()

    service = RetrievalService(db_session)
    results = service.search_chunks(
        query="vector embeddings",
        document_kind="specification",
        limit=3,
    )

    assert len(results) == 1
    assert results[0].filename == "analysis.md"
    assert results[0].score == 0.0
