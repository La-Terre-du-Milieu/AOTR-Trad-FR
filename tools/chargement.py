"""Écran de chargement : « Loading » est dessiné dans l'image de fond d'AotR (art/compiledtextures/lo/loadpage_bg.dds),
pas dans lotr.str. On efface le mot dans le cartouche du haut et on écrit « CHARGEMENT » avec la police Aniron
(celle de l'image d'origine), au même format DDS (DXT3). build_submod.py copie le résultat dans le submod.

Usage : python tools/chargement.py [sortie.dds]     (défaut : work/chargement/loadpage_bg.dds + aperçu .png)
Dépendance : Pillow (lecture et écriture DDS).
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = r'C:\AgeoftheRing\aotr\art\compiledtextures\lo\loadpage_bg.dds'
# Aniron (Pete Klassen), la police de l'image d'origine, tapée en majuscules ; à installer sur la machine
FONT = next((p for p in (os.path.join(os.environ.get('LOCALAPPDATA', ''), r'Microsoft\Windows\Fonts\anirm__.ttf'),
                          r'C:\Windows\Fonts\anirm__.ttf') if os.path.exists(p)), 'anirm__.ttf')
OUT = os.path.join(ROOT, 'work', 'chargement', 'loadpage_bg.dds')
TEXT = 'CHARGEMENT'
WORD = (446, 12, 582, 50)        # zone du mot « Loading » dans la texture 1024×1024
REF = ('LOADING', 117)           # mot d'origine et sa largeur dans la texture (px)
BASELINE = 40
COLOR = (150, 190, 204)


def build(dest):
    im = Image.open(SOURCE).convert('RGBA')
    a = np.asarray(im).copy()
    x0, y0, x1, y1 = WORD
    a[y0:y1, x0:x1, :3] = 0          # l'intérieur du cartouche est noir pur autour du mot
    im = Image.fromarray(a, 'RGBA')
    size = 10
    while ImageFont.truetype(FONT, size + 1).getlength(REF[0]) <= REF[1]:   # même corps que le mot d'origine
        size += 1
    font = ImageFont.truetype(FONT, size)
    width = font.getlength(TEXT)
    draw = ImageDraw.Draw(im)
    draw.text((512 - width / 2, BASELINE), TEXT, font=font, fill=COLOR + (255,), anchor='ls')
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    im.save(dest, format='DDS', pixel_format='DXT3')
    im.crop((370, 0, 660, 70)).resize((1160, 280), Image.LANCZOS).save(os.path.splitext(dest)[0] + '_apercu.png')
    print(f'« {TEXT} » (police {size}, {width:.0f} px) -> {dest}')


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else OUT)
