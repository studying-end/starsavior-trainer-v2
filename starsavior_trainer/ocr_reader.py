"""区域 OCR 读取器 — 按区域裁剪 + OCR，带 max_area 过滤。

重构自 screen_reader.py §5（行 112-161）。RegionOcrReader 把"对哪些区域 OCR"的策略
(read_all/read_names/read_prefixes/read_where) 与底层 OcrEngine 解耦。

**批量化优化**：所有 read_* 共享一次全图 read_lines（缓存到 self._lines），按 region rect
中心点匹配文字 —— 一帧只 OCR 一次(全图)，而非每区域单独 crop+read_text(~10-40 次调用)。
OCR 引擎的 read_lines 一次拿全部 text+bbox，比逐区域快一个量级。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Iterable

from PIL import Image

from starsavior_trainer.models import Rect
from starsavior_trainer.ocr import OcrEngine, OcrLine
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.text_utils import looks_like_ocr_region


@dataclass(frozen=True)
class RegionText:
    name: str
    text: str
    confidence: float


def _line_center_in_rect(line: OcrLine, rect: Rect) -> bool:
    """OCR 行 bbox 中心点是否落在 region rect 内。"""
    cx = (line.box[0] + line.box[2]) // 2
    cy = (line.box[1] + line.box[3]) // 2
    return rect.x <= cx <= rect.x + rect.width and rect.y <= cy <= rect.y + rect.height


class RegionOcrReader:
    def __init__(self, profile: RegionProfile, ocr: OcrEngine):
        self.profile = profile
        self.ocr = ocr
        # 全图 OCR 缓存(lazy)：同一 reader(=同一帧)的所有 read_* 共享一次 read_lines。
        self._lines: list[OcrLine] | None = None

    def _all_lines(self, image: Image.Image) -> list[OcrLine]:
        if self._lines is None:
            try:
                self._lines = self.ocr.read_lines(image)
            except Exception:
                self._lines = []
        return self._lines

    def read_all(self, image: Image.Image, max_area: int | None = None) -> list[RegionText]:
        return self.read_where(image, lambda _name, _rect: True, max_area=max_area)

    def read_names(self, image: Image.Image, names: Iterable[str]) -> list[RegionText]:
        wanted = set(names)
        return self.read_where(image, lambda name, _rect: name in wanted)

    def read_prefixes(
        self,
        image: Image.Image,
        prefixes: Iterable[str],
        max_area: int | None = None,
    ) -> list[RegionText]:
        wanted = tuple(prefixes)
        return self.read_where(image, lambda name, _rect: name.startswith(wanted), max_area=max_area)

    def read_ocr_regions(self, image: Image.Image, max_area: int | None = None) -> list[RegionText]:
        return self.read_where(image, lambda name, _rect: looks_like_ocr_region(name), max_area=max_area)

    def read_where(
        self,
        image: Image.Image,
        predicate: Callable[[str, Rect], bool],
        max_area: int | None = None,
    ) -> list[RegionText]:
        lines = self._all_lines(image)
        results: list[RegionText] = []
        for name, rect in self.profile.regions.items():
            if max_area is not None and rect.width * rect.height > max_area:
                continue
            if not predicate(name, rect):
                continue
            in_lines = [ln for ln in lines if _line_center_in_rect(ln, rect)]
            text = " ".join(ln.text for ln in in_lines)
            confidence = sum(ln.confidence for ln in in_lines) / len(in_lines) if in_lines else 0.0
            results.append(RegionText(name=name, text=text, confidence=confidence))
        return results
