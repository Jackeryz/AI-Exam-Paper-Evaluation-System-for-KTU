"""Automated Keyword and Concept Extraction Engine using text frequency, domain patterns, and rule synthesis."""

import re
from typing import Dict, List, Set
from pydantic import BaseModel, Field

from app.services.grading.rubric_parser import ParsedRubric


class ExtractedKeywordSet(BaseModel):
    required_keywords: List[str] = Field(default_factory=list)
    important_concepts: List[str] = Field(default_factory=list)
    synonyms: Dict[str, List[str]] = Field(default_factory=dict)
    related_terminology: List[str] = Field(default_factory=list)


class KeywordExtractor:
    """Extracts mandatory keywords and technical terms from multi-source material without manual entry."""

    # Common English stop words to filter out
    STOP_WORDS: Set[str] = {
        "the", "and", "is", "in", "it", "of", "to", "a", "that", "this", "for", "on", "with",
        "as", "are", "was", "be", "by", "an", "or", "at", "from", "which", "shall", "state",
        "has", "have", "had", "can", "could", "should", "would", "may", "might", "must",
        "not", "all", "any", "both", "each", "few", "more", "most", "other", "some", "such",
    }

    def extract(
        self,
        question_text: str,
        ideal_answer: str,
        rubric: ParsedRubric,
        study_material: List[str],
    ) -> ExtractedKeywordSet:
        """Extract required keywords, concepts, and synonyms."""
        combined_text = f"{question_text}\n{ideal_answer}\n{rubric.raw_rubric_text}\n" + "\n".join(study_material)
        
        # 1. Extract Capitalized technical terms & Proper Nouns (e.g. "Directive Principles", "Fundamental Rights", "Article 14")
        concept_candidates = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", combined_text)
        filtered_concepts = [c for c in concept_candidates if c.lower() not in self.STOP_WORDS and len(c) > 3]

        # Deduplicate preserving order
        unique_concepts = list(dict.fromkeys(filtered_concepts))

        # 2. Extract Significant Words (>4 letters)
        words = re.findall(r"\b[a-zA-Z]{4,}\b", combined_text)
        word_freq: Dict[str, int] = {}
        for w in words:
            w_lower = w.lower()
            if w_lower not in self.STOP_WORDS:
                word_freq[w_lower] = word_freq.get(w_lower, 0) + 1

        # Top frequent technical terms
        top_words = sorted(word_freq.keys(), key=lambda k: word_freq[k], reverse=True)[:15]
        
        # Combine rubric mandatory keywords
        all_required_kw = list(dict.fromkeys(rubric.mandatory_keywords + top_words[:8]))

        # Synthesize basic domain synonyms
        synonym_map: Dict[str, List[str]] = {
            "constitution": ["statute", "supreme law", "constitutional charter"],
            "economics": ["financial study", "market analysis", "economic theory"],
            "ethics": ["moral principles", "code of conduct", "professional integrity"],
            "rights": ["entitlements", "liberties", "privileges"],
            "duty": ["obligation", "responsibility"],
        }

        return ExtractedKeywordSet(
            required_keywords=all_required_kw if all_required_kw else ["concept", "principle", "rule"],
            important_concepts=unique_concepts[:8] if unique_concepts else ["Fundamental Concept"],
            synonyms=synonym_map,
            related_terminology=top_words[8:] if len(top_words) > 8 else [],
        )
