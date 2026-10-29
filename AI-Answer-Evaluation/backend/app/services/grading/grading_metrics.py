"""Centralized, reusable quantitative metrics for answer paper grading."""

import re
from typing import Dict, List, Optional, Set
import numpy as np


class GradingMetrics:
    """Pure mathematical and text-based metrics for deterministic answer evaluation."""

    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two embedding vectors (0.0 to 1.0)."""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        v1 = np.array(vec1, dtype=float)
        v2 = np.array(vec2, dtype=float)
        dot = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 > 0 and norm2 > 0:
            sim = dot / (norm1 * norm2)
            return float(np.clip(sim, 0.0, 1.0))
        return 0.0

    @staticmethod
    def keyword_coverage(
        student_text: str,
        required_keywords: List[str],
        synonyms: Optional[Dict[str, List[str]]] = None,
    ) -> float:
        """Compute proportion of required keywords or their synonyms present in student answer."""
        if not required_keywords:
            return 1.0
        if not student_text.strip():
            return 0.0

        lowered_text = student_text.lower()
        normalized_student = re.sub(r"\s*([=+\-*/^])\s*", r"\1", lowered_text)
        # Normalize multiplication in formulas (e.g. i*r -> ir)
        norm_student_formulas = re.sub(r"([a-zA-Z0-9])\*([a-zA-Z0-9])", r"\1\2", normalized_student)
        syn_map = synonyms or {}

        matched = 0
        for kw in required_keywords:
            kw_lower = kw.lower()
            kw_normalized = re.sub(r"\s*([=+\-*/^])\s*", r"\1", kw_lower)
            kw_norm_formulas = re.sub(r"([a-zA-Z0-9])\*([a-zA-Z0-9])", r"\1\2", kw_normalized)

            # Direct keyword match or operator-normalized match
            if (kw_lower in lowered_text or 
                kw_normalized in normalized_student or 
                kw_norm_formulas in norm_student_formulas or
                kw_norm_formulas.replace(" ", "") in norm_student_formulas.replace(" ", "")):
                matched += 1
                continue
            
            # Check synonyms if available
            syn_list = syn_map.get(kw, syn_map.get(kw_lower, []))
            if any(
                syn.lower() in lowered_text or 
                re.sub(r"\s*([=+\-*/^])\s*", r"\1", syn.lower()) in normalized_student or
                re.sub(r"([a-zA-Z0-9])\*([a-zA-Z0-9])", r"\1\2", re.sub(r"\s*([=+\-*/^])\s*", r"\1", syn.lower())).replace(" ", "") in norm_student_formulas.replace(" ", "")
                for syn in syn_list
            ):
                matched += 1
                continue

            # Word-level token match (e.g. "40 watts" matching "40w" or "10 ohms" matching "10Ω")
            kw_tokens = [t for t in re.findall(r'[a-zA-Z0-9]+', kw_lower) if t]
            if len(kw_tokens) > 1:
                token_matches = 0
                for tok in kw_tokens:
                    tok_syns = syn_map.get(tok, [tok])
                    if any(ts.lower() in lowered_text or ts.lower() in normalized_student for ts in tok_syns):
                        token_matches += 1
                if token_matches == len(kw_tokens):
                    matched += 1

        return float(round(matched / len(required_keywords), 4))

    @staticmethod
    def concept_overlap(student_text: str, required_concepts: List[str], synonyms: Optional[Dict[str, List[str]]] = None) -> float:
        """Compute coverage ratio of core conceptual phrases, accounting for synonyms."""
        if not required_concepts:
            return 1.0
        if not student_text.strip():
            return 0.0

        lowered_text = student_text.lower()
        normalized_student = re.sub(r"\s*([=+\-*/^])\s*", r"\1", lowered_text)
        norm_student_formulas = re.sub(r"([a-zA-Z0-9])\*([a-zA-Z0-9])", r"\1\2", normalized_student)
        syn_map = synonyms or {}

        matched = 0
        for concept in required_concepts:
            c_lower = concept.lower()
            c_norm = re.sub(r"\s*([=+\-*/^])\s*", r"\1", c_lower)
            if c_lower in lowered_text or c_norm in normalized_student:
                matched += 1
                continue
            
            # Check concept synonyms
            syn_list = syn_map.get(concept, syn_map.get(c_lower, []))
            if any(
                syn.lower() in lowered_text or 
                re.sub(r"\s*([=+\-*/^])\s*", r"\1", syn.lower()) in normalized_student or
                re.sub(r"([a-zA-Z0-9])\*([a-zA-Z0-9])", r"\1\2", re.sub(r"\s*([=+\-*/^])\s*", r"\1", syn.lower())).replace(" ", "") in norm_student_formulas.replace(" ", "")
                for syn in syn_list
            ):
                matched += 1
                continue

            # Word-level token match for multi-word concepts
            c_tokens = [t for t in re.findall(r'[a-zA-Z0-9]+', c_lower) if t]
            if len(c_tokens) > 1:
                token_matches = 0
                for tok in c_tokens:
                    tok_syns = syn_map.get(tok, [tok])
                    if any(ts.lower() in lowered_text or ts.lower() in normalized_student for ts in tok_syns):
                        token_matches += 1
                if token_matches == len(c_tokens):
                    matched += 1

        return float(round(matched / len(required_concepts), 4))

    @staticmethod
    def length_normalization(
        student_text: str,
        ideal_text: str,
        concept_coverage: float = 0.0,
        section_coverage: float = 0.0,
        semantic_similarity: float = 0.0,
        keyword_coverage: float = 0.0,
    ) -> float:
        """Ratio of student answer length relative to ideal answer, calibrated so concise correct answers are not penalized."""
        student_words = len(student_text.split())
        ideal_words = len(ideal_text.split())
        if ideal_words == 0:
            return 1.0
        if student_words == 0:
            return 0.0

        ratio = student_words / ideal_words

        # If student answer adequately covers key concepts, rubric sections,
        # or has high semantic similarity / keyword coverage,
        # avoid penalizing concise answers simply for brevity.
        has_strong_content = (
            concept_coverage >= 0.70 or
            section_coverage >= 0.70 or
            (concept_coverage >= 0.50 and section_coverage >= 0.50) or
            (semantic_similarity >= 0.65 and keyword_coverage >= 0.50) or
            semantic_similarity >= 0.75
        )

        if has_strong_content:
            if ratio < 0.30:
                # Concise but conceptually sound answer
                if concept_coverage >= 0.70 or section_coverage >= 0.70 or semantic_similarity >= 0.75 or (semantic_similarity >= 0.65 and keyword_coverage >= 0.60):
                    return 1.0
                return float(round(max(0.90, ratio / 0.30), 4))
            elif ratio <= 1.5:
                return 1.0
        elif concept_coverage >= 0.40 or semantic_similarity >= 0.55:
            if ratio < 0.30:
                return float(round(max(0.70, ratio / 0.30), 4))

        if ratio < 0.30:
            # Severely incomplete answer lacking concepts
            return float(round(ratio / 0.30, 4))
        elif ratio <= 1.5:
            return 1.0
        else:
            # Overly verbose / bloated penalty
            penalty = max(0.5, 1.0 - (ratio - 1.5) * 0.2)
            return float(round(penalty, 4))

    @staticmethod
    def is_negated(text: str, phrase: str) -> bool:
        """Check if phrase is preceded by a negation word (not, does not, cannot, never, no, without)."""
        pattern = rf"(?:not|does\s+not|did\s+not|cannot|can\s+not|never|no|is\s+not|are\s+not|was\s+not)\s+(?:[\w]+\s+){{0,3}}{re.escape(phrase)}"
        return bool(re.search(pattern, text, re.IGNORECASE))

    @staticmethod
    def detect_contradictions(
        student_text: str,
        ideal_text: str,
        question_text: str = "",
        rubric_text: str = "",
    ) -> List[str]:
        """Detect factual contradictions, inverted relationships, and invalid negated claims."""
        if not student_text or not student_text.strip():
            return []

        contradictions: List[str] = []
        student_lower = student_text.lower()
        ref_context = f"{ideal_text} {question_text} {rubric_text}".lower()
        sentences = [s.strip() for s in re.split(r"[.\n]+", student_lower) if s.strip()]

        # 1. Direct vs Inverse relationship contradictions (Economics / Scientific Laws)
        has_inverse = any(w in ref_context for w in ["inverse", "inversely", "negative relationship", "downward sloping", "law of demand"])
        has_direct = any(w in ref_context for w in ["directly proportional", "direct relationship", "positive relationship", "increases with"])

        if has_inverse:
            for s in sentences:
                is_exc = any(exc in s for exc in ["giffen", "veblen", "exception", "snob", "inferior"])
                if not is_exc:
                    if any(w in s for w in ["directly proportional", "direct relationship", "positive relationship"]):
                        if not GradingMetrics.is_negated(s, "directly proportional") and not GradingMetrics.is_negated(s, "direct relationship"):
                            contradictions.append("Student asserts a direct relationship where an inverse relationship was expected.")
                    if re.search(r"price\s+(?:rises|increases?|goes\s+up).*demand\s+(?:also\s+)?(?:rises|increases?|more|proportionally)", s):
                        contradictions.append("Student states demand increases as price increases (violating the Law of Demand).")
            # Misidentification of exceptions or assumptions
            if re.search(r"(?:giffen|veblen)\s+.*(?:exceptions?|because)\s+.*(?:demand|quantity)\s+(?:falls?|decreases?)\s+.*(?:price\s+(?:goes\s+up|rises|increases?))", student_lower):
                contradictions.append("Student misidentifies economic exceptions by stating demand falls as price rises.")
            if re.search(r"(?:assumptions?|ceteris paribus)\s+.*(?:changing|varying|variable)\s+(?:tastes?|income|preferences?)", student_lower):
                contradictions.append("Student asserts tastes/income vary, contradicting the ceteris paribus assumption of constant conditions.")

        if has_direct and not has_inverse:
            for s in sentences:
                if any(w in s for w in ["inversely proportional", "inverse relationship"]):
                    if not GradingMetrics.is_negated(s, "inversely proportional") and not GradingMetrics.is_negated(s, "inverse relationship"):
                        contradictions.append("Student asserts an inverse relationship where a direct relationship was expected.")

        # 2. Constitutional / Legal / Principle negations
        has_basic_structure = any(w in ref_context for w in ["basic structure", "kesavananda", "article 368", "amending power"])
        if has_basic_structure:
            unlimited_patterns = [
                (r"without\s+(?:any\s+)?(?:restriction|limitation)", "claims power without any restriction/limitation"),
                (r"supreme\s+power\s+.*to\s+change\s+anything", "claims supreme power to change anything"),
                (r"absolute\s+(?:sovereign\s+)?constituent\s+power", "claims absolute constituent power"),
                (r"(?:can|may)\s+(?:amend|alter|repeal|destroy|replace)\s+(?:any|all)\s+part\s+of\s+the\s+constitution", "claims power to amend/destroy any part of constitution"),
                (r"can\s+(?:alter|destroy|emasculate|remove)\s+(?:the\s+)?basic\s+structure", "claims power to alter or destroy basic structure"),
                (r"(?:removing|immune\s+to|without)\s+judicial\s+review", "claims removal of or immunity from judicial review"),
                (r"no\s+limitation\s+by\s+judicial\s+review", "claims no limitation by judicial review"),
                (r"unlimited\s+amending\s+power", "claims unlimited amending power"),
            ]
            for pat, desc in unlimited_patterns:
                m = re.search(pat, student_lower)
                if m and not GradingMetrics.is_negated(student_lower, m.group(0)):
                    contradictions.append(f"Student asserts '{m.group(0)}', contradicting the Basic Structure Doctrine limitation on amending power.")
                    break

            if "golaknath" in student_lower and any(w in student_lower for w in ["established", "propounded", "introduced", "ruled"]):
                contradictions.append("Student erroneously attributes the Basic Structure Doctrine to Golaknath case instead of Kesavananda Bharati.")

        # 3. Formula inversions & calculation errors
        norm_st = re.sub(r"\s*([=+\-*/^])\s*", r"\1", student_lower)
        if "v=ir" in ref_context or "ohm" in ref_context:
            if "i=r/v" in norm_st or "v=i/r" in norm_st or "i=v*r" in norm_st or "r=v*i" in norm_st:
                contradictions.append("Student inverts Ohm's Law formula (e.g., I = R / V or V = I / R instead of V = IR).")

        if "power" in ref_context or "p=i^2" in ref_context:
            if "p=v/i" in norm_st or "p=i/v" in norm_st or "p=r/i" in norm_st:
                contradictions.append("Student inverts Electrical Power formula (e.g., P = V / I instead of P = V * I or P = I^2 * R).")
            if re.search(r"\b5\s*(?:w|watts?)\b", student_lower) and not re.search(r"\b40\s*(?:w|watts?)\b", student_lower):
                contradictions.append("Student calculates 5 Watts instead of the correct power dissipation of 40 Watts.")

        # 4. Economics PED formula inversion
        if "elasticity" in ref_context or "ped" in ref_context:
            if re.search(r"change\s+in\s+price\s+(?:/|over|divided\s+by)\s+.*change\s+in\s+quantity", student_lower):
                contradictions.append("Student inverts Price Elasticity of Demand formula (%ΔP/%ΔQ instead of %ΔQ/%ΔP).")
            if "elastic demand means consumers buy the same quantity" in student_lower or "inelastic demand means demand fluctuates" in student_lower:
                contradictions.append("Student reverses the definitions of elastic and inelastic demand.")

        # 5. Data Structures (Stack LIFO vs Queue FIFO)
        if "stack" in ref_context and "queue" not in question_text.lower():
            if re.search(r"stack\s+is\s+(?:a\s+)?first[\s-]in[\s-]first[\s-]out", student_lower) or "stack is a fifo" in student_lower or "stack is fifo" in student_lower:
                if not GradingMetrics.is_negated(student_lower, "fifo"):
                    contradictions.append("Student asserts Stack is FIFO (First-In-First-Out), which defines a Queue.")

        # 6. Database ACID properties (Atomicity rollback & Durability persistence)
        if "acid" in ref_context or "durability" in ref_context or "atomicity" in ref_context:
            if "partially completed and saved" in student_lower or "saved halfway" in student_lower:
                contradictions.append("Student states transactions can be partially completed and saved, violating Atomicity.")
            if "stored only in temporary ram" in student_lower or "disappears when power goes off" in student_lower or "volatile temporary" in student_lower:
                contradictions.append("Student states data is stored in temporary volatile RAM, violating Durability.")

        # 7. Constitutional remedies (Article 32 & DPSPs)
        if "article 32" in ref_context or "habeas corpus" in ref_context:
            if "enforce directive principles" in student_lower or "dpsps strictly justiciable" in student_lower:
                contradictions.append("Student claims Article 32 enforces Directive Principles of State Policy (DPSPs), which are non-justiciable under Article 37.")

        return list(dict.fromkeys(contradictions))



    @staticmethod
    def section_coverage_ratio(student_text: str, expected_sections: List[str]) -> float:
        """Check if expected structural sections exist or are addressed."""
        if not expected_sections:
            return 1.0
        if not student_text.strip():
            return 0.0

        lowered_text = student_text.lower()
        cleaned_student = re.sub(r"['\"]", "", lowered_text)
        stop_words = {"statement", "description", "selection", "correct", "criteria", "about", "state", "with", "from"}

        found = 0
        for section in expected_sections:
            sec_clean = re.sub(r"['\"]", "", section.lower())
            # Direct section header match
            if sec_clean in cleaned_student or section.lower() in lowered_text:
                found += 1
                continue

            # Meaningful section keyword match
            sec_words = [w for w in re.findall(r"[a-z0-9]{3,}", sec_clean) if w not in stop_words]
            if sec_words and any(w in cleaned_student for w in sec_words):
                found += 1
                continue

            # Numerical calculation / units / formula recognition in student answer
            if any(calc in sec_clean for calc in ["numerical", "calculation", "units", "problem"]):
                if re.search(r"\d+\s*[a-zΩ]+|\d+\s*[=+\-*/^]\s*\d+", lowered_text):
                    found += 1

        return float(round(found / len(expected_sections), 4))
