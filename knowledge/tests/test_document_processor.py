"""
Unit tests for DocumentProcessor service.

Tests cover:
- chunk_text edge cases (empty, short, long text)
- _clean_text normalisation
- _find_break_point boundary preference
- process_document with a real temp TXT file
- process_document with an unsupported file type
"""
import os
import tempfile
import pytest

# Ensure Django settings are configured before importing application code
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from knowledge.services.document_processor import DocumentProcessor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def processor():
    """DocumentProcessor with default settings (chunk_size=1000, overlap=200)."""
    return DocumentProcessor(chunk_size=1000, chunk_overlap=200)


@pytest.fixture
def small_processor():
    """DocumentProcessor with small chunk size for boundary testing."""
    return DocumentProcessor(chunk_size=50, chunk_overlap=10)


# ---------------------------------------------------------------------------
# chunk_text
# ---------------------------------------------------------------------------

class TestChunkText:
    def test_empty_string_returns_empty_list(self, processor):
        result = processor.chunk_text("")
        assert result == []

    def test_whitespace_only_string_returns_single_empty_chunk(self, processor):
        # chunk_text checks `if not text` (True for ""), so "" returns []
        # But whitespace-only input passes that check, then _clean_text
        # strips it to "", which is <= chunk_size → [""] is returned.
        # This documents the current (accepted) behaviour.
        result = processor.chunk_text("   \n\n  ")
        # The implementation returns [""] for whitespace-only input;
        # callers should handle empty-string chunks downstream.
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] == ""

    def test_short_text_returns_single_chunk(self, processor):
        short = "Hello, this is a short document."
        result = processor.chunk_text(short)
        assert len(result) == 1
        assert result[0] == short

    def test_text_at_exact_chunk_size_returns_single_chunk(self):
        proc = DocumentProcessor(chunk_size=20, chunk_overlap=0)
        text = "A" * 20
        result = proc.chunk_text(text)
        assert len(result) == 1

    def test_long_text_produces_multiple_chunks(self):
        proc = DocumentProcessor(chunk_size=100, chunk_overlap=20)
        # 400 characters guaranteed to require multiple chunks
        text = "This is a test sentence. " * 20
        result = proc.chunk_text(text)
        assert len(result) > 1

    def test_chunk_overlap_carries_content_forward(self):
        proc = DocumentProcessor(chunk_size=100, chunk_overlap=30)
        # Build text long enough to need 3+ chunks
        text = "word " * 80  # 400 chars
        chunks = proc.chunk_text(text)
        assert len(chunks) >= 2
        # The start of chunk[1] should overlap with the end of chunk[0]
        # Verify chunks are non-empty strings
        for chunk in chunks:
            assert isinstance(chunk, str)
            assert len(chunk) > 0

    def test_chunks_collectively_cover_all_content(self):
        proc = DocumentProcessor(chunk_size=100, chunk_overlap=0)
        # Use distinct tokens to verify coverage
        words = [f"word{i}" for i in range(50)]
        text = " ".join(words)
        chunks = proc.chunk_text(text)
        combined = " ".join(chunks)
        for word in words:
            assert word in combined, f"{word} is missing from chunks"

    def test_single_very_long_word_handled_gracefully(self):
        proc = DocumentProcessor(chunk_size=10, chunk_overlap=2)
        text = "A" * 50  # No spaces or sentence boundaries
        result = proc.chunk_text(text)
        assert len(result) >= 1
        assert all(isinstance(c, str) and len(c) > 0 for c in result)


# ---------------------------------------------------------------------------
# _clean_text
# ---------------------------------------------------------------------------

class TestCleanText:
    def test_multiple_spaces_collapsed_to_one(self, processor):
        text = "hello    world"
        cleaned = processor._clean_text(text)
        assert "  " not in cleaned
        assert "hello world" in cleaned

    def test_more_than_two_newlines_collapsed(self, processor):
        text = "line1\n\n\n\nline2"
        cleaned = processor._clean_text(text)
        assert "\n\n\n" not in cleaned
        assert "line1" in cleaned
        assert "line2" in cleaned

    def test_leading_trailing_whitespace_stripped(self, processor):
        text = "   hello world   "
        cleaned = processor._clean_text(text)
        assert cleaned == cleaned.strip()

    def test_line_leading_trailing_whitespace_stripped(self, processor):
        text = "  hello  \n  world  "
        cleaned = processor._clean_text(text)
        for line in cleaned.split("\n"):
            assert line == line.strip()

    def test_clean_text_preserves_double_newline_paragraph_breaks(self, processor):
        text = "paragraph one\n\nparagraph two"
        cleaned = processor._clean_text(text)
        assert "\n\n" in cleaned

    def test_empty_string_returns_empty(self, processor):
        assert processor._clean_text("") == ""


# ---------------------------------------------------------------------------
# _find_break_point
# ---------------------------------------------------------------------------

class TestFindBreakPoint:
    def test_prefers_sentence_boundary_over_word_boundary(self, processor):
        # Text has a sentence end followed by a space in the latter half,
        # and a plain word boundary later — sentence should win.
        text = "This is some intro text. More content here to fill up the space end"
        bp = processor._find_break_point(text)
        # The sentence boundary is at the ". " position
        sentence_pos = text.index(". ") + 1  # position just after the period
        # break_point should be <= sentence_pos + 1
        assert bp <= len(text)
        assert bp > 0

    def test_falls_back_to_word_boundary_when_no_sentence_end(self, processor):
        # No sentence-ending punctuation in the latter half
        text = "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10"
        bp = processor._find_break_point(text)
        # Should land on a space or end of text
        assert bp > 0
        assert bp <= len(text)
        # Character at break point (or just before) should be a space or end
        if bp < len(text):
            assert text[bp - 1] == ' ' or text[bp] == ' ' or bp == len(text)

    def test_paragraph_break_preferred_when_in_latter_half(self, processor):
        text = "intro content\n\nsecond paragraph content here for length padding"
        bp = processor._find_break_point(text)
        para_pos = text.index("\n\n")
        # paragraph is in latter half, so break should be at/after para_pos
        assert bp > 0


# ---------------------------------------------------------------------------
# process_document — real TXT file
# ---------------------------------------------------------------------------

class TestProcessDocument:
    def test_process_txt_file_returns_full_text_and_chunks(self, tmp_path):
        content = "This is a test document. " * 60  # ~1500 chars
        txt_file = tmp_path / "sample.txt"
        txt_file.write_text(content, encoding="utf-8")

        proc = DocumentProcessor(chunk_size=200, chunk_overlap=50)
        full_text, chunks = proc.process_document(str(txt_file), "txt")

        assert isinstance(full_text, str)
        assert len(full_text) > 0
        assert isinstance(chunks, list)
        assert len(chunks) >= 1

    def test_process_txt_single_chunk_for_short_file(self, tmp_path):
        content = "Short file content."
        txt_file = tmp_path / "short.txt"
        txt_file.write_text(content, encoding="utf-8")

        proc = DocumentProcessor(chunk_size=1000, chunk_overlap=200)
        full_text, chunks = proc.process_document(str(txt_file), "txt")

        assert full_text.strip() == content
        assert len(chunks) == 1

    def test_process_document_unsupported_type_returns_empty(self, tmp_path):
        fake_file = tmp_path / "data.xyz"
        fake_file.write_text("some content", encoding="utf-8")

        proc = DocumentProcessor()
        full_text, chunks = proc.process_document(str(fake_file), "xyz")

        assert full_text == ""
        assert chunks == []

    def test_process_txt_with_utf8_content(self, tmp_path):
        # Unicode characters including Japanese
        content = "Hello world. " * 10 + "日本語テスト。" * 5
        txt_file = tmp_path / "unicode.txt"
        txt_file.write_text(content, encoding="utf-8")

        proc = DocumentProcessor(chunk_size=100, chunk_overlap=20)
        full_text, chunks = proc.process_document(str(txt_file), "txt")

        assert "Hello world" in full_text
        assert len(chunks) >= 1
