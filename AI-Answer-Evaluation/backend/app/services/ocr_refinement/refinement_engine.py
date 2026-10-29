"""OCR Refinement engine enforcing strict KTU examination preservation rules.

Rules enforced:
1. Correct OCR mistranscriptions (characters, punctuation, spacing) using technical context.
2. Strictly preserve student wording, grammar errors, spelling choices, equations, units, code, and numbering.
3. NEVER add missing facts, explanations, or academic definitions.
4. NEVER paraphrase, summarize, or produce ideal answers.
5. Trace all proposed corrections with category, reason, review flags, and heuristic confidence.
6. Fallback safely to unmodified raw OCR text on any error or suspicious length drift.
"""

from datetime import datetime
import difflib
import json
import re
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import logger
from app.services.llm.llm_interface import get_llm_provider, LLMProvider


class ProposedCorrection(BaseModel):
    """Traceable proposed correction for teacher inspection."""
    original_fragment: str
    refined_fragment: str
    category: str = "OCR_CHAR_SUBSTITUTION"  # OCR_CHAR_SUBSTITUTION, PUNCTUATION_SPACING, TECHNICAL_TYPO, UNCERTAIN
    reason: str
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    requires_review: bool = False
    is_aligned: bool = True


class UncertainSpan(BaseModel):
    """Flagged ambiguous or low-confidence transcription span."""
    fragment: str
    reason: str
    flag: str = "UNCERTAIN_OCR"  # UNCERTAIN_OCR, AMBIGUOUS_TERM, QUESTION_BOUNDARY


class OCRRefinementResult(BaseModel):
    """Comprehensive result of OCR LLM refinement."""
    raw_ocr_text: str
    refined_ocr_text: Optional[str] = None
    corrected_text: Optional[str] = None
    diff: str = ""
    replacements_made: int = 0
    proposed_changes: List[ProposedCorrection] = []
    uncertain_spans: List[UncertainSpan] = []
    provider: Optional[str] = None
    model: Optional[str] = None
    status: str = "PENDING"  # PENDING, PROCESSING, REFINED, FAILED_FALLBACK_RAW, SKIPPED, TEACHER_APPROVED, TEACHER_REVERTED_RAW
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    processing_time_seconds: Optional[float] = None

    # Backward-compatible property aliases
    @property
    def raw_ocr(self) -> str:
        return self.raw_ocr_text

    @property
    def corrected_ocr(self) -> str:
        return self.refined_ocr_text or self.raw_ocr_text

    @property
    def refinement_time_taken(self) -> Optional[float]:
        return self.processing_time_seconds


class OCRRefinementEngine:
    """Production-grade KTU OCR Refinement Engine."""

    SYSTEM_PROMPT = (
        "You are an expert OCR transcription recovery assistant for handwritten KTU Engineering examination papers.\n"
        "Your sole task is to recover obvious character-recognition mistakes made by the OCR engine.\n\n"
        "STRICT PRESERVATION RULES:\n"
        "1. DO NOT improve or correct the student's underlying knowledge, grammar, or phrasing.\n"
        "2. If the student made a factual error or wrote grammatically incomplete sentences, KEEP IT EXACTLY AS IS.\n"
        "3. NEVER add missing definitions, keywords, explanations, or facts that are not present in the OCR text.\n"
        "4. NEVER paraphrase, summarize, or reword sentences.\n"
        "5. PRESERVE all question numbers (e.g., '1(a)', 'Q2'), equations, mathematical symbols, units, code, and lists.\n"
        "6. If a character or word cannot be deciphered with high certainty, DO NOT GUESS. Keep the raw fragment and flag it in 'uncertain_spans'.\n"
        "7. For every correction made, provide an entry in 'proposed_changes' explaining the exact typo and reason.\n\n"
        "OUTPUT FORMAT: You MUST reply with valid JSON only, using this schema:\n"
        "{\n"
        '  "refined_text": "<the refined transcription maintaining original layout>",\n'
        '  "proposed_changes": [\n'
        '    {\n'
        '      "original_fragment": "<exact original fragment>",\n'
        '      "refined_fragment": "<corrected fragment>",\n'
        '      "category": "OCR_CHAR_SUBSTITUTION" | "PUNCTUATION_SPACING" | "TECHNICAL_TYPO" | "UNCERTAIN",\n'
        '      "reason": "<short explanation>",\n'
        '      "confidence": <float between 0.0 and 1.0>,\n'
        '      "requires_review": <true | false>\n'
        '    }\n'
        '  ],\n'
        '  "uncertain_spans": [\n'
        '    {\n'
        '      "fragment": "<uncertain segment>",\n'
        '      "reason": "<why uncertain>",\n'
        '      "flag": "UNCERTAIN_OCR" | "AMBIGUOUS_TERM"\n'
        '    }\n'
        '  ]\n'
        "}\n"
        "Return NO conversational preamble or postscript, ONLY the raw JSON object."
    )

    def __init__(self, llm_provider: Optional[LLMProvider] = None) -> None:
        self.settings = get_settings()
        self.llm_provider = llm_provider or get_llm_provider()
        self.provider_name = getattr(self.llm_provider, "provider_name", "OLLAMA")
        self.model_name = getattr(self.llm_provider, "model", self.settings.LLM_MODEL)

    async def refine(self, raw_ocr_text: str) -> OCRRefinementResult:
        """Run refinement with strict rule enforcement, validation, and fallback."""
        start_time = time.perf_counter()

        if not raw_ocr_text or not raw_ocr_text.strip():
            return OCRRefinementResult(
                raw_ocr_text=raw_ocr_text or "",
                refined_ocr_text=None,
                corrected_text=raw_ocr_text or "",
                status="SKIPPED",
                replacements_made=0,
                provider=None,
                model=None,
                processing_time_seconds=round(time.perf_counter() - start_time, 3),
            )

        # Check if refinement is disabled
        if not self.settings.REFINEMENT_ENABLED:
            logger.info("OCR Refinement is disabled by configuration. Retaining raw OCR text.")
            return OCRRefinementResult(
                raw_ocr_text=raw_ocr_text,
                refined_ocr_text=None,
                corrected_text=raw_ocr_text,
                status="SKIPPED",
                replacements_made=0,
                provider=None,
                model=None,
                processing_time_seconds=round(time.perf_counter() - start_time, 3),
            )

        prompt = f"Raw Handwritten OCR Text:\n```\n{raw_ocr_text}\n```\n\nProvide the refined JSON output now:"

        try:
            # Generate with strict error surfacing and controlled timeout
            response = await self.llm_provider.generate(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                timeout=self.settings.REFINEMENT_TIMEOUT_SECONDS,
                strict=True,
            )

            raw_content = response.content.strip() if response and response.content else ""
            if not raw_content:
                logger.warning("LLM returned empty or whitespace response. Falling back to raw OCR text.")
                return self._create_fallback_result(
                    raw_ocr_text=raw_ocr_text,
                    status="FAILED_FALLBACK_RAW",
                    error_message="LLM returned an empty response.",
                    processing_time_seconds=round(time.perf_counter() - start_time, 3),
                )

            parsed_data = self._parse_json_response(raw_content)
            if not parsed_data or not isinstance(parsed_data, dict):
                logger.warning("LLM response could not be parsed into required JSON schema. Falling back.")
                return self._create_fallback_result(
                    raw_ocr_text=raw_ocr_text,
                    status="FAILED_FALLBACK_RAW",
                    error_message="LLM response did not adhere to required JSON schema.",
                    processing_time_seconds=round(time.perf_counter() - start_time, 3),
                )

            refined_candidate = parsed_data.get("refined_text")
            if not isinstance(refined_candidate, str) or not refined_candidate.strip():
                logger.warning("LLM response JSON lacked non-empty refined_text field. Falling back.")
                return self._create_fallback_result(
                    raw_ocr_text=raw_ocr_text,
                    status="FAILED_FALLBACK_RAW",
                    error_message="LLM response did not contain valid refined_text.",
                    processing_time_seconds=round(time.perf_counter() - start_time, 3),
                )
            refined_candidate = refined_candidate.strip()

            # Validate against hallucinations or unacceptable length divergence
            is_valid, validation_error = self._validate_refinement(raw_ocr_text, refined_candidate)
            if not is_valid:
                logger.warning(f"Refinement rejected by validation rules: {validation_error}")
                return self._create_fallback_result(
                    raw_ocr_text=raw_ocr_text,
                    status="FAILED_FALLBACK_RAW",
                    error_message=f"Refinement validation failed: {validation_error}",
                    processing_time_seconds=round(time.perf_counter() - start_time, 3),
                )

            # Build proposed changes with alignment checks
            proposed_changes = self._build_proposed_changes(
                raw_ocr_text=raw_ocr_text,
                refined_text=refined_candidate,
                raw_changes=parsed_data.get("proposed_changes", []),
            )

            # Build uncertain spans
            uncertain_spans = [
                UncertainSpan(
                    fragment=u.get("fragment", ""),
                    reason=u.get("reason", "Ambiguous text"),
                    flag=u.get("flag", "UNCERTAIN_OCR"),
                )
                for u in parsed_data.get("uncertain_spans", [])
                if u.get("fragment")
            ]

            # Compute diff
            diff_lines = list(
                difflib.unified_diff(
                    raw_ocr_text.splitlines(),
                    refined_candidate.splitlines(),
                    fromfile="raw_ocr",
                    tofile="refined_ocr",
                    lineterm="",
                )
            )
            diff_output = "\n".join(diff_lines)
            replacements = sum(1 for line in diff_lines if line.startswith("-") or line.startswith("+"))

            return OCRRefinementResult(
                raw_ocr_text=raw_ocr_text,
                refined_ocr_text=refined_candidate,
                corrected_text=refined_candidate,
                diff=diff_output,
                replacements_made=replacements,
                proposed_changes=proposed_changes,
                uncertain_spans=uncertain_spans,
                provider=response.provider or self.provider_name,
                model=response.model or self.model_name,
                status="REFINED",
                processing_time_seconds=round(time.perf_counter() - start_time, 3),
            )

        except Exception as exc:
            logger.error(f"OCR Refinement encountered error: {exc}. Safely falling back to raw OCR text.")
            return self._create_fallback_result(
                raw_ocr_text=raw_ocr_text,
                status="FAILED_FALLBACK_RAW",
                error_message=str(exc),
                processing_time_seconds=round(time.perf_counter() - start_time, 3),
            )

    def _parse_json_response(self, content: str) -> Optional[Dict[str, Any]]:
        """Safely parse structured JSON from LLM, stripping backticks or extra text."""
        if not content or not content.strip():
            return None

        # Try direct parse
        try:
            val = json.loads(content)
            if isinstance(val, dict):
                return val
        except Exception:
            pass

        # Try regex search for ```json { ... } ``` or outermost { ... }
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if json_match:
            try:
                val = json.loads(json_match.group(1))
                if isinstance(val, dict):
                    return val
            except Exception:
                pass

        # Outermost bracket match
        brace_match = re.search(r"(\{.*\})", content, re.DOTALL)
        if brace_match:
            try:
                val = json.loads(brace_match.group(1))
                if isinstance(val, dict):
                    return val
            except Exception:
                pass

        # Malformed or plain text without JSON schema cannot be treated as valid refinement
        logger.warning("Could not extract valid JSON object from LLM response.")
        return None

    def _validate_refinement(self, raw_text: str, candidate_text: str) -> (bool, Optional[str]):
        """Sanity check that LLM did not hallucinate new essays or drop large chunks."""
        raw_words = len(raw_text.split())
        cand_words = len(candidate_text.split())

        if raw_words == 0:
            return True, None

        ratio = cand_words / raw_words
        # Reject if text expanded by >35% or shrunk by >30%
        if ratio > 1.35:
            return False, f"Refined text word count expanded too much ({cand_words} vs {raw_words} words, ratio {ratio:.2f})"
        if ratio < 0.65:
            return False, f"Refined text word count dropped excessively ({cand_words} vs {raw_words} words, ratio {ratio:.2f})"

        # Check for obvious AI conversational leakage
        leakage_phrases = [
            "here is the corrected",
            "as an ai",
            "i have corrected",
            "student's answer",
            "ideal answer:",
            "note:",
        ]
        cand_lower = candidate_text.lower()
        for phrase in leakage_phrases:
            if phrase in cand_lower and phrase not in raw_text.lower():
                return False, f"Detected conversational leakage phrase '{phrase}' in refined output"

        return True, None

    def _build_proposed_changes(
        self,
        raw_ocr_text: str,
        refined_text: str,
        raw_changes: List[Dict[str, Any]],
    ) -> List[ProposedCorrection]:
        """Normalize proposed changes, align to original text, and detect diff changes."""
        changes: List[ProposedCorrection] = []

        for ch in raw_changes:
            orig = str(ch.get("original_fragment", "")).strip()
            ref = str(ch.get("refined_fragment", "")).strip()
            if not orig or not ref or orig == ref:
                continue

            # Check alignment in raw text
            is_aligned = orig in raw_ocr_text
            conf = float(ch.get("confidence", 0.85))
            conf = max(0.0, min(1.0, conf))

            # Review required if confidence < 0.80 or category is technical meaning or unaligned
            category = ch.get("category", "OCR_CHAR_SUBSTITUTION")
            requires_review = ch.get("requires_review", False) or conf < 0.80 or (not is_aligned)

            changes.append(
                ProposedCorrection(
                    original_fragment=orig,
                    refined_fragment=ref,
                    category=category,
                    reason=ch.get("reason", "Plausible transcription recovery"),
                    confidence=conf,
                    requires_review=requires_review,
                    is_aligned=is_aligned,
                )
            )

        # If LLM didn't list itemized changes but text changed, synthesize from sequence matcher
        if not changes and raw_ocr_text != refined_text:
            matcher = difflib.SequenceMatcher(None, raw_ocr_text.split(), refined_text.split())
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag in ("replace", "delete", "insert"):
                    orig_f = " ".join(raw_ocr_text.split()[i1:i2])
                    ref_f = " ".join(refined_text.split()[j1:j2])
                    if orig_f or ref_f:
                        changes.append(
                            ProposedCorrection(
                                original_fragment=orig_f,
                                refined_fragment=ref_f,
                                category="OCR_CHAR_SUBSTITUTION" if tag == "replace" else "PUNCTUATION_SPACING",
                                reason=f"Diff-derived {tag} segment",
                                confidence=0.75,
                                requires_review=True,
                                is_aligned=orig_f in raw_ocr_text if orig_f else False,
                            )
                        )

        return changes

    def _sanitize_error_message(self, error: Any) -> str:
        """Strip tracebacks, credentials, and sensitive headers; produce clear explanations."""
        err_str = str(error) if error else "Unknown refinement error"
        err_lower = err_str.lower()

        # Connection / Daemon Unreachable errors
        if any(term in err_lower for term in [
            "10061", "connection refused", "connecterror", "failed to connect",
            "connection attempt failed", "all connection attempts failed",
            "cannot connect", "target machine actively refused", "winerror",
            "offline", "connection error"
        ]):
            return "Local Ollama service unreachable at http://localhost:11434. Original raw OCR text retained."

        # Timeout errors
        if "timeout" in err_lower or "timed out" in err_lower:
            return "LLM refinement timed out. Original raw OCR text retained."

        # Cloud policy / Privacy errors
        if "allow_cloud_llm" in err_lower or "cloud llm provider" in err_lower or "permissionerror" in err_lower:
            return "External cloud LLM provider is blocked by privacy configuration (ALLOW_CLOUD_LLM=False). Original raw OCR text retained."

        # Missing API Key
        if "api_key" in err_lower or "not configured" in err_lower:
            return "LLM provider is not configured. Original raw OCR text retained."

        # Validation errors
        if "refinement validation" in err_lower or "word count" in err_lower or "conversational leakage" in err_lower:
            clean_msg = err_str.replace("Refinement validation failed: ", "").replace("Refinement validation rejected: ", "").strip()
            return f"Refinement validation rejected: {clean_msg}. Original raw OCR text retained."

        # JSON parsing errors
        if "json" in err_lower or "schema" in err_lower:
            return "LLM response did not adhere to required JSON schema. Original raw OCR text retained."

        # Generic sanitization: remove any authorization headers, bearer tokens, or query strings
        sanitized = re.sub(r'bearer\s+[A-Za-z0-9_\-\.]+', '[REDACTED]', err_str, flags=re.IGNORECASE)
        sanitized = re.sub(r'key=[A-Za-z0-9_\-]+', 'key=[REDACTED]', sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r'(?:password|secret|token)[:=]\s*\S+', '[REDACTED]', sanitized, flags=re.IGNORECASE)
        if len(sanitized) > 180:
            sanitized = sanitized[:177] + "..."
        if "retained" not in sanitized.lower():
            sanitized = f"{sanitized}. Original raw OCR text retained."
        return sanitized

    def _create_fallback_result(
        self,
        raw_ocr_text: str,
        status: str = "FAILED_FALLBACK_RAW",
        error_message: str = "Refinement failed",
        processing_time_seconds: Optional[float] = None,
    ) -> OCRRefinementResult:
        """Create a safe fallback result preserving original raw OCR text."""
        safe_error = self._sanitize_error_message(error_message)
        return OCRRefinementResult(
            raw_ocr_text=raw_ocr_text,
            refined_ocr_text=None,  # Never report fallback text as LLM-generated output
            corrected_text=raw_ocr_text,
            diff="",
            replacements_made=0,
            proposed_changes=[],
            uncertain_spans=[
                UncertainSpan(
                    fragment="Full Script",
                    reason=f"Refinement unavailable: {safe_error}",
                    flag="UNCERTAIN_OCR",
                )
            ],
            provider=self.provider_name,
            model=self.model_name,
            status=status or "FAILED_FALLBACK_RAW",
            error_message=safe_error,
            processing_time_seconds=processing_time_seconds,
        )

