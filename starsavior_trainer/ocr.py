from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from PIL import Image

# onnxruntime-gpu 需 cuDNN/cuBLAS DLL 在 PATH。pip 装的 nvidia-cudnn-cu13 /
# nvidia-cublas-cu13 把 DLL 放在 site-packages/nvidia/*/bin；加进 PATH 让
# onnxruntime 的 CUDAExecutionProvider 能加载（否则回退 CPU，OCR 慢 ~3 倍）。
#
# 路径陷阱(2026-07-04 实机修复)：
# - nvidia-cudnn-cu13 → nvidia/cudnn/bin/ (cudnn64_9.dll) ✓ import nvidia.cudnn 拿到
# - nvidia-cublas-cu11 → nvidia/cublas/bin/ (cublasLt64_11.dll, CUDA 11) ← import nvidia.cublas 拿到这个
# - nvidia-cublas (13.6.0.2, CUDA 13) → nvidia/cu13/bin/x86_64/ (cublasLt64_13.dll)
#   onnxruntime-gpu 1.27 要的是 cuBLAS 13 (cublasLt64_13.dll)，但 nvidia/cu13/ 无 __init__.py
#   不能 import，必须按文件路径找。cu11 的 cublas 装到 nvidia/cublas/bin/ 会"遮蔽"
#   import 结果，但 13 的 DLL 在 nvidia/cu13/bin/x86_64/，加进 PATH 即可。
for _pkg in ("nvidia.cudnn", "nvidia.cublas", "nvidia.cufft", "nvidia.curand", "nvidia.cuda_runtime", "nvidia.cuda_nvrtc", "nvidia.nvjitlink"):
    try:
        _m = __import__(_pkg, fromlist=["x"])
        # nvidia.* 是 PEP 420 命名空间包，__file__ 为 None；用 __path__[0] 取实际目录
        _base = list(_m.__path__)[0] if hasattr(_m, "__path__") else os.path.dirname(_m.__file__)
        _d = os.path.join(_base, "bin")
        if os.path.isdir(_d):
            os.environ["PATH"] = _d + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass
# nvidia-cublas 13.6.0.2 把 cublasLt64_13.dll 装到 nvidia/cu13/bin/x86_64/（无 __init__.py，
# 不能 import）。按 nvidia 包根目录的相对路径找 cu13/bin/x86_64。
try:
    import nvidia  # type: ignore
    _nv_root = list(nvidia.__path__)[0] if hasattr(nvidia, "__path__") else os.path.dirname(nvidia.__file__)
    _cu13_bin = os.path.normpath(os.path.join(_nv_root, "cu13", "bin", "x86_64"))
    if os.path.isdir(_cu13_bin):
        os.environ["PATH"] = _cu13_bin + os.pathsep + os.environ.get("PATH", "")
except Exception:
    pass


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float


@dataclass(frozen=True)
class OcrLine:
    """A single detected text block with its bounding box (x1, y1, x2, y2),
    in the coordinate space of the image passed to read_lines()."""
    text: str
    confidence: float
    box: tuple[int, int, int, int]


class OcrEngine(Protocol):
    def read_text(self, image: Image.Image) -> OcrResult:
        raise NotImplementedError

    def read_lines(self, image: Image.Image) -> list[OcrLine]:
        raise NotImplementedError


class NoopOcrEngine:
    def read_text(self, image: Image.Image) -> OcrResult:
        return OcrResult(text="", confidence=0.0)

    def read_lines(self, image: Image.Image) -> list[OcrLine]:
        return []


class RapidOcrEngine:
    """Real OCR via RapidOCR (PP-OCRv4 models on ONNX Runtime).

    替代旧 PaddleOcrEngine：paddleocr 2.7.3 在本环境对游戏 UI 全乱码幻觉、3.x 又
    撞 paddlepaddle-gpu 3.0.0b2 (beta) 的 PIR 崩溃，二者皆不可用。RapidOCR 用相同
    PP-OCRv4 模型但走 ONNX Runtime——稳定、轻量，GPU 加速经 onnxruntime-gpu
    (CUDAExecutionProvider)。实机验证：大厅帧 "训练/委托/休息/RANK/3月上旬/力量…"
    全部识别正确。

    OCR engine 选择（用户配置）：
    - engine="auto"（默认）: 优先 GPU（CUDAExecutionProvider 可用就用），失败回退 CPU
    - engine="gpu": 强制 GPU，构造失败回退 CPU（不报错，OCR 照常可用）
    - engine="cpu": 强制 CPU（use_cuda=False），不尝试 GPU

    注意：onnxruntime（CPU）和 onnxruntime-gpu 同时安装时，import onnxruntime 加载的
    可能是 CPU 版本（providers 只返回 CPUExecutionProvider）。要真正用 GPU：
      pip uninstall onnxruntime  # 卸载 CPU 版本，让 onnxruntime-gpu 接管
    或保留两者，engine="auto" 会自动检测：CUDA EP 不可用时回退 CPU。
    """

    def __init__(self, use_cuda: bool | None = None, engine: str = "auto") -> None:
        # engine 参数优先于 use_cuda（兼容旧调用方）
        # use_cuda=True → engine="gpu"；use_cuda=False → engine="cpu"；None → engine
        if use_cuda is not None:
            engine = "gpu" if use_cuda else "cpu"

        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as exc:
            raise RuntimeError("rapidocr-onnxruntime is not installed") from exc

        # 决定是否尝试 CUDA
        try_cuda = engine != "cpu"  # auto 或 gpu 都尝试
        kwargs = (
            {"det_use_cuda": True, "cls_use_cuda": True, "rec_use_cuda": True}
            if try_cuda
            else {}
        )
        try:
            self._engine = RapidOCR(**kwargs)
            # 验证 CUDA EP 真的可用（防止 silent fallback 到 CPU 但用户以为用 GPU）
            if try_cuda and not self._is_cuda_active():
                import warnings
                warnings.warn(
                    "OCR engine='gpu' but CUDAExecutionProvider not active "
                    "(onnxruntime CPU 版本仍安装着? 装 onnxruntime-gpu 或卸载 onnxruntime). "
                    "Falling back to CPU.",
                    RuntimeWarning,
                    stacklevel=2,
                )
        except Exception:
            # GPU 构造失败（缺 CUDA/cuDNN 等）→ 回退 CPU，识别照常可用。
            self._engine = RapidOCR()

    @staticmethod
    def _is_cuda_active() -> bool:
        """检测当前 onnxruntime 是否真用了 CUDAExecutionProvider。
        rapidocr_onnxruntime 内部封装了 onnxruntime Session，无法直接拿到 provider
        列表——间接检测：onnxruntime.get_available_providers() 含 CUDA 即视为可用。
        """
        try:
            import onnxruntime as ort
            return "CUDAExecutionProvider" in ort.get_available_providers()
        except Exception:
            return False

    @staticmethod
    def _run(engine, image: Image.Image) -> list:
        import numpy as np

        result, _elapse = engine(np.array(image.convert("RGB")))
        return result or []

    def read_text(self, image: Image.Image) -> OcrResult:
        result = self._run(self._engine, image)
        texts = [str(item[1]) for item in result if item[1]]
        if not texts:
            return OcrResult(text="", confidence=0.0)
        scores = [float(item[2]) for item in result if item[1]]
        return OcrResult(text=" ".join(texts), confidence=sum(scores) / len(scores))

    def read_lines(self, image: Image.Image) -> list[OcrLine]:
        result = self._run(self._engine, image)
        lines: list[OcrLine] = []
        for item in result:
            box, text, score = item[0], item[1], item[2]
            if not text:
                continue
            xs = [int(p[0]) for p in box]
            ys = [int(p[1]) for p in box]
            lines.append(
                OcrLine(
                    text=str(text),
                    confidence=float(score),
                    box=(min(xs), min(ys), max(xs), max(ys)),
                )
            )
        return lines
