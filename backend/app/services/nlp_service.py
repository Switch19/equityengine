"""
Shared spaCy infrastructure. Loading a spaCy model takes noticeable
time (usually 0.5-2 seconds), so it is loaded once per process and
cached, not reloaded on every request.
"""
from functools import lru_cache

import spacy
from spacy.matcher import PhraseMatcher


@lru_cache(maxsize=1)
def get_nlp():
    """
    Returns the shared spaCy pipeline instance. Cached so this only
    runs once no matter how many times it's called across the app.
    """
    return spacy.load("en_core_web_sm")


def build_phrase_matcher(phrases: list[str]) -> PhraseMatcher:
    """
    Builds a case-insensitive PhraseMatcher for a fixed list of
    phrases (skills, institution names, etc.). Matching is
    case-insensitive (attr="LOWER") so "python" in a CV matches
    "Python" in the taxonomy.
    """
    nlp = get_nlp()
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    patterns = [nlp.make_doc(phrase) for phrase in phrases]
    matcher.add("PHRASES", patterns)
    return matcher


def find_phrase_matches(text: str, matcher: PhraseMatcher) -> set[str]:
    """
    Runs a pre-built PhraseMatcher over text and returns the set of
    matched surface strings (deduplicated, as they appeared in the
    original text — case as typed by the candidate, not the taxonomy).
    """
    nlp = get_nlp()
    doc = nlp(text)
    matches = matcher(doc)
    return {doc[start:end].text for _, start, end in matches}
