# /// script
# dependencies = ["pillow"]
# ///
"""Builds the site's framed product images from App Store captures and Apple product bezels.

  uv run tools/build_assets.py <mattermost-native checkout>

Each capture is clipped to the bezel's own screen shape (the transparent region connected to the
screen centre), so square screenshot corners never show past rounded screen corners. A capture
named NAME-dark.png beside NAME.png is used for the dark variant when it exists.
"""
import sys, pathlib
from PIL import Image, ImageDraw, ImageChops

repo = pathlib.Path(sys.argv[1]).expanduser()
BZ, SH, OUT = repo / "build/bezels", repo / "build/appstore", pathlib.Path(__file__).resolve().parent.parent / "assets"

def screen_mask(bezel: Image.Image) -> Image.Image:
    """White where the bezel's screen opening is (transparent pixels connected to the centre)."""
    a = bezel.getchannel("A").point(lambda v: 255 if v < 128 else 0)
    w, h = a.size
    ImageDraw.floodfill(a, (w // 2, h // 2), 128)
    return a.point(lambda v: 255 if v == 128 else 0)

def fit(shot: Image.Image, size, mode="fill"):
    """Scale the capture to the screen rect; 'letterbox' keeps aspect and extends edge rows."""
    W, H = size
    if mode == "fill":
        return shot.resize(size, Image.LANCZOS)
    s = W / shot.width
    scaled = shot.resize((W, round(shot.height * s)), Image.LANCZOS)
    canvas = Image.new("RGBA", size)
    top = (H - scaled.height) // 2
    canvas.paste(scaled, (0, top))
    if top > 0:  # extend the window's own top and bottom rows (its background), not a foreign color
        canvas.paste(scaled.crop((0, 8, W, 9)).resize((W, top)), (0, 0))
        bottom = H - top - scaled.height
        canvas.paste(scaled.crop((0, scaled.height - 9, W, scaled.height - 8)).resize((W, bottom)), (0, top + scaled.height))
        canvas.paste(scaled.crop((0, 0, W, scaled.height - 8)), (0, top))
    return canvas

def framed(bezel_file, shot_file, rect, width, mode="fill", crop_top=0):
    bezel = Image.open(BZ / bezel_file).convert("RGBA")
    shot = Image.open(shot_file).convert("RGBA")
    if crop_top:  # start at a message boundary; keep the capture's own top bar by shifting content only
        shot = shot.crop((0, crop_top, shot.width, shot.height))
    x, y, w, h = rect
    layer = Image.new("RGBA", bezel.size)
    layer.paste(fit(shot, (w, h), mode), (x, y))
    mask = screen_mask(bezel)
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
    out = Image.new("RGBA", bezel.size)
    out.alpha_composite(layer)
    out.alpha_composite(bezel)
    return out.resize((width, round(out.height * width / out.width)), Image.LANCZOS)

def shot_path(rel, dark):
    p = SH / rel
    d = p.with_name(p.stem + "-dark.png")
    return d if dark and d.exists() else p

ITEMS = [
    # name, bezel light, bezel dark, capture, screen rect, output width, mode
    ("duo-open", "Bezel-iPhone-Duo/iPhone Duo - Star White - Inner Open Landscape.png",
     "Bezel-iPhone-Duo/iPhone Duo - Night Sky - Inner Open Landscape.png", "duo-unfolded/01-conversation.png", (120, 120, 2853, 2007), 1600, "fill"),
    ("duo-folded", "Bezel-iPhone-Duo/iPhone Duo - Star White - Outer Closed Portrait.png",
     "Bezel-iPhone-Duo/iPhone Duo - Night Sky - Outer Closed Portrait.png", "duo-folded/03-agent.png", (88, 80, 1398, 2034), 640, "fill"),
    ("iphone-channels", "Bezel-iPhone-17/iPhone 17 Pro - Silver - Portrait.png",
     "Bezel-iPhone-17/iPhone 17 Pro - Deep Blue - Portrait.png", "iphone-6.3/01-channels.png", (72, 69, 1206, 2622), 600, "fill"),
    ("iphone-agent", "Bezel-iPhone-17/iPhone 17 Pro - Silver - Portrait.png",
     "Bezel-iPhone-17/iPhone 17 Pro - Deep Blue - Portrait.png", "iphone-6.3/03-agent.png", (72, 69, 1206, 2622), 600, "fill"),
    ("iphone-info", "Bezel-iPhone-17/iPhone 17 Pro - Silver - Portrait.png",
     "Bezel-iPhone-17/iPhone 17 Pro - Deep Blue - Portrait.png", "iphone-6.3/04-channel-info.png", (72, 69, 1206, 2622), 600, "fill"),
    ("ipad", "Bezel-iPad-Pro-(M5)/iPad Pro (M5) 13\" - Silver - Landscape.png",
     "Bezel-iPad-Pro-(M5)/iPad Pro (M5) 13\" - Space Black - Landscape.png", "ipad-13/04-channel-info.png", (124, 118, 2752, 2064), 1400, "fill"),
    ("mac", "Bezel-MacBook-Pro-M5/MacBook Pro M5 14-inch Silver.png",
     "Bezel-MacBook-Pro-M5/MacBook Pro M5 14-inch Space Black.png", "mac/01-conversation.png", (418, 288, 3024, 1964), 1600, "letterbox"),
]

for name, light, dark, cap, rect, width, mode in ITEMS:
    for variant, bezel in (("", light), ("-dark", dark)):
        img = framed(bezel, shot_path(cap, bool(variant)), rect, width, mode)
        img.save(OUT / f"{name}{variant}.webp", quality=86, method=6)
        print(f"{name}{variant}.webp", img.size, (OUT / f"{name}{variant}.webp").stat().st_size // 1024, "KB")
