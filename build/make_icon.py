"""生成应用图标（可重复执行）。"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "app" / "resources" / "app.ico"
SIZE = 512
RADIUS = 112

FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/msyhbd.ttc"),
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/arialbd.ttf"),
]


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size)


def build() -> None:
    top = (79, 141, 247)
    bottom = (29, 78, 216)

    gradient = Image.new("RGB", (SIZE, SIZE))
    draw = ImageDraw.Draw(gradient)
    for y in range(SIZE):
        ratio = y / (SIZE - 1)
        color = tuple(round(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3))
        draw.line([(0, y), (SIZE, y)], fill=color)

    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, SIZE - 1, SIZE - 1], radius=RADIUS, fill=255
    )

    icon = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    icon.paste(gradient, (0, 0), mask)

    # 左上角柔光，增加层次（高斯模糊避免出现硬边）
    glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([-160, -240, 380, 220], fill=(255, 255, 255, 46))
    glow = glow.filter(ImageFilter.GaussianBlur(70))
    icon = Image.alpha_composite(icon, glow)
    icon.putalpha(Image.composite(icon.getchannel("A"), mask, mask))

    draw = ImageDraw.Draw(icon)
    font = load_font(300)
    draw.text((SIZE / 2, SIZE / 2 + 10), "改", font=font, fill=(255, 255, 255, 255), anchor="mm")

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    icon.save(
        TARGET,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"icon written: {TARGET}")


if __name__ == "__main__":
    build()
