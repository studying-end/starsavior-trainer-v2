"""画面处理器协议 — 架构契约的体现。

每个游戏画面注册一个 handler，声明：对应哪个 Screen、优先级、是否参与锚点匹配、
如何从 OCR 文字产出 payload、如何根据观测决策。

契约（不可违背）：
- parse 只读 OCR 文字/区域，产出类型化 payload，绝不产 Action。
- decide 只读 observation + state（+ policy 配置/实例状态），产出 Action，绝不直接读像素。
- screens/__init__.py 的注册表是分类/决策/payload 读取三处的唯一调度枢纽。

迁移过渡：DelegatingScreenHandler 转发到已测试的 _has_X_signature/parse_X/decide_X，
行为 1:1 零回归。decide 接收 TrainerPolicy 实例是有意的（决策依赖其 config 与 _pending_*
实例状态），不是泄漏。

重构自 d:/chengfeng；详见 docs/现有项目架构分析.md §3.3、docs/新项目技术设计.md §6.2。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional, Protocol, runtime_checkable

from PIL import Image

from starsavior_trainer.models import Action, GameState, Observation, Screen
from starsavior_trainer.regions import RegionProfile

if TYPE_CHECKING:  # avoid a runtime import cycle with policy
    from starsavior_trainer.policy import TrainerPolicy


@runtime_checkable
class ScreenHandler(Protocol):
    """The contract a screen handler must satisfy."""

    screen: Screen
    # Lower priority is checked first during classification. Mirrors the original
    # ordered _match_screen signature checks so behaviour stays identical.
    priority: int

    def has_anchor(self, anchors: dict[str, str]) -> tuple[bool, float]:
        """Return (is_this_screen, confidence) from the OCR'd anchor texts."""
        ...

    def parse(
        self,
        region_texts: object,
        profile: RegionProfile,
        image: Optional[Image.Image] = None,
    ) -> object | None:
        """Build this screen's structured payload, or None if not parseable."""
        ...

    def decide(self, observation: Observation, state: GameState, policy: "TrainerPolicy") -> Action:
        """Choose an Action for an Observation of this screen."""
        ...


class DelegatingScreenHandler:
    """Concrete handler that forwards to existing functions (1:1 behaviour).

    Each screen wires the already-tested ``_has_X_signature`` / ``parse_X`` /
    ``decide_X`` callables here, so the registry changes the *dispatch* without
    changing any decision or parsing logic.
    """

    def __init__(
        self,
        screen: Screen,
        decide_fn: Callable[[Observation, GameState, "TrainerPolicy"], Action],
        *,
        priority: int = 1000,
        anchor_fn: Optional[Callable[[dict[str, str]], bool]] = None,
        anchor_confidence: float = 1.0,
        parse_fn: Optional[Callable[..., object | None]] = None,
        parse_needs_image: bool = False,
        ocr_prefixes: Optional[list[str]] = None,
    ) -> None:
        self.screen = screen
        self.priority = priority
        self._decide_fn = decide_fn
        self._anchor_fn = anchor_fn
        self._anchor_confidence = anchor_confidence
        self._parse_fn = parse_fn
        self._parse_needs_image = parse_needs_image
        # Region-name prefixes to OCR before parsing (used by the live loop).
        # None means this screen needs no OCR payload (policy clicks a fixed button).
        self.ocr_prefixes = ocr_prefixes

    def has_anchor(self, anchors: dict[str, str]) -> tuple[bool, float]:
        if self._anchor_fn is None:
            return (False, 0.0)
        return (True, self._anchor_confidence) if self._anchor_fn(anchors) else (False, 0.0)

    def parse(
        self,
        region_texts: object,
        profile: RegionProfile,
        image: Optional[Image.Image] = None,
    ) -> object | None:
        if self._parse_fn is None:
            return None
        if self._parse_needs_image:
            return self._parse_fn(region_texts, profile, image)
        return self._parse_fn(region_texts, profile)

    def decide(self, observation: Observation, state: GameState, policy: "TrainerPolicy") -> Action:
        return self._decide_fn(observation, state, policy)
