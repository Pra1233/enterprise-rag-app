import logging
from functools import lru_cache

from langchain_text_splitters import RecursiveCharacterTextSplitter
from transformers import AutoTokenizer, PreTrainedTokenizerBase

from src.core.config import get_settings
from src.ingestion.parsers import ParsedDocument
from src.models.okf import DocumentMetadata, KnowledgeChunk, ParentChunk

logger = logging.getLogger(__name__)

PARENT_CHUNK_TOKENS = 1024
CHILD_CHUNK_TOKENS = 256
CHUNK_OVERLAP_RATIO = 0.1


@lru_cache
def _get_tokenizer() -> PreTrainedTokenizerBase:
    """Tokenizer matching the embedding model, so chunk sizes are measured in
    the same tokens the embedder will actually consume.
    """
    return AutoTokenizer.from_pretrained(get_settings().embedding_model)


def _token_length(text: str) -> int:
    return len(_get_tokenizer().encode(text, add_special_tokens=False))


def chunk_document(
    parsed: ParsedDocument, metadata: DocumentMetadata
) -> tuple[list[ParentChunk], list[KnowledgeChunk]]:
    """Parent-child (small-to-big) chunking.

    Splits the document into large parent chunks (~1024 tokens) kept in
    Postgres for LLM context, then splits each parent into small child
    chunks (~256 tokens) that get embedded and indexed in Qdrant for precise
    retrieval. Every child chunk links back to its parent via parent_doc_id.
    """
    full_text = "\n\n".join(page.text for page in parsed.pages if page.text)
    if not full_text.strip():
        logger.warning("Document %s has no extractable text; skipping chunking", metadata.document_id)
        return [], []

    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=PARENT_CHUNK_TOKENS,
        chunk_overlap=int(PARENT_CHUNK_TOKENS * CHUNK_OVERLAP_RATIO),
        length_function=_token_length,
    )
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHILD_CHUNK_TOKENS,
        chunk_overlap=int(CHILD_CHUNK_TOKENS * CHUNK_OVERLAP_RATIO),
        length_function=_token_length,
    )

    parent_chunks: list[ParentChunk] = []
    child_chunks: list[KnowledgeChunk] = []

    for parent_index, parent_text in enumerate(parent_splitter.split_text(full_text)):
        parent = ParentChunk(
            document_id=metadata.document_id,
            chunk_index=parent_index,
            content=parent_text,
            token_count=_token_length(parent_text),
            page_numbers=metadata.page_numbers,
        )
        parent_chunks.append(parent)

        for child_text in child_splitter.split_text(parent_text):
            child_chunks.append(KnowledgeChunk(parent_doc_id=parent.parent_id, content=child_text, metadata=metadata))

    logger.info(
        "Chunked document %s into %d parent chunks / %d child chunks",
        metadata.document_id,
        len(parent_chunks),
        len(child_chunks),
    )
    return parent_chunks, child_chunks
