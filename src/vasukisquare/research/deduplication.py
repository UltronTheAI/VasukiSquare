"""Deduplication and near-duplicate detection for research documents."""

import re
from typing import Any, Dict, List, Optional, Set
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


# ==============================================================================
# BOOK IDEA MULTI-LEVEL DEDUPLICATION
# ==============================================================================

STOP_WORDS = {
    "a", "an", "the", "and", "or", "in", "of", "to", "for", "with", "on", "at", "by",
    "from", "into", "about", "guide", "handbook", "complete", "practical", "introduction",
    "introductory", "getting", "started", "mastering", "essential", "essentials", "ultimate",
    "beginner", "beginners", "noob", "noobs", "zero", "hero", "learn", "learning",
    "building", "build", "modern", "deep", "dive", "basic", "basics", "fundamental",
    "fundamentals", "programming", "manual", "overview",
}


def normalize_title(title: str) -> str:
    """Normalize book title for collision and deduplication detection."""
    if not title:
        return ""
    cleaned = re.sub(r"[^\w\s]", " ", title.lower()).strip()
    words = [w for w in cleaned.split() if w not in STOP_WORDS and len(w) > 1]
    return " ".join(words)


def normalize_topic(topic: str) -> str:
    """Normalize topic string for deduplication."""
    if not topic:
        return ""
    cleaned = re.sub(r"[^\w\s]", " ", topic.lower()).strip()
    words = [w for w in cleaned.split() if w not in STOP_WORDS and len(w) > 1]
    return " ".join(words)


class IdeaDedupMatch:
    """Result of a candidate idea deduplication evaluation."""

    def __init__(
        self,
        is_duplicate: bool,
        reason: Optional[str] = None,
        similarity_score: float = 0.0,
        matched_record_id: Optional[str] = None,
        matched_title: Optional[str] = None,
        distinct_angle_accepted: bool = False,
    ):
        self.is_duplicate = is_duplicate
        self.reason = reason
        self.similarity_score = similarity_score
        self.matched_record_id = matched_record_id
        self.matched_title = matched_title
        self.distinct_angle_accepted = distinct_angle_accepted

    def to_dict(self) -> dict:
        return {
            "is_duplicate": self.is_duplicate,
            "reason": self.reason,
            "similarity_score": round(self.similarity_score, 3),
            "matched_record_id": self.matched_record_id,
            "matched_title": self.matched_title,
            "distinct_angle_accepted": self.distinct_angle_accepted,
        }


class IdeaDeduplicationService:
    """Multi-level deduplication engine comparing candidate ideas against historical MongoDB books and ideas."""

    def __init__(
        self,
        token_similarity_threshold: float = 0.75,
        shingle_similarity_threshold: float = 0.65,
    ):
        self.token_threshold = token_similarity_threshold
        self.shingle_threshold = shingle_similarity_threshold

    def has_distinct_angle(
        self,
        candidate_angle: str,
        candidate_summary: str,
        historical_angle: str,
        historical_summary: str,
    ) -> bool:
        """Evaluate whether a candidate on a similar subject has a genuinely distinct angle/focus."""
        cand_text = f"{candidate_angle} {candidate_summary}".strip()
        hist_text = f"{historical_angle} {historical_summary}".strip()
        if not cand_text or not hist_text:
            return False

        # Compare angle tokens (excluding common filler words)
        cand_angle_tokens = {w for w in tokenize_text(candidate_angle or candidate_summary) if w not in STOP_WORDS}
        hist_angle_tokens = {w for w in tokenize_text(historical_angle or historical_summary) if w not in STOP_WORDS}

        if not cand_angle_tokens or not hist_angle_tokens:
            return False

        common_tokens = cand_angle_tokens.intersection(hist_angle_tokens)
        cand_overlap_ratio = len(common_tokens) / len(cand_angle_tokens)
        jaccard = jaccard_similarity(cand_angle_tokens, hist_angle_tokens)

        # Genuinely distinct angles should share almost no angle-defining keywords (< 20% overlap and jaccard < 0.15)
        return cand_overlap_ratio < 0.20 and jaccard < 0.15

    def check_duplicate(
        self,
        candidate_title: str,
        candidate_topic: str,
        candidate_summary: str = "",
        candidate_angle: str = "",
        candidate_keywords: Optional[List[str]] = None,
        historical_records: Optional[List[Dict[str, Any]]] = None,
    ) -> IdeaDedupMatch:
        """Perform multi-level deduplication against historical books and ideas."""
        if not historical_records:
            return IdeaDedupMatch(is_duplicate=False, similarity_score=0.0)

        cand_title_norm = normalize_title(candidate_title)
        cand_topic_norm = normalize_topic(candidate_topic)
        cand_tokens = tokenize_text(f"{candidate_title} {candidate_topic} {candidate_summary}")
        if candidate_keywords:
            cand_tokens.update(tokenize_text(" ".join(candidate_keywords)))
        cand_shingles = get_shingles(f"{candidate_title} {candidate_summary}", k=2)

        highest_sim = 0.0
        best_match_title = None
        best_match_id = None

        for rec in historical_records:
            rec_id = str(rec.get("id") or rec.get("_id") or "")
            rec_title = rec.get("title", "")
            rec_topic = rec.get("topic", "") or rec_title
            rec_summary = rec.get("summary", "") or rec.get("description", "")
            rec_angle = rec.get("angle", "")
            rec_status = rec.get("status", "ready")

            # Ignore previously rejected ideas unless they were rejected for being low quality
            if rec_status == "rejected" and "duplicate" in (rec.get("rejection_reason") or "").lower():
                # Still check against root books, but avoid rejection loops on identical rejection reasons
                pass

            hist_title_norm = normalize_title(rec_title)
            hist_topic_norm = normalize_topic(rec_topic)

            # Level 1: Exact Normalized Title Match
            if cand_title_norm and hist_title_norm and cand_title_norm == hist_title_norm:
                # Check if angle is genuinely distinct
                if self.has_distinct_angle(candidate_angle, candidate_summary, rec_angle, rec_summary):
                    return IdeaDedupMatch(
                        is_duplicate=False,
                        similarity_score=0.95,
                        matched_record_id=rec_id,
                        matched_title=rec_title,
                        distinct_angle_accepted=True,
                    )
                return IdeaDedupMatch(
                    is_duplicate=True,
                    reason=f"Duplicate title matching existing record '{rec_title}'",
                    similarity_score=1.0,
                    matched_record_id=rec_id,
                    matched_title=rec_title,
                )

            # Level 2: Exact Normalized Topic Match
            if cand_topic_norm and hist_topic_norm and cand_topic_norm == hist_topic_norm:
                if self.has_distinct_angle(candidate_angle, candidate_summary, rec_angle, rec_summary):
                    return IdeaDedupMatch(
                        is_duplicate=False,
                        similarity_score=0.85,
                        matched_record_id=rec_id,
                        matched_title=rec_title,
                        distinct_angle_accepted=True,
                    )
                return IdeaDedupMatch(
                    is_duplicate=True,
                    reason=f"Same core topic and thesis as existing record '{rec_title}'",
                    similarity_score=0.90,
                    matched_record_id=rec_id,
                    matched_title=rec_title,
                )

            # Level 3: Token & Shingle Jaccard Similarity
            hist_tokens = tokenize_text(f"{rec_title} {rec_topic} {rec_summary}")
            hist_shingles = get_shingles(f"{rec_title} {rec_summary}", k=2)

            token_sim = jaccard_similarity(cand_tokens, hist_tokens)
            shingle_sim = jaccard_similarity(cand_shingles, hist_shingles)
            composite_sim = max(token_sim, shingle_sim)

            if composite_sim > highest_sim:
                highest_sim = composite_sim
                best_match_title = rec_title
                best_match_id = rec_id

            if token_sim >= self.token_threshold or shingle_sim >= self.shingle_threshold:
                if self.has_distinct_angle(candidate_angle, candidate_summary, rec_angle, rec_summary):
                    return IdeaDedupMatch(
                        is_duplicate=False,
                        similarity_score=composite_sim,
                        matched_record_id=rec_id,
                        matched_title=rec_title,
                        distinct_angle_accepted=True,
                    )
                return IdeaDedupMatch(
                    is_duplicate=True,
                    reason=f"High conceptual overlap (similarity: {composite_sim:.2f}) with existing record '{rec_title}'",
                    similarity_score=composite_sim,
                    matched_record_id=rec_id,
                    matched_title=rec_title,
                )

        return IdeaDedupMatch(
            is_duplicate=False,
            similarity_score=highest_sim,
            matched_record_id=best_match_id,
            matched_title=best_match_title,
        )

