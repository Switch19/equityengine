"""
Semantic similarity via a locally hosted Sentence Transformers model
(all-MiniLM-L6-v2). No external API call — the model loads once from
disk (backend/models/all-MiniLM-L6-v2/) and stays in memory, which is
why EMBEDDING_MODEL_PATH points at a local folder, not a model name
that would trigger a download from the Hugging Face hub.

This is the P_emb component of the Evidence Score (40% weight — the
largest single component), so getting the similarity logic right
matters more than any other single piece of the scoring formula.
"""
from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import settings


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """
    Loaded once per process (model loading takes real time — usually
    1-3 seconds for a model this size). If this raises an error on
    startup, the most likely cause is EMBEDDING_MODEL_PATH in .env not
    pointing at the actual folder containing the downloaded model
    files (config.json, pytorch_model.bin, etc.) relative to wherever
    you run `uvicorn main:app` from.
    """
    return SentenceTransformer(settings.EMBEDDING_MODEL_PATH)


def encode_texts(texts: list[str]) -> np.ndarray:
    """
    Encodes a list of strings into normalised embedding vectors.
    normalize_embeddings=True means each vector has unit length, which
    is what allows cosine_similarity() below to be a plain dot product
    instead of needing to divide by vector norms every time.
    """
    model = get_embedding_model()
    return model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    return float(np.dot(vec_a, vec_b))


def semantic_similarity(text_a: str, text_b: str) -> float:
    """Similarity between two single pieces of text, e.g. one project
    description against one job description. Returns 0.0 for empty
    input rather than raising, since candidates with sparse profiles
    are an expected, common case, not an error condition."""
    if not text_a or not text_a.strip() or not text_b or not text_b.strip():
        return 0.0
    embeddings = encode_texts([text_a, text_b])
    return cosine_similarity(embeddings[0], embeddings[1])


def best_match_similarity(candidate_texts: list[str], reference_texts: list[str]) -> float:
    """
    Compares a GROUP of candidate texts (e.g. all of a candidate's
    project descriptions) against a group of reference texts (e.g. a
    job's required skills, or the candidate's own claimed skill list).

    For each REFERENCE item (each claimed skill, or each job
    requirement), finds the single best-matching candidate text, then
    averages those best-matches across references. This asks "for
    each thing you claim, is there at least one project that strongly
    supports it?" rather than "on average, how relevant are all your
    projects?" — the latter would unfairly penalise a candidate who
    has one excellent, highly relevant project alongside several
    unrelated hobby projects, since the unrelated ones would drag the
    average down even though they don't undermine the genuine evidence
    for the claimed skill. This is a deliberate design choice, not the
    only reasonable one — worth naming explicitly in Chapter 4 as a
    design decision with a stated rationale, since a plain average
    would be an equally defensible alternative with different
    trade-offs.
    """
    candidate_texts = [t for t in candidate_texts if t and t.strip()]
    reference_texts = [t for t in reference_texts if t and t.strip()]
    if not candidate_texts or not reference_texts:
        return 0.0

    candidate_embeddings = encode_texts(candidate_texts)
    reference_embeddings = encode_texts(reference_texts)

    # Since both sets of embeddings are normalised, this matrix
    # multiplication IS the pairwise cosine similarity matrix, shape
    # (num_candidate_texts, num_reference_texts).
    similarity_matrix = candidate_embeddings @ reference_embeddings.T
    # For each reference (column), the best-matching candidate text —
    # i.e. max down each column, not across each row.
    best_matches = similarity_matrix.max(axis=0)
    return float(best_matches.mean())
