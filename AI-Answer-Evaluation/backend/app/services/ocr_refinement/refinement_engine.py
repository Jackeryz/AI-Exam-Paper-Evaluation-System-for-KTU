"""OCR Refinement engine enforcing strict preservation rules (no paraphrasing, no grammar fixes, no content additions)."""

import difflib
from typing import Any, Dict, Tuple
from pydantic import BaseModel

from app.core.logging import logger
from app.services.llm.llm_interface import get_llm_provider, LLMProvider


class OCRRefinementResult(BaseModel):
    raw_ocr: str
    corrected_ocr: str
    diff: str
    replacements_made: int


class OCRRefinementEngine:
    """Strict OCR Refinement pipeline."""

    SYSTEM_PROMPT = (
        "You are an expert OCR Correction Engine for handwritten KTU examination answer papers.\n"
        "RULES (CRITICAL - YOU MUST FOLLOW EXACTLY):\n"
        "1. Correct ONLY obvious OCR mistranscriptions (e.g. 'c0nstituti0n' -> 'constitution', 'econnomic' -> 'economic').\n"
        "2. NEVER rewrite the student's answer.\n"
        "3. NEVER fix student grammar mistakes.\n"
        "4. NEVER paraphrase.\n"
        "5. NEVER add missing facts, words, or details.\n"
        "6. Output ONLY the raw corrected text, keeping line breaks unchanged.\n"
    )

    def __init__(self, llm_provider: Any = None) -> None:
        self.llm_provider = llm_provider or get_llm_provider()

    async def refine(self, raw_ocr_text: str) -> OCRRefinementResult:
        """Run LLM refinement and compute structural diff."""
        if not raw_ocr_text.strip():
            return OCRRefinementResult(
                raw_ocr=raw_ocr_text,
                corrected_ocr=raw_ocr_text,
                diff="",
                replacements_made=0,
            )

        prompt = f"Raw Handwritten OCR Text:\n{raw_ocr_text}\n\nCorrected Output:"
        response = await self.llm_provider.generate(prompt=prompt, system_prompt=self.SYSTEM_PROMPT)

        corrected_text = response.content.strip()
        
        # Calculate Unified Diff
        diff_lines = list(
            difflib.unified_diff(
                raw_ocr_text.splitlines(),
                corrected_text.splitlines(),
                fromfile="raw_ocr",
                tofile="corrected_ocr",
                lineterm="",
            )
        )
        diff_output = "\n".join(diff_lines)
        replacements = sum(1 for line in diff_lines if line.startswith("-") or line.startswith("+"))

        return OCRRefinementResult(
            raw_ocr=raw_ocr_text,
            corrected_ocr=corrected_text if corrected_text else raw_ocr_text,
            diff=diff_output,
            replacements_made=replacements,
        )
