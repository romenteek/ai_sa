from app.services.chunking import chunk_text, enumerate_chunks


def test_chunk_text_splits_long_text_with_overlap() -> None:
    text = " ".join(f"word{i}" for i in range(60))

    chunks = chunk_text(text=text, max_chunk_size=80, overlap=10)

    assert len(chunks) > 1
    assert all(chunks)


def test_enumerate_chunks_adds_index_and_token_estimate() -> None:
    items = enumerate_chunks(["alpha beta", "gamma"])

    assert items[0]["chunk_index"] == 0
    assert items[1]["chunk_index"] == 1
    assert items[0]["token_estimate"] >= 1
