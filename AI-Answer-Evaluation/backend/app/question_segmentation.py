"""Question segmentation module delegating to app.services.question_segmentation."""

from app.services.question_segmentation.question_segmenter import QuestionSegmenter, SegmentedQuestion

__all__ = ["QuestionSegmenter", "SegmentedQuestion"]
