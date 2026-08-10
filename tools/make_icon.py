"""Konveyor Denetim Sistemi uygulama ikonu uretir (app.ico + app.png).
Tema: incelenen parca + delik uzerinde buyutec (delik denetimi).
Calistir:  veri_toplama\\Scripts\\python.exe tools\\make_icon.py
"""
import os
from PIL import Image, ImageDraw

S = 1024  # supersample tuval (sonra 256'ya kuculur)
OUT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BG = (27, 30, 37, 255)        # #1b1e25  kart arka plani
BORDER = (44, 49, 59, 255)    # #2c313b
STEEL = (174, 180, 191, 255)  # #aeb4bf  aluminyum parca
STEEL_EDGE = (107, 114, 128, 255)
HOLE = (21, 23, 28, 255)      # #15171c  delik
ACCENT = (76, 143, 224, 255)  # #4c8fe0  buyutec (mavi vurgu)


def rounded(draw, box, radius, **kw):
    draw.rounded_rectangle(box, radius=radius, **kw)


def build():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Arka plan kart
    rounded(d, (40, 40, S - 40, S - 40), 170, fill=BG, outline=BORDER, width=14)

    # Incelenen parca (kademeli braket hissi: ana blok + ust cikinti)
    rounded(d, (210, 250, 770, 814), 48, fill=STEEL, outline=STEEL_EDGE, width=8)
    rounded(d, (250, 170, 560, 320), 36, fill=STEEL, outline=STEEL_EDGE, width=8)

    # Delik (denetim hedefi)
    cx, cy, r = 470, 540, 132
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=HOLE, outline=STEEL_EDGE, width=10)

    # Buyutec: delik uzerinde halka + sap
    lx, ly, ro, ri = 560, 590, 250, 188
    # sap (once, halkanin altinda kalsin)
    d.line((lx + 150, ly + 150, 880, 880), fill=ACCENT, width=86)
    d.ellipse((880 - 43, 880 - 43, 880 + 43, 880 + 43), fill=ACCENT)
    # halka
    d.ellipse((lx - ro, ly - ro, lx + ro, ly + ro), outline=ACCENT, width=64)
    # cam parlamasi (ince ic kenar)
    d.ellipse((lx - ri, ly - ri, lx + ri, ly + ri), outline=(120, 170, 235, 90), width=10)

    base = img.resize((256, 256), Image.LANCZOS)
    ico_path = os.path.join(OUT_DIR, "app.ico")
    png_path = os.path.join(OUT_DIR, "app.png")
    base.save(ico_path, format="ICO",
              sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    base.save(png_path, format="PNG")
    print("OK uretildi:", ico_path)
    print("OK uretildi:", png_path)


if __name__ == "__main__":
    build()
