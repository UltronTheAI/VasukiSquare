"""Deduplication and near-duplicate detection for research documents."""

import re
from typing import List, Set
from vasukisquare.research.models import SourceDocument, normalize_url


def tokenize_text(text: str) -> Set[str]:
    """Tokenize text into lowercase alphanumeric words for similarity comparison."""
    words = re.findall(r"\b[a-zA-Z0-9_]{3,}\b", text.lower())
    return set(words)


def get_shingles(text: str, k: int = 3) -> Set[str]:
    """Generate k-word shingles from text."""
    words = re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower())
    if len(words) < k:
        return set(words)
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    if union == 0:
        return 0.0
    return intersection / union


def is_near_duplicate(text_a: str, text_b: str, threshold: float = 0.80) -> bool:
    """Determine if two texts are near-duplicates using shingle and token Jaccard similarity."""
    if not text_a or not text_b:
        return False
    # If identical length and text
    if text_a.strip() == text_b.strip():
        return True

    # Word tokens
    tokens_a = tokenize_text(text_a)
    tokens_b = tokenize_text(text_b)
    token_sim = jaccard_similarity(tokens_a, tokens_b)
    if token_sim >= threshold:
        return True

    # Shingles
    shingles_a = get_shingles(text_a, k=3)
    shingles_b = get_shingles(text_b, k=3)
    shingle_sim = jaccard_similarity(shingles_a, shingles_b)
    return shingle_sim >= threshold


class DeduplicationService:
    """Service to prune exact URL duplicates and near-duplicate document contents."""

    def __init__(self, near_duplicate_threshold: float = 0.80):
        self.near_duplicate_threshold = near_duplicate_threshold

    def deduplicate(self, documents: List[SourceDocument]) -> List[SourceDocument]:
        """Perform two-phase deduplication: exact URL filtering followed by near-duplicate text pruning."""
        if not documents:
            return []

        # Phase 1: Exact URL deduplication (keep the one with higher reliability / longer text)
        url_map: dict[str, SourceDocument] = {}
        for doc in documents:
            norm_url = normalize_url(doc.url)
            if norm_url not in url_map:
                url_map[norm_url] = doc
            else:
                existing = url_map[norm_url]
                # Keep the more informative document
                if len(doc.extracted_text) > len(existing.extracted_text):
                    url_map[norm_url] = doc

        unique_by_url = list(url_map.values())

        # Phase 2: Near-duplicate content pruning
        pruned_docs: List[SourceDocument] = []
        for doc in unique_by_url:
            is_dup = False
            for kept in pruned_docs:
                if is_near_duplicate(
                    doc.extracted_text or doc.title,
                    kept.extracted_text or kept.title,
                    threshold=self.near_duplicate_threshold,
                ):
                    is_dup = True
                    # If this doc is higher reliability, replace
                    if doc.reliability_score > kept.reliability_score:
                        pruned_docs.remove(kept)
                        pruned_docs.append(doc)
                    break
            if not is_dup:
                pruned_docs.append(doc)

        return pruned_docs

