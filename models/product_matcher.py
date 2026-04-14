import re
import numpy as np
# Add project root to Python path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sentence_transformers import SentenceTransformer, util
from rapidfuzz import fuzz
from loguru import logger


class ProductMatcher:
    SBERT_THRESHOLD = 0.72      # lowered to catch book matches
    HIGH_CONFIDENCE = 0.88

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        logger.info(f"Loading SBERT model: {model_name}")
        self.model = SentenceTransformer(model_name)
        logger.info("SBERT model loaded successfully!")

    def encode(self, text: str) -> np.ndarray:
        return self.model.encode(text, convert_to_tensor=True)

    def encode_batch(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(texts, convert_to_tensor=True)

    def sbert_similarity(self, title_a: str, title_b: str) -> float:
        embeddings = self.model.encode([title_a, title_b])
        score = util.cos_sim(embeddings[0], embeddings[1])
        return float(score)

    def fuzzy_similarity(self, title_a: str, title_b: str) -> float:
        return fuzz.token_sort_ratio(
            title_a.lower(),
            title_b.lower()
        )

    def extract_version_numbers(self, title: str) -> set:
        """
        Extract version/model numbers from product titles.

        Key fix: removed 4 from ignored set so XM4 is detected.
        Only ignore truly ambiguous single digits: 1, 2, 3, 8.

        iPhone 15  → {15}
        Galaxy S24 → {24}
        XM5        → {5}
        XM4        → {4}   ← now detected!
        QC45       → {45}
        128GB      → ignored by pattern (followed by GB)
        """
        results = set()

        # Pattern 1 — standalone 1-2 digit numbers
        # NOT preceded or followed by other digits
        # NOT followed by GB/TB (storage)
        standalone = re.findall(
            r'(?<!\d)(\d{1,2})(?!\d)(?!\s*[Gg][Bb])(?!\s*[Tt][Bb])',
            title
        )
        results.update(standalone)

        # Pattern 2 — letters directly followed by 1-2 digits
        # catches XM4, XM5, S24, QC45
        letter_prefix = re.findall(r'[a-zA-Z](\d{1,2})(?!\d)', title)
        results.update(letter_prefix)

        # Only ignore truly ambiguous values
        # Removed 4 so XM4 gets detected!
        ignored = {"1", "2", "3", "8"}
        return results - ignored

    def is_different_version(self, title_a: str, title_b: str) -> bool:
        """
        Returns True only if titles have CLEARLY different version numbers.

        iPhone 15 vs iPhone 14     → True
        Sony XM5  vs Sony XM4      → True  ← now works!
        QC45      vs QC45          → False
        Book      vs Book (Author) → False
        """
        nums_a = self.extract_version_numbers(title_a)
        nums_b = self.extract_version_numbers(title_b)

        if not nums_a or not nums_b:
            return False

        only_in_a = nums_a - nums_b
        only_in_b = nums_b - nums_a

        if only_in_a and only_in_b:
            logger.debug(
                f"Different versions: "
                f"{only_in_a} vs {only_in_b} | "
                f"{title_a[:25]} vs {title_b[:25]}"
            )
            return True

        return False

    def combined_score(self, title_a: str, title_b: str) -> dict:
        """Combine SBERT + fuzzy + version guard."""
        sbert_score = self.sbert_similarity(title_a, title_b)
        fuzzy_score = self.fuzzy_similarity(title_a, title_b) / 100
        combined = (sbert_score * 0.7) + (fuzzy_score * 0.3)

        different_version = self.is_different_version(title_a, title_b)
        if different_version:
            combined = combined * 0.5
            logger.debug(f"Version penalty: {combined:.4f}")

        return {
            "sbert_score": round(sbert_score, 4),
            "fuzzy_score": round(fuzzy_score, 4),
            "combined_score": round(combined, 4),
            "different_version": different_version,
            "is_match": combined >= self.SBERT_THRESHOLD,
            "confidence": self._get_confidence(combined),
            "needs_review": (
                combined >= self.SBERT_THRESHOLD
                and combined < self.HIGH_CONFIDENCE
            ),
        }

    def _get_confidence(self, score: float) -> str:
        if score >= self.HIGH_CONFIDENCE:
            return "high"
        elif score >= self.SBERT_THRESHOLD:
            return "medium"
        elif score >= 0.60:
            return "low"
        else:
            return "no_match"

    def match_by_ean(self, ean_a: str, ean_b: str) -> bool:
        if not ean_a or not ean_b:
            return False
        return ean_a.strip() == ean_b.strip()

    def find_best_match(
        self,
        query_title: str,
        candidate_titles: list[str]
    ) -> dict:
        if not candidate_titles:
            return {
                "match_index": -1,
                "score": 0,
                "confidence": "no_match"
            }

        # Filter out different versions
        compatible_indices = []
        compatible_titles = []

        for i, title in enumerate(candidate_titles):
            if not self.is_different_version(query_title, title):
                compatible_indices.append(i)
                compatible_titles.append(title)

        # Fall back to all candidates if everything filtered
        if not compatible_titles:
            compatible_indices = list(range(len(candidate_titles)))
            compatible_titles = candidate_titles

        # Batch encode for speed
        all_texts = [query_title] + compatible_titles
        embeddings = self.model.encode(all_texts, convert_to_tensor=True)

        query_embedding = embeddings[0]
        candidate_embeddings = embeddings[1:]

        scores = util.cos_sim(query_embedding, candidate_embeddings)[0]
        scores = scores.cpu().numpy()

        best_local_idx = int(np.argmax(scores))
        best_score = float(scores[best_local_idx])
        best_original_idx = compatible_indices[best_local_idx]

        return {
            "match_index": best_original_idx,
            "matched_title": candidate_titles[best_original_idx],
            "score": round(best_score, 4),
            "confidence": self._get_confidence(best_score),
            "is_match": best_score >= self.SBERT_THRESHOLD,
        }