"""
Generates EquityEngine's PWA icons: a simple geometric "beacon" mark
(a radiating light source) in the beacon-gold accent colour on the
ink-navy background, matching the design tokens in tailwind.config.js.
Drawn with primitives rather than relying on the Fraunces font being
available in this environment, so it doesn't depend on a font file
existing here — the actual app still uses Fraunces via Google Fonts,
this is just the icon generation step.

Maskable-icon safe zone: Android's adaptive icon system can crop up to
~20% off each edge when applying a mask (circle, squircle, etc.), so
the beacon mark is kept within the center ~80% of the canvas.
"""
from PIL import Image, ImageDraw
import math

INK = (20, 22, 58)       # #14163A
BEACON = (242, 183, 5)   # #F2B705


def draw_beacon_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), INK + (255,))
    draw = ImageDraw.Draw(img)

    cx, cy = size / 2, size / 2
    # Core circle (the "evidence" point)
    core_r = size * 0.11
    draw.ellipse(
        [cx - core_r, cy - core_r, cx + core_r, cy + core_r],
        fill=BEACON,
    )

    # Radiating rays (the "visibility/beacon" motif) — eight rays at
    # 45-degree intervals, tapered triangles from the core outward,
    # kept inside the ~80% safe zone for maskable icon cropping.
    ray_inner = size * 0.17
    ray_outer = size * 0.37
    ray_half_width = size * 0.035

    for angle_deg in range(0, 360, 45):
        angle = math.radians(angle_deg)
        perp = angle + math.pi / 2

        inner_x = cx + ray_inner * math.cos(angle)
        inner_y = cy + ray_inner * math.sin(angle)
        outer_x = cx + ray_outer * math.cos(angle)
        outer_y = cy + ray_outer * math.sin(angle)

        p1 = (inner_x + ray_half_width * math.cos(perp), inner_y + ray_half_width * math.sin(perp))
        p2 = (inner_x - ray_half_width * math.cos(perp), inner_y - ray_half_width * math.sin(perp))
        p3 = (outer_x, outer_y)

        draw.polygon([p1, p2, p3], fill=BEACON)

    return img


def draw_rounded_mask(size: int, radius_ratio: float = 0.22) -> Image.Image:
    """Rounds the icon's corners for platforms that don't apply their
    own adaptive mask (e.g. desktop PWA install, iOS home screen)."""
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    radius = int(size * radius_ratio)
    draw.rounded_rectangle([0, 0, size, size], radius=radius, fill=255)
    return mask


def generate(size: int, path: str, rounded: bool = True):
    icon = draw_beacon_icon(size)
    if rounded:
        mask = draw_rounded_mask(size)
        bg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        bg.paste(icon, (0, 0), mask)
        icon = bg
    icon.save(path, "PNG")
    print(f"Saved {path} ({size}x{size})")


if __name__ == "__main__":
    generate(192, "icon-192.png")
    generate(512, "icon-512.png")
    # A maskable variant (no rounded-corner mask applied here — the
    # OS applies its own mask shape, so this version should fill the
    # full square with the safe-zone padding already built in above).
    generate(512, "icon-512-maskable.png", rounded=False)
