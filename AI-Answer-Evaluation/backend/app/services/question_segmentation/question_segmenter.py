"""Question segmentation service detecting questions, subquestions (a), (b), (i), (ii), and non-sequential numbering."""

import re
from typing import Dict, List, Optional
from pydantic import BaseModel


class SegmentedQuestion(BaseModel):
    question_number: str
    main_question: str
    subquestion: Optional[str] = None
    extracted_text: str
    start_line: int
    end_line: int


class QuestionSegmenter:
    """Regex & Rule-based Question Segmentation Service with non-sequential numbering support."""

    # Matches "1.", "Question 1", "Q1(a)", "1(a)(i)", "(a)", "(b)", "(i)", "(ii)"
    QUESTION_PATTERN = re.compile(
        r"^(?:Question\s*|Q\s*)?(\d+)?\s*(?:\(([a-z0-9]+)\)|\.|\:)?\s*(?:\(([ivxlcdm]+)\))?",
        re.IGNORECASE
    )

    def segment_text(self, ocr_text: str) -> List[SegmentedQuestion]:
        """Segment raw OCR text into structured question blocks."""
        lines = [line.strip() for line in ocr_text.splitlines() if line.strip()]
        segments: List[SegmentedQuestion] = []
        
        current_q_num = "1"
        current_lines: List[str] = []
        start_idx = 1

        for idx, line in enumerate(lines, start=1):
            match = re.search(r"^(?:Question|Q)?\s*(\d{1,2})\s*(?:\(([a-d])\))?\s*(?:\(([i-v]+)\))?", line, re.IGNORECASE)
            if match and len(line) < 80:
                q_main = match.group(1) or current_q_num
                q_sub = match.group(2)
                q_roman = match.group(3)
                
                full_num = f"{q_main}"
                if q_sub:
                    full_num += f"({q_sub.lower()})"
                if q_roman:
                    full_num += f"({q_roman.lower()})"

                if current_lines:
                    segments.append(
                        SegmentedQuestion(
                            question_number=current_q_num,
                            main_question=current_q_num.split("(")[0],
                            subquestion=current_q_num.split("(")[1].replace(")", "") if "(" in current_q_num else None,
                            extracted_text="\n".join(current_lines),
                            start_line=start_idx,
                            end_line=idx - 1,
                        )
                    )
                    current_lines = []
                    start_idx = idx

                current_q_num = full_num

            current_lines.append(line)

        if current_lines:
            segments.append(
                SegmentedQuestion(
                    question_number=current_q_num,
                    main_question=current_q_num.split("(")[0],
                    subquestion=current_q_num.split("(")[1].replace(")", "") if "(" in current_q_num else None,
                    extracted_text="\n".join(current_lines),
                    start_line=start_idx,
                    end_line=len(lines),
                )
            )

        return segments
