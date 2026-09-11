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
from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:  # import cost paid only by type checkers, never at runtime
    import numpy as np
    from sentence_transformers import SentenceTransformer


@lru_cache(maxsize=1)
def get_embedding_model() -> "SentenceTransformer":
    """
    Loaded once per process (model loading takes real time — usually
    1-3 seconds for a model this size). If this raises an error on
    startup, the most likely cause is EMBEDDING_MODEL_PATH in .env not
    pointing at the actual folder containing the downloaded model
    files (config.json, pytorch_model.bin, etc.) relative to wherever
    you run `uvicorn main:app` from.

    The `sentence_transformers` import lives INSIDE this function on
    purpose. At module scope it pulls in the whole transformers stack
    (torch included) the moment anything imports this module — and
    since competency_engine imports it, that meant every single
    `import main` paid a multi-minute import scan before the app even
    started building routes. Deferring it here keeps that cost on the
    first request that actually needs an embedding, where the model
    load itself already dominates, and lru_cache means it is paid once.
    """
    from sentence_transformers import SentenceTransformer

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
    # numpy is imported here for the same reason as sentence_transformers
    # above: competency_engine imports this module, so a top-level
    # `import numpy` charged every `import main` for array-library
    # startup — including tooling runs that never compute a similarity.
    # The annotations above stay valid unquoted because of the
    # `from __future__ import annotations` at the top of the file, and
    # sys.modules caches the import so repeat calls are a dict lookup.
    import numpy as np

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
    return best_match_similarity_batch([candidate_texts], reference_texts)[0]


def best_match_similarity_batch(
    candidate_text_groups: list[list[str]], reference_texts: list[str]
) -> list[float]:
    """
    best_match_similarity() for SEVERAL candidates against the SAME
    references, returning one score per group in the order given.

    Same scoring rule as the single-group version — which delegates
    here, so the rule has exactly one implementation — but the model is
    invoked twice in total rather than twice per candidate. That matters
    wherever a group of candidates is scored against one job: comparing
    a rejected applicant against the median of everyone advanced for
    that job (see feedback_service.py) would otherwise re-encode the
    job's requirements once per peer, which is the dominant cost.
    """
    reference_texts = [t for t in reference_texts if t and t.strip()]
    cleaned_groups = [[t for t in group if t and t.strip()] for group in candidate_text_groups]

    flattened = [text for group in cleaned_groups for text in group]
    if not reference_texts or not flattened:
        return [0.0] * len(cleaned_groups)

    reference_embeddings = encode_texts(reference_texts)
    # One encode call for every candidate text across every group.
    # Encoding is per-text and order-preserving, so slicing this back
    # apart below is equivalent to having encoded each group alone.
    candidate_embeddings = encode_texts(flattened)

    scores: list[float] = []
    cursor = 0
    for group in cleaned_groups:
        if not group:
            # A candidate with no project or repo descriptions at all —
            # expected for a sparse profile, scored 0.0 rather than
            # treated as an error (same as the single-group path).
            scores.append(0.0)
            continue

        group_embeddings = candidate_embeddings[cursor:cursor + len(group)]
        cursor += len(group)

        # Since both sets of embeddings are normalised, this matrix
        # multiplication IS the pairwise cosine similarity matrix, shape
        # (num_candidate_texts, num_reference_texts).
        similarity_matrix = group_embeddings @ reference_embeddings.T
        # For each reference (column), the best-matching candidate text —
        # i.e. max down each column, not across each row.
        scores.append(float(similarity_matrix.max(axis=0).mean()))

    return scores
