from collections.abc import Iterable


def chunk_text(text: str, max_chunk_size: int, overlap: int) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []

    if overlap >= max_chunk_size:
        raise ValueError("Chunk overlap must be smaller than max chunk size.")

    chunks: list[str] = []
    start = 0
    length = len(normalized)

    while start < length:
        end = min(start + max_chunk_size, length)
        if end < length:
            split_at = normalized.rfind(" ", start, end)
            if split_at > start:
                end = split_at

        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= length:
            break

        start = max(0, end - overlap)

    return chunks


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def enumerate_chunks(chunks: Iterable[str]) -> list[dict]:
    return [
        {
            "chunk_index": index,
            "text": chunk,
            "token_estimate": estimate_tokens(chunk),
        }
        for index, chunk in enumerate(chunks)
    ]
