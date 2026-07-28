import importlib.util
import sys
import types
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "test_ocr.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ocr_sandbox_test_ocr", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_initialize_ocr_uses_paddleocr_3x_model_dir_kwargs(monkeypatch, tmp_path):
    module = load_module()

    det_dir = tmp_path / "det"
    rec_dir = tmp_path / "rec"
    det_dir.mkdir()
    rec_dir.mkdir()
    (det_dir / "model.txt").write_text("det", encoding="utf-8")
    (rec_dir / "model.txt").write_text("rec", encoding="utf-8")

    class FakePaddleOCR:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            if "text_detection_model_dir" not in kwargs or "text_recognition_model_dir" not in kwargs:
                raise TypeError("missing local model dir kwargs")

    fake_paddleocr_module = types.ModuleType("paddleocr")
    fake_paddleocr_module.PaddleOCR = FakePaddleOCR
    monkeypatch.setitem(sys.modules, "paddleocr", fake_paddleocr_module)

    monkeypatch.setattr(module, "__file__", str(MODULE_PATH), raising=False)
    monkeypatch.setenv("PADDLEOCR_MODEL_ROOT", str(tmp_path))

    ocr = module.initialize_ocr()

    assert isinstance(ocr, FakePaddleOCR)
    assert ocr.kwargs["text_detection_model_dir"] == str(det_dir)
    assert ocr.kwargs["text_recognition_model_dir"] == str(rec_dir)
    assert ocr.kwargs["text_detection_model_name"] == "PP-OCRv5_mobile_det"
    assert ocr.kwargs["text_recognition_model_name"] == "en_PP-OCRv5_mobile_rec"
    assert ocr.kwargs["use_doc_orientation_classify"] is False
    assert ocr.kwargs["use_doc_unwarping"] is False
    assert ocr.kwargs["use_textline_orientation"] is False
    assert ocr.kwargs["enable_mkldnn"] is False


def test_run_ocr_reads_paddleocr_3x_results():
    module = load_module()

    class FakePaddleOCR:
        def predict(self, image):
            yield {
                "rec_texts": ["English text"],
                "rec_scores": [0.987],
                "rec_boxes": [[[1, 2], [3, 4], [5, 6], [7, 8]]],
            }

    result = module.run_ocr(FakePaddleOCR(), module.Image.new("RGB", (10, 10)))

    assert result["text"] == "English text"
    assert result["confidence"] == 0.987
    assert result["bounding_boxes"][0]["bbox"] == [[1, 2], [3, 4], [5, 6], [7, 8]]


def test_run_ocr_converts_paddleocr_3x_rectangle_boxes():
    module = load_module()

    class FakePaddleOCR:
        def predict(self, image):
            yield {
                "rec_texts": ["English text"],
                "rec_scores": [0.987],
                "rec_boxes": [[1, 2, 7, 8]],
            }

    result = module.run_ocr(FakePaddleOCR(), module.Image.new("RGB", (10, 10)))

    assert result["bounding_boxes"][0]["bbox"] == [[1, 2], [7, 2], [7, 8], [1, 8]]
