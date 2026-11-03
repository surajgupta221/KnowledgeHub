"""Document chunking service for RAG pipeline."""

import logging

logger = logging.getLogger(__name__)


class ChunkingService:
    """Service for splitting documents into semantic chunks with overlap."""

    # Chunking configuration
    CHUNK_SIZE = 500  # Target tokens per chunk
    CHUNK_OVERLAP = 50  # Overlap between chunks (tokens)
    MIN_CHUNK_SIZE = 100  # Minimum tokens for a valid chunk

    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
        min_chunk_size: int = MIN_CHUNK_SIZE,
    ):
        """
        Initialize chunking service.

        Args:
            chunk_size: Target number of tokens per chunk
            chunk_overlap: Number of overlapping tokens between chunks
            min_chunk_size: Minimum chunk size (smaller chunks are dropped)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def chunk_text(self, text: str, document_id: int) -> list[dict]:
        """
        Split text into semantic chunks with overlap.

        Strategy:
        1. Split by paragraphs (double newline)
        2. Within paragraphs, split by sentences
        3. Group sentences into chunks (target: chunk_size tokens)
        4. Add overlap between consecutive chunks

        Args:
            text: Full document text
            document_id: ID of document being chunked (for metadata)

        Returns:
            List of chunk dicts: {
                'document_id': int,
                'sequence': int,
                'text': str,
                'token_estimate': int,
            }
        """
        if not text or not text.strip():
            logger.warning(
                "Empty text provided for chunking",
                extra={"document_id": document_id},
            )
            return []

        # Split into sentences (simple heuristic: split on . ! ? followed by space)
        sentences = self._split_sentences(text)

        if not sentences:
            logger.warning(
                "No sentences extracted from text",
                extra={"document_id": document_id},
            )
            return []

        # Group sentences into chunks
        chunks = self._group_sentences_into_chunks(sentences, document_id)

        logger.info(
            "Document chunked successfully",
            extra={
                "document_id": document_id,
                "chunk_count": len(chunks),
                "avg_tokens": (
                    sum(c["token_estimate"] for c in chunks) / len(chunks)
                    if chunks
                    else 0
                ),
            },
        )

        return chunks

    def _split_sentences(self, text: str) -> list[str]:
        """
        Split text into sentences.

        Simple heuristic: split on . ! ? followed by space or newline.
        Preserves punctuation in sentences.

        Args:
            text: Full text

        Returns:
            List of sentence strings (stripped)
        """
        # Replace multiple spaces/newlines with single space
        text = " ".join(text.split())

        # Split on sentence boundaries: . ! ? followed by space
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)

        # Filter empty sentences and strip whitespace
        sentences = [s.strip() for s in sentences if s.strip()]

        return sentences

    def _group_sentences_into_chunks(
        self, sentences: list[str], document_id: int
    ) -> list[dict]:
        """
        Group sentences into chunks with target size and overlap.

        Algorithm:
        1. Iterate through sentences, accumulating into current chunk
        2. When chunk reaches target size, save and start new chunk
        3. Add overlap: include last N tokens of previous chunk in new chunk
        4. Skip chunks smaller than min_chunk_size

        Args:
            sentences: List of sentences
            document_id: Document ID for metadata

        Returns:
            List of chunk dicts
        """
        chunks = []
        current_chunk_sentences = []
        current_chunk_tokens = 0

        for sentence in sentences:
            token_count = self._estimate_tokens(sentence)

            # Check if adding this sentence exceeds chunk size
            if current_chunk_tokens + token_count > self.chunk_size and current_chunk_sentences:
                # Save current chunk if it meets minimum size
                if current_chunk_tokens >= self.min_chunk_size:
                    chunk_text = " ".join(current_chunk_sentences)
                    chunks.append({
                        "document_id": document_id,
                        "sequence": len(chunks),
                        "text": chunk_text,
                        "token_estimate": current_chunk_tokens,
                    })

                # Start new chunk with overlap
                current_chunk_sentences, current_chunk_tokens = (
                    self._create_overlap_chunk(
                        current_chunk_sentences, sentences, sentences.index(sentence)
                    )
                )

            # Add sentence to current chunk
            current_chunk_sentences.append(sentence)
            current_chunk_tokens += token_count

        # Save final chunk if it meets minimum size, or if it is the only chunk
        # (a short document must still be searchable)
        if current_chunk_sentences and (
            current_chunk_tokens >= self.min_chunk_size or not chunks
        ):
            chunk_text = " ".join(current_chunk_sentences)
            chunks.append({
                "document_id": document_id,
                "sequence": len(chunks),
                "text": chunk_text,
                "token_estimate": current_chunk_tokens,
            })

        return chunks

    def _create_overlap_chunk(
        self, previous_sentences: list[str], all_sentences: list[str], current_index: int
    ) -> tuple[list[str], int]:
        """
        Create new chunk with overlap from previous chunk.

        Takes last N tokens of previous chunk and adds them to start of new chunk.

        Args:
            previous_sentences: Sentences from previous chunk
            all_sentences: All sentences in document
            current_index: Index of first sentence to add to new chunk

        Returns:
            Tuple of (new_chunk_sentences, token_count)
        """
        # Calculate overlap: how many sentences from end of previous chunk to keep
        overlap_sentences = []
        overlap_tokens = 0

        for sentence in reversed(previous_sentences):
            token_count = self._estimate_tokens(sentence)
            if overlap_tokens + token_count <= self.chunk_overlap:
                overlap_sentences.insert(0, sentence)
                overlap_tokens += token_count
            else:
                break

        # Start new chunk with overlap + first sentence of new chunk
        new_chunk_sentences = overlap_sentences
        new_chunk_tokens = overlap_tokens

        if current_index < len(all_sentences):
            new_chunk_sentences.append(all_sentences[current_index])
            new_chunk_tokens += self._estimate_tokens(all_sentences[current_index])

        return new_chunk_sentences, new_chunk_tokens

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Simple approximation: ~1 token per 4 characters (typical for English).
        Production should use tiktoken library.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        return max(1, len(text) // 4)
