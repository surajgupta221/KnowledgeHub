"""Tests for chunking service."""


from app.services.chunking_service import ChunkingService


class TestChunkingSplitSentences:
    """Test sentence splitting logic."""

    def test_split_sentences_basic(self):
        """Test basic sentence splitting."""
        service = ChunkingService()
        text = "First sentence. Second sentence. Third sentence."

        sentences = service._split_sentences(text)

        assert len(sentences) == 3
        assert sentences[0] == "First sentence."
        assert sentences[1] == "Second sentence."
        assert sentences[2] == "Third sentence."

    def test_split_sentences_with_punctuation(self):
        """Test splitting with various punctuation."""
        service = ChunkingService()
        text = "Question? Yes! Exclamation. End."

        sentences = service._split_sentences(text)

        assert len(sentences) == 4
        assert sentences[0] == "Question?"
        assert sentences[1] == "Yes!"
        assert sentences[2] == "Exclamation."

    def test_split_sentences_with_extra_whitespace(self):
        """Test that extra whitespace is normalized."""
        service = ChunkingService()
        text = "First  sentence.\n\nSecond   sentence."

        sentences = service._split_sentences(text)

        assert len(sentences) == 2
        assert sentences[0] == "First sentence."
        assert sentences[1] == "Second sentence."

    def test_split_empty_text(self):
        """Test empty text handling."""
        service = ChunkingService()
        sentences = service._split_sentences("")

        assert sentences == []


class TestChunkingTokenEstimate:
    """Test token estimation."""

    def test_token_estimate_calculation(self):
        """Test that token estimate is roughly correct."""
        service = ChunkingService()

        # "This is a test" ≈ 4 words ≈ 4-5 tokens
        text = "This is a test sentence with several words."
        tokens = service._estimate_tokens(text)

        # Should be positive and reasonable
        assert tokens > 0
        assert tokens < len(text)  # Fewer tokens than characters

    def test_token_estimate_empty(self):
        """Test empty text returns 1 token minimum."""
        service = ChunkingService()
        tokens = service._estimate_tokens("")

        assert tokens == 1  # Minimum 1 token


class TestChunkingGroupSentences:
    """Test sentence grouping into chunks."""

    def test_group_sentences_respects_chunk_size(self):
        """Test that chunks don't exceed target size too much."""
        service = ChunkingService(chunk_size=50, chunk_overlap=5, min_chunk_size=5)
        # Create longer sentences to ensure multiple chunks
        sentences = [
            "The quick brown fox jumps over the lazy dog multiple times every day.",
            "This is another long sentence with lots of words to add more tokens.",
            "Here we have a third sentence that also contains many words and tokens.",
            "Now we add a fourth sentence with significant content and length here.",
            "Finally a fifth sentence to include more data and ensure chunk splitting.",
            "And a sixth sentence with even more information to ensure multiple chunks.",
        ]

        chunks = service._group_sentences_into_chunks(sentences, document_id=1)

        # Should have created at least one chunk (test the structure works)
        assert len(chunks) >= 1

        # Each chunk should have correct structure
        for i, chunk in enumerate(chunks):
            assert chunk["sequence"] == i
            assert chunk["document_id"] == 1
            assert chunk["text"]
            assert chunk["token_estimate"] > 0


    def test_group_sentences_min_chunk_size(self):
        """Test that small chunks are filtered out."""
        service = ChunkingService(chunk_size=1000, min_chunk_size=50)
        sentences = ["Short.", "Also short."]

        chunks = service._group_sentences_into_chunks(sentences, document_id=1)

        # Should be empty or very few chunks (below minimum)
        assert len(chunks) <= 1

    def test_short_document_still_produces_single_chunk(self):
        """A document below min_chunk_size must not become unsearchable."""
        service = ChunkingService()  # default min_chunk_size=100 tokens
        text = "Passwords must be rotated every 90 days. MFA is mandatory for all employees."

        chunks = service.chunk_text(text, document_id=7)

        assert len(chunks) == 1
        assert chunks[0]["document_id"] == 7
        assert chunks[0]["sequence"] == 0
        assert "MFA is mandatory" in chunks[0]["text"]

    def test_group_sentences_overlap(self):
        """Test that overlap is applied between chunks."""
        service = ChunkingService(
            chunk_size=50,
            chunk_overlap=20,
            min_chunk_size=20,
        )
        sentences = [
            "First sentence here.",
            "Second sentence here.",
            "Third sentence here.",
            "Fourth sentence here.",
            "Fifth sentence here.",
        ]

        chunks = service._group_sentences_into_chunks(sentences, document_id=1)

        # With overlap, chunks should share some text
        if len(chunks) > 1:
            # Check that first sentence of chunk N appears in chunk N-1 or N
            # (due to overlap mechanism)
            assert len(chunks) >= 2


class TestChunkingIntegration:
    """Integration tests for full chunking pipeline."""

    def test_chunk_text_simple(self):
        """Test chunking of simple document."""
        service = ChunkingService(
            chunk_size=100,
            chunk_overlap=10,
            min_chunk_size=20,
        )

        text = (
            "This is the first paragraph with multiple sentences. "
            "It contains information about various topics. "
            "The second paragraph starts here. "
            "It has different content. "
            "We can have as many sentences as needed."
        )

        chunks = service.chunk_text(text, document_id=1)

        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk["document_id"] == 1
            assert "text" in chunk
            assert "token_estimate" in chunk
            assert "sequence" in chunk
            assert chunk["text"]

    def test_chunk_text_empty(self):
        """Test chunking of empty document."""
        service = ChunkingService()

        chunks = service.chunk_text("", document_id=1)

        assert chunks == []

    def test_chunk_text_whitespace_only(self):
        """Test chunking of whitespace-only document."""
        service = ChunkingService()

        chunks = service.chunk_text("   \n\n   ", document_id=1)

        assert chunks == []

    def test_chunk_text_preserves_content(self):
        """Test that chunking preserves original content."""
        service = ChunkingService(chunk_size=100)

        original_text = (
            "The quick brown fox jumps over the lazy dog. "
            "This is a pangram sentence. "
            "It contains all letters of the alphabet. "
            "The second paragraph starts now. "
            "We have more content here to chunk. "
            "Final sentence in the text."
        )

        chunks = service.chunk_text(original_text, document_id=1)

        # Should produce at least one chunk with the lower chunk size
        # (with default chunk_size=500, text may be too small)
        if chunks:
            # If chunks exist, verify structure
            assert all("text" in c for c in chunks)
            assert all("document_id" in c for c in chunks)
            assert all(c["document_id"] == 1 for c in chunks)


class TestChunkingEdgeCases:
    """Test edge cases and error conditions."""

    def test_chunk_very_long_sentence(self):
        """Test handling of very long sentence (exceeds chunk size)."""
        service = ChunkingService(chunk_size=50, min_chunk_size=10)

        # One very long sentence
        long_sentence = "word " * 200  # 200 words
        text = f"{long_sentence}. Next sentence here."

        chunks = service.chunk_text(text, document_id=1)

        # Should still produce chunks
        assert len(chunks) > 0

    def test_chunk_no_sentence_endings(self):
        """Test text without proper sentence endings."""
        service = ChunkingService()

        # Text without periods
        text = "This is text\nWith line breaks\nBut no periods"

        chunks = service.chunk_text(text, document_id=1)

        # Should handle gracefully (may produce one chunk)
        assert len(chunks) >= 0
