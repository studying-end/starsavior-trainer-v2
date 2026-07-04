"""交易商店 parser — Journey Trading (交易)。

重构自 screen_reader.py §5（行 1190-1228）。商品名/价格 OCR 不可靠, 买/不买看效果,
效果只在选中后中央详情显示 → 检视器逐行点开读 shop_detail_effect。
"""
from __future__ import annotations

from collections.abc import Iterable

from PIL import Image

from starsavior_trainer.models import ShopItem, ShopScene
from starsavior_trainer.ocr_reader import RegionText
from starsavior_trainer.regions import RegionProfile
from starsavior_trainer.text_utils import parse_first_int


def parse_shop(
    region_texts: Iterable[RegionText],
    profile: RegionProfile,
    image: Image.Image | None = None,
) -> ShopScene | None:
    """Read Journey Trading (交易) items: one ShopItem per defined row.

    The right-side list OCRs unreliably (small text over a textured/transparent
    panel, with strikethrough prices), and the buy decision keys off each item's
    *effect* — which only shows in the centre detail panel once the item is
    selected, so the shop inspector reads it by clicking each row. We therefore
    return one clickable item per ``shop_item_N`` row regardless of whether its
    name/price OCR'd; name/price are filled best-effort for logging/identity. The
    selected item's effect detail is read separately (``shop_detail_effect``) and
    attributed to the clicked row by the inspector.
    """
    texts = {item.name: item.text for item in region_texts}

    items: list[ShopItem] = []
    for idx in range(1, 6):
        target = profile.regions.get(f"shop_item_{idx}")
        if target is None:
            continue
        name = texts.get(f"shop_item_{idx}_name", "").strip()
        price = parse_first_int(texts.get(f"shop_item_{idx}_price", ""))
        button = profile.regions.get(f"shop_item_{idx}_button")
        click_target = button if button is not None else target
        items.append(ShopItem(name=name, price=price if price is not None else 0, target=click_target))

    if not items:
        return None
    return ShopScene(
        items=tuple(items),
        # The selected item's effect detail (centre panel) — only this needs OCR;
        # the shop inspector attributes it to the row it clicked last turn.
        selected_effect=texts.get("shop_detail_effect", "").strip(),
        buy_button=profile.regions.get("shop_buy_button"),
        back_button=profile.regions.get("shop_back_button"),
    )
