"""Structured Rubric Parser extracting section-wise mark allocations, expected sections, and scoring rules."""

import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RubricSection(BaseModel):
    name: str
    allocated_marks: float
    description: str = ""
    mandatory_keywords: List[str] = Field(default_factory=list)


class ParsedRubric(BaseModel):
    total_marks: float = 10.0
    sections: List[RubricSection] = Field(default_factory=list)
    scoring_rules: List[str] = Field(default_factory=list)
    mandatory_keywords: List[str] = Field(default_factory=list)
    raw_rubric_text: str = ""


class RubricParser:
    """Parses raw dictionary or text rubrics into structured allocations."""

    def parse(self, rubric_data: Any, default_max_marks: float = 10.0) -> ParsedRubric:
        """Parse structured dict or raw text into ParsedRubric."""
        if not rubric_data:
            return ParsedRubric(
                total_marks=default_max_marks,
                sections=[
                    RubricSection(name="Concept Understanding", allocated_marks=default_max_marks * 0.4),
                    RubricSection(name="Correctness & Keywords", allocated_marks=default_max_marks * 0.3),
                    RubricSection(name="Completeness", allocated_marks=default_max_marks * 0.3),
                ],
                scoring_rules=["Scored based on concept accuracy, keyword alignment, and completeness."],
                mandatory_keywords=[],
                raw_rubric_text="Default Standard Rubric",
            )

        if isinstance(rubric_data, dict):
            sections = []
            rules = rubric_data.get("scoring_rules", [])
            keywords = rubric_data.get("mandatory_keywords", [])
            total = float(rubric_data.get("total_marks", default_max_marks))

            sections_dict = rubric_data.get("sections") or rubric_data.get("criteria")
            if isinstance(sections_dict, dict):
                for sec_name, sec_val in sections_dict.items():
                    if isinstance(sec_val, (int, float)):
                        sections.append(RubricSection(name=sec_name, allocated_marks=float(sec_val)))
                    elif isinstance(sec_val, dict):
                        sections.append(
                            RubricSection(
                                name=sec_name,
                                allocated_marks=float(sec_val.get("marks", sec_val.get("allocated_marks", 2.0))),
                                description=str(sec_val.get("description", "")),
                                mandatory_keywords=sec_val.get("keywords", []),
                            )
                        )

            if not sections:
                sections = [
                    RubricSection(name="Main Content", allocated_marks=total),
                ]

            return ParsedRubric(
                total_marks=total,
                sections=sections,
                scoring_rules=rules if isinstance(rules, list) else [str(rules)],
                mandatory_keywords=keywords if isinstance(keywords, list) else [],
                raw_rubric_text=str(rubric_data),
            )

        # Parse text string (e.g. "Definition: 2 marks, Advantages: 3 marks, Applications: 5 marks")
        rubric_text = str(rubric_data)
        sections = []
        
        # Regex search for "Section: X marks"
        pattern = re.compile(r"([A-Za-z\s]+):\s*(\d+(?:\.\d+)?)\s*(?:marks?|m|pts?)?", re.IGNORECASE)
        matches = pattern.findall(rubric_text)

        if matches:
            for sec_name, marks_str in matches:
                sections.append(
                    RubricSection(
                        name=sec_name.strip(),
                        allocated_marks=float(marks_str),
                    )
                )

        if not sections:
            sections = [
                RubricSection(name="Concept & Correctness", allocated_marks=default_max_marks * 0.5),
                RubricSection(name="Completeness & Keywords", allocated_marks=default_max_marks * 0.5),
            ]

        extracted_keywords = re.findall(r"\b[A-Z][a-z]{3,}\b", rubric_text)

        return ParsedRubric(
            total_marks=default_max_marks,
            sections=sections,
            scoring_rules=[rubric_text],
            mandatory_keywords=list(set(extracted_keywords)),
            raw_rubric_text=rubric_text,
        )
