from PIL import Image, ImageDraw, ImageFont
import os

S, OUT = 2048, 512
SAFE = 0.80                       # content shrink so nothing hits the circular crop

NAVY_TOP, NAVY_BOT = (18, 38, 61), (8, 16, 28)
GREEN, GREEN_D, GREEN_L = (22, 199, 120), (14, 160, 96), (60, 224, 150)
OFFWHITE, WHITE = (243, 247, 250), (255, 255, 255)

def u(f): return int(round(f * S))

def base():
    img = Image.new("RGB", (S, S), NAVY_BOT)
    d = ImageDraw.Draw(img)
    for y in range(S):
        t = (y / (S - 1)) ** 0.85
        d.line([(0, y), (S, y)],
               fill=tuple(int(NAVY_TOP[i] + (NAVY_BOT[i] - NAVY_TOP[i]) * t) for i in range(3)))
    return img

def layer():
    ov = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    return ov, ImageDraw.Draw(ov)

def compose(ov):
    """Shrink the content layer toward the centre, then composite on the gradient."""
    n = int(S * SAFE)
    small = ov.resize((n, n), Image.LANCZOS)
    img = base().convert("RGBA")
    img.alpha_composite(small, ((S - n) // 2, (S - n) // 2))
    return img.convert("RGB")

def candle(d, cx, top, bot, wtop, wbot, color, w=.058, ww=.018):
    d.rounded_rectangle([u(cx - w/2), u(top), u(cx + w/2), u(bot)], radius=u(w*.30), fill=color)
    d.rounded_rectangle([u(cx - ww/2), u(wtop), u(cx + ww/2), u(wbot)], radius=u(ww/2), fill=color)

def polyline(d, pts, color, w=.052):
    px = [(u(x), u(y)) for x, y in pts]
    d.line(px, fill=color, width=u(w), joint="curve")
    for p in px:
        d.ellipse([p[0]-u(w/2), p[1]-u(w/2), p[0]+u(w/2), p[1]+u(w/2)], fill=color)

def font(size, name="seguibl.ttf"):
    for p in (name, "segoeuib.ttf", "arialbd.ttf"):
        f = os.path.join("C:\Windows\Fonts", p)
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()

def centred(d, txt, f, cy, fill):
    bb = d.textbbox((0, 0), txt, font=f)
    d.text((S/2 - (bb[0]+bb[2])/2, u(cy) - (bb[1]+bb[3])/2), txt, font=f, fill=fill)

# ------------------------------------------------------------------ A: bubble
def variant_bubble():
    ov, d = layer()
    d.rounded_rectangle([u(.13), u(.16), u(.87), u(.66)], radius=u(.105), fill=OFFWHITE)
    d.polygon([(u(.30), u(.62)), (u(.285), u(.87)), (u(.505), u(.645))], fill=OFFWHITE)
    candle(d, .295, .445, .560, .400, .592, GREEN_D, w=.070, ww=.022)
    candle(d, .500, .355, .505, .310, .540, GREEN,   w=.070, ww=.022)
    candle(d, .705, .255, .425, .215, .462, GREEN_L, w=.070, ww=.022)
    return compose(ov)

# ---------------------------------------------------------------- B: wordmark
def variant_wordmark():
    ov, d = layer()
    f = font(u(.285))
    centred(d, "DSE", f, .365, WHITE)
    d.rounded_rectangle([u(.16), u(.585), u(.84), u(.625)], radius=u(.020), fill=(30, 62, 88))
    polyline(d, [(.185, .795), (.375, .690), (.545, .742), (.755, .585)], GREEN, w=.062)
    d.polygon([(u(.660), u(.545)), (u(.855), u(.520)), (u(.822), u(.712))], fill=GREEN_L)
    return compose(ov)

# ------------------------------------------------------------------- C: pulse
def variant_pulse():
    ov, d = layer()
    for cx, top in ((.185, .615), (.355, .520), (.525, .565), (.695, .410)):
        d.rounded_rectangle([u(cx-.042), u(top), u(cx+.042), u(.855)], radius=u(.026),
                            fill=(30, 60, 90, 255))
    polyline(d, [(.145, .680), (.330, .520), (.505, .592), (.735, .320)], GREEN, w=.060)
    d.polygon([(u(.620), u(.255)), (u(.855), u(.225)), (u(.818), u(.455))], fill=GREEN_L)
    return compose(ov)

def save(img, name):
    img.resize((OUT, OUT), Image.LANCZOS).save(name + ".png")
    img.resize((1024, 1024), Image.LANCZOS).save(name + "@1024.png")

variants = [("logo-a-bubble", "A - bubble", variant_bubble()),
            ("logo-b-wordmark", "B - wordmark", variant_wordmark()),
            ("logo-c-pulse", "C - pulse", variant_pulse())]
for n, _, im in variants:
    save(im, n)

# preview: exactly how Telegram crops it, at real list/profile sizes
sheet = Image.new("RGB", (1200, 400), (246, 247, 249))
sd = ImageDraw.Draw(sheet)
lbl = font(30, "segoeuib.ttf")
for i, (n, title, _) in enumerate(variants):
    src, x0 = Image.open(n + ".png"), 40 + i * 390
    sd.text((x0, 22), title, font=lbl, fill=(28, 38, 48))
    for sz, pos in ((240, (x0, 78)), (88, (x0 + 262, 78)), (44, (x0 + 262, 190))):
        m = Image.new("L", (sz, sz), 0)
        ImageDraw.Draw(m).ellipse([0, 0, sz - 1, sz - 1], fill=255)
        sheet.paste(src.resize((sz, sz), Image.LANCZOS), pos, m)
sheet.save("logo-preview.png")
print("ok")
