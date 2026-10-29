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
            full_num = None
            if len(line) < 80:
                # 1. "Question 1", "Q.1", "Q1", "Q1(a)"
                m_q = re.match(r"^(?:Question|Q\.?)\s*(\d{1,2})(?:\s*[\.\:\-])?\s*(?:\(([a-zA-Z0-9]+)\))?\s*(?:\(([ivxlcdm]+)\))?", line, re.IGNORECASE)
                # 2. "1(a)", "1(b)", "1(a)(i)"
                m_np = re.match(r"^(\d{1,2})\s*\(([a-zA-Z0-9]+)\)\s*(?:\(([ivxlcdm]+)\))?", line, re.IGNORECASE)
                # 3. "1.", "1)", "1:", "1 -" followed by whitespace
                m_nd = re.match(r"^(\d{1,2})\s*[\.\:\)\-](?:\s+|$)", line, re.IGNORECASE)
                # 4. Standalone subquestion "(a)", "(b)"
                m_sub = re.match(r"^\(([a-zA-Z0-9]+)\)(?:\s+|$)", line, re.IGNORECASE)

                if m_q:
                    q_main = m_q.group(1)
                    q_sub = m_q.group(2)
                    q_rom = m_q.group(3)
                    full_num = f"{q_main}"
                    if q_sub:
                        full_num += f"({q_sub.lower()})"
                    if q_rom:
                        full_num += f"({q_rom.lower()})"
                elif m_np:
                    q_main = m_np.group(1)
                    q_sub = m_np.group(2)
                    q_rom = m_np.group(3)
                    full_num = f"{q_main}({q_sub.lower()})"
                    if q_rom:
                        full_num += f"({q_rom.lower()})"
                elif m_nd:
                    full_num = m_nd.group(1)
                elif m_sub:
                    main_part = current_q_num.split("(")[0] if current_q_num else "1"
                    full_num = f"{main_part}({m_sub.group(1).lower()})"

            if full_num:
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
