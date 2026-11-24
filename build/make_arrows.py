"""生成界面用的小图标（下拉箭头、微调箭头）。

用法：
    .venv\\Scripts\\python.exe build\\make_arrows.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "app" / "resources"
SCALE = 8
SIZE = 10


def chevron(color: str, direction: str) -> Image.Image:
    """绘制抗锯齿的 V 形箭头，direction 为 up / down。"""
    canvas = SIZE * SCALE
    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    pad = 2 * SCALE
    width = max(1, round(1.6 * SCALE))
    if direction == "down":
        points = [(pad, pad), (canvas // 2, canvas - pad), (canvas - pad, pad)]
    else:
        points = [(pad, canvas - pad), (canvas // 2, pad), (canvas - pad, canvas - pad)]
    draw.line(points, fill=color, width=width, joint="curve")
    # 圆头端点，避免缩小后出现尖角
    radius = width / 2
    for x, y in (points[0], points[-1]):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    return image.resize((SIZE, SIZE), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    variants = {
        "arrow_up": ("up", "#6B7280"),
        "arrow_down": ("down", "#6B7280"),
        "arrow_up_active": ("up", "#2F6FED"),
        "arrow_down_active": ("down", "#2F6FED"),
        "arrow_down_disabled": ("down", "#C3CAD5"),
    }
    for name, (direction, color) in variants.items():
        path = OUT / f"{name}.png"
        chevron(color, direction).save(path)
        print(f"已生成 {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
