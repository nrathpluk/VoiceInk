"""Generate icon.ico for ThaiVoice. Purple circle + 3 white equalizer bars."""
from PIL import Image, ImageDraw

SIZE = 256
BG = (108, 99, 255, 255)        # #6C63FF
FG = (255, 255, 255, 255)


def render(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Filled purple circle
    pad = max(2, size // 64)
    d.ellipse((pad, pad, size - pad, size - pad), fill=BG)

    # 3 vertical "sound wave" bars centered, varying heights
    # Heights as fraction of size: short, tall, medium
    heights = [0.32, 0.52, 0.40]
    bar_w = max(2, size // 12)
    gap = max(2, size // 18)
    total_w = 3 * bar_w + 2 * gap
    cx = size // 2
    cy = size // 2
    x0 = cx - total_w // 2
    radius = bar_w // 2

    for i, hf in enumerate(heights):
        h = int(size * hf)
        bx0 = x0 + i * (bar_w + gap)
        bx1 = bx0 + bar_w
        by0 = cy - h // 2
        by1 = cy + h // 2
        d.rounded_rectangle((bx0, by0, bx1, by1), radius=radius, fill=FG)

    return img


def main():
    base = render(SIZE)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    base.save(
        "icon.ico",
        format="ICO",
        sizes=[(s, s) for s in sizes],
    )
    print("wrote icon.ico")


if __name__ == "__main__":
    main()
