"""Test en jeu : une sauvegarde de campagne par mission, à partir de celle du Save Generator du launcher.

Une sauvegarde .BfME2Campaign est une suite de blocs « CHUNK_<nom> » + « KOLB » + position (uint32) de la fin du
bloc dans le fichier. Le bloc GameState contient la description (UTF-16) et le chemin de la carte (ASCII, longueur sur
un octet) ; le bloc Campaign, le nom de la campagne, le numéro de la mission (uint32, à partir de 0 : c'est lui qui
choisit la carte chargée) et les héros emportés. On remplace description, carte et numéro, puis on décale les positions
de fin des blocs suivants.

Usage : python tools/sauvegardes_test.py [--efface]
  écrit « TEST <mission>.BfME2Campaign » dans le dossier de sauvegardes d'AotR ; --efface les retire.
"""
import glob
import os
import re
import struct
import sys

import saut_mission

SAVES = os.path.join(os.environ.get('APPDATA', ''), 'Age of the Ring', 'Save')
SOURCE = 'Auto Save for Campaign Fords of Isen.BfME2Campaign'


def missions():
    """[(mission, carte)] de la campagne du Seigneur des Anneaux (ANGMAR_BONUS_CAMPAIGN), dans l'ordre."""
    text = open(saut_mission.INI, encoding='cp1252', errors='replace').read()
    text = text[text.index('LinearCampaign ANGMAR_BONUS_CAMPAIGN'):]
    return re.findall(r'(?m)^\s*Mission\s+(\w+)\s*\r?\n\s*Map\s*=\s*"([^"]+)"', text)


def make(data, index, mission, mapname):
    gs = data.index(b'CHUNK_GameState')
    desc = data.index(b'_\x00_\x00A\x00U\x00T\x00O\x00', gs)          # « __AUTO#SAVE__ » précédé de sa longueur
    n = data[desc - 1]
    path = desc + 2 * n                                                   # octet de longueur du chemin de la carte
    old_end = path + 1 + data[path]
    label = f'TEST {mission}'.encode('utf-16-le')
    new_path = f'maps\\{mapname}\\{mapname}.map'.encode('ascii')
    new = data[:desc - 1] + bytes([len(label) // 2]) + label + bytes([len(new_path)]) + new_path
    delta = len(new) - old_end
    out = bytearray(new + data[old_end:])
    for m in re.finditer(rb'KOLB', out):          # positions de fin des blocs : décalées si après la carte
        end = struct.unpack_from('<I', out, m.end())[0]
        if old_end <= end <= len(data):
            struct.pack_into('<I', out, m.end(), end + delta)
    camp = out.index(b'ANGMAR_BONUS_CAMPAIGN', out.index(b'CHUNK_Campaign'))
    struct.pack_into('<I', out, out.index(b'KOLB', camp) + 9, index)     # KOLB, fin du bloc, version, numéro
    return bytes(out)


def main(argv):
    if '--efface' in argv:
        for f in glob.glob(os.path.join(SAVES, 'TEST *.BfME2Campaign')):
            os.remove(f)
        print('sauvegardes de test retirées')
        return
    data = open(os.path.join(SAVES, SOURCE), 'rb').read()
    for i, (mission, mapname) in enumerate(missions(), 1):
        with open(os.path.join(SAVES, f'TEST {i:02d} {mission}.BfME2Campaign'), 'wb') as f:
            f.write(make(data, i - 1, f'{i:02d} {mission}', mapname))
    print(f'{len(missions())} sauvegardes de test -> {SAVES}')


if __name__ == '__main__':
    main(sys.argv[1:])
