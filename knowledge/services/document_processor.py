"""
Document Processor Service

Extracts text from uploaded documents and splits into chunks.
"""
import logging
import re
from typing import List, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Processes uploaded documents for the knowledge base.

    Handles:
    - Text extraction from PDF, TXT, DOCX
    - Chunking text for embedding
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        Args:
            chunk_size: Target size of each chunk in characters
            chunk_overlap: Overlap between chunks for context continuity
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def extract_text(self, file_path: str, file_type: str) -> str:
        """
        Extract text content from a document.

        Args:
            file_path: Path to the file
            file_type: File extension (pdf, txt, docx)

        Returns:
            Extracted text content
        """
        file_type = file_type.lower()

        try:
            if file_type == 'txt':
                return self._extract_txt(file_path)
            elif file_type == 'pdf':
                return self._extract_pdf(file_path)
            elif file_type in ('docx', 'doc'):
                return self._extract_docx(file_path)
            else:
                logger.warning(f"Unsupported file type: {file_type}")
                return ""
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            raise

    def _extract_txt(self, file_path: str) -> str:
        """Extract text from TXT file."""
        encodings = ['utf-8', 'latin-1', 'cp1252']

        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue

        raise ValueError("Could not decode text file")

    def _extract_pdf(self, file_path: str) -> str:
        """Extract text from PDF file."""
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(file_path)
            text_parts = []

            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            return '\n\n'.join(text_parts)

        except ImportError:
            logger.error("PyPDF2 not installed")
            raise
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            raise

    def _extract_docx(self, file_path: str) -> str:
        """Extract text from DOCX file."""
        try:
            from docx import Document

            doc = Document(file_path)
            text_parts = []

            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text)

            return '\n\n'.join(text_parts)

        except ImportError:
            logger.error("python-docx not installed")
            raise
        except Exception as e:
            logger.error(f"DOCX extraction error: {e}")
            raise

    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks.

        Uses sentence boundaries when possible for cleaner splits.

        Args:
            text: Full text to chunk

        Returns:
            List of text chunks
        """
        if not text:
            return []

        # Clean text
        text = self._clean_text(text)

        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            # Find end of chunk
            end = start + self.chunk_size

            if end >= len(text):
                # Last chunk
                chunks.append(text[start:].strip())
                break

            # Try to break at sentence boundary
            chunk_text = text[start:end]
            break_point = self._find_break_point(chunk_text)

            if break_point > 0:
                end = start + break_point

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start with overlap
            start = end - self.chunk_overlap

        return chunks

    def _find_break_point(self, text: str) -> int:
        """Find the best point to break text (sentence/paragraph boundary)."""
        # Look for paragraph break
        last_para = text.rfind('\n\n')
        if last_para > len(text) * 0.5:  # Must be in latter half
            return last_para + 2

        # Look for sentence end
        sentence_ends = ['.', '!', '?']
        for i in range(len(text) - 1, int(len(text) * 0.5), -1):
            if text[i] in sentence_ends and i + 1 < len(text) and text[i + 1] == ' ':
                return i + 1

        # Fall back to word boundary
        last_space = text.rfind(' ')
        if last_space > len(text) * 0.5:
            return last_space

        return len(text)

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Replace multiple newlines with double newline
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Replace multiple spaces with single space
        text = re.sub(r' {2,}', ' ', text)

        # Remove leading/trailing whitespace from lines
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)

        return text.strip()

    def process_document(self, file_path: str, file_type: str) -> Tuple[str, List[str]]:
        """
        Full document processing pipeline.

        Args:
            file_path: Path to the document
            file_type: File extension

        Returns:
            Tuple of (full_text, list_of_chunks)
        """
        # Extract text
        full_text = self.extract_text(file_path, file_type)

        # Chunk text
        chunks = self.chunk_text(full_text)

        logger.info(f"Processed document: {len(full_text)} chars -> {len(chunks)} chunks")

        return full_text, chunks
