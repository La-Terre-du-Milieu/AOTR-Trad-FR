"""Voix françaises officielles (BFME II / RotWK) pour AotR.

Deux cas :
  1. Voix vanilla qu'AotR n'a pas remplacées (~10 800) : elles sont lues depuis l'EnglishAudio.big
     de l'installation de base du launcher. On les couvre avec une archive !AotR_VF.big.
  2. Voix vanilla qu'AotR a remplacées par un fichier dans data/audio/sounds (777) : la VF n'est
     remplacée que si la durée correspond à la VO vanilla (même réplique) ou si le fichier est
     listé dans audio_valides.txt après écoute.

Usage :
  python tools/audio_vf.py analyse          -> work/audio_vf.csv
  python tools/audio_vf.py ecoute <dossier> -> paires AOTR/VF des voix douteuses, à écouter
  python tools/audio_vf.py build <dossier>  -> <dossier>/!AotR_VF.big + <dossier>/data/audio/sounds/*.wav
"""
import csv
import os
import shutil
import struct
import sys

from bigfile import BigFile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AOTR = r'C:\AgeoftheRing'
EA = r'C:\Program Files (x86)\Electronic Arts'
# (jeu, VO de la base du launcher, VF d'EA) — RotWK en dernier : il l'emporte sur BFME II
GAMES = [
    ('BFME2', os.path.join(AOTR, 'bfme2', 'lang', 'EnglishAudio.big'),
     os.path.join(EA, 'La Bataille pour la Terre du Milieu II', 'lang', 'FrenchAudio.big')),
    ('RotWK', os.path.join(AOTR, 'rotwk', 'lang', 'EnglishAudio.big'),
     os.path.join(EA, "L'Avènement du Roi-sorcier", 'lang', 'frenchaudio.big')),
]
MOD_AUDIO = os.path.join(AOTR, 'aotr', 'data', 'audio')
VALIDES = os.path.join(ROOT, 'audio_valides.txt')
BIG_NAME = '!AotR_VF.big'
TOLERANCE = 0.10


def wav_duration(head):
    """Durée en secondes d'un WAV (PCM ou IMA ADPCM) à partir de ses premiers octets."""
    if head[:4] != b'RIFF':
        return None
    pos, fmt = 12, None
    while pos + 8 <= len(head):
        cid, size = head[pos:pos + 4], struct.unpack('<I', head[pos + 4:pos + 8])[0]
        if cid == b'fmt ':
            fmt = struct.unpack('<HHIIHH', head[pos + 8:pos + 24])
        elif cid == b'data' and fmt:
            tag, channels, rate, byte_rate, align, _ = fmt
            if tag == 0x11 and align:
                per_block = (align - 4 * channels) * 2 // channels + 1
                return size / align * per_block / rate
            return size / byte_rate if byte_rate else None
        pos += 8 + size + (size & 1)
    return None


def load():
    games = [(name, BigFile(en), BigFile(fr)) for name, en, fr in GAMES]
    mod = {}
    for sub in ('sounds', 'speech'):
        folder = os.path.join(MOD_AUDIO, sub)
        for f in os.listdir(folder):
            mod[f'data/audio/{sub}/{f.lower()}'] = os.path.join(folder, f)
    return games, mod


def valides():
    if not os.path.exists(VALIDES):
        return set()
    with open(VALIDES, encoding='utf-8') as f:
        return {ln.strip().lower() for ln in f if ln.strip() and not ln.startswith('#')}


def analyse(games, mod):
    """Voix remplacées par AotR qui existent en VF -> lignes (fichier, jeu, durées, statut)."""
    ok = valides()
    rows = {}
    for name, en, fr in games:
        for path in fr.files:
            if path not in mod or not path.endswith('.wav'):
                continue
            with open(mod[path], 'rb') as f:
                d_mod = wav_duration(f.read(4096))
            d_en = wav_duration(en.read(path, 4096)) if path in en.files else None
            d_fr = wav_duration(fr.read(path, 4096))
            same = d_mod and d_en and abs(d_mod - d_en) / d_en <= TOLERANCE
            base = os.path.basename(path)
            status = 'sûr' if same else ('validé' if base in ok else 'à écouter')
            rows[path] = (base, name, d_mod, d_en, d_fr, status)
    return rows


def write_big(dest, entries):
    """entries : liste de (nom interne, BigFile source, chemin normalisé dans la source)."""
    names = [n.encode('latin1') for n, _, _ in entries]
    sizes = [src.files[p][1] for _, src, p in entries]
    header = 16 + sum(8 + len(n) + 1 for n in names)
    with open(dest, 'wb') as out:
        out.write(b'BIGF' + struct.pack('<I', header + sum(sizes)) + struct.pack('>II', len(entries), header))
        off = header
        for n, size in zip(names, sizes):
            out.write(struct.pack('>II', off, size) + n + b'\0')
            off += size
        for _, src, p in entries:
            out.write(src.read(p))


def build(dest, games, mod, rows):
    vanilla = {}
    for _, _, fr in games:
        for path, (_, _, orig) in fr.files.items():
            if path not in mod and path.startswith('data/audio/'):
                vanilla[path] = (orig, fr, path)
    os.makedirs(dest, exist_ok=True)
    write_big(os.path.join(dest, BIG_NAME), sorted(vanilla.values(), key=lambda e: e[2]))
    sounds = os.path.join(dest, 'data', 'audio', 'sounds')
    os.makedirs(sounds, exist_ok=True)
    fr_by_game = {name: fr for name, _, fr in games}
    loose = [(p, r) for p, r in rows.items() if r[5] in ('sûr', 'validé')]
    for path, (base, game, *_) in loose:
        fr_by_game[game].extract(path, os.path.join(sounds, base))
    print(f'{BIG_NAME} : {len(vanilla)} voix vanilla | {len(loose)} voix AotR remplacées en VF -> {dest}')


def ecoute(dest, games, mod, rows):
    os.makedirs(dest, exist_ok=True)
    fr_by_game = {name: fr for name, _, fr in games}
    todo = [(p, r) for p, r in rows.items() if r[5] == 'à écouter']
    for path, (base, game, *_) in todo:
        stem = os.path.splitext(base)[0]
        shutil.copy(mod[path], os.path.join(dest, f'{stem}__AOTR.wav'))
        fr_by_game[game].extract(path, os.path.join(dest, f'{stem}__VF.wav'))
    print(f'{len(todo)} paires à écouter dans {dest}')
    print(f'Ajouter les noms validés (ex. {todo[0][1][0] if todo else "x.wav"}) dans {VALIDES}')


if __name__ == '__main__':
    action = sys.argv[1]
    games, mod = load()
    rows = analyse(games, mod)
    if action == 'analyse':
        out = os.path.join(ROOT, 'work', 'audio_vf.csv')
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(['fichier', 'jeu', 'durée AotR', 'durée VO vanilla', 'durée VF', 'statut'])
            for base, game, d_mod, d_en, d_fr, status in sorted(rows.values()):
                w.writerow([base, game, *(f'{d:.2f}' if d else '' for d in (d_mod, d_en, d_fr)), status])
        for s in ('sûr', 'validé', 'à écouter'):
            print(f'{s:10} {sum(r[5] == s for r in rows.values())}')
        print('liste :', out)
    elif action == 'ecoute':
        ecoute(sys.argv[2], games, mod, rows)
    elif action == 'build':
        build(sys.argv[2], games, mod, rows)
