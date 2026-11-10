"""Sous-titres des cinématiques : les passages restés en anglais (voix propres à AotR, montages).

Le moteur sait afficher des sous-titres de vidéo, mais ni EA ni AotR ne s'en servent :
  - data/ini/video.ini : « HasSubtitles = Yes » dans le bloc Video ;
  - data/english/movies/<Video>.ini (nom du bloc Video, pas du fichier) :
        SubTitles <Video>
          FontName = "Albertus MT"
          FontPitch = 18
          SubTitleType = CINEMA                       (ou HUD)
          LineTable = <15 hauteurs croissantes entre 0 et 1>
          SubTitle = Label:<étiquette> Color:R:255 G:255 B:255 Style:OUTLINED Align:CENTER Line:13 StartFrame:48 EndFrame:120
        End
    Le moteur cherche « SUBTITLE:<étiquette> » dans lotr.str ; les images comptent depuis 1, à la cadence de la vidéo.

Usage :
  python tools/soustitres.py transcrit <liste.csv> <soustitres.csv>
      Transcrit (faster-whisper) les passages laissés en anglais par cinematiques_vf.py ; ajoute les nouvelles
      lignes à soustitres.csv (clé ; vidéo ; fichier ; début ; fin ; VO ; FR) sans toucher aux lignes existantes.
  python tools/soustitres.py construit <soustitres.csv> <source_du_submod>
      Écrit data/english/movies/*.ini, data/ini/video.ini (copie de celle du mod + HasSubtitles) et ajoute les
      textes SUBTITLE:* au data/lotr.str du submod. Seules les lignes traduites (FR non vide) sont prises.
"""
import csv
import os
import re
import subprocess
import sys

import rules
import strfile

AOTR = r'C:\AgeoftheRing\aotr'
SPEECH = os.path.join(AOTR, 'data', 'audio', 'speech')
MODEL = 'medium.en'
MIN_GAP = 1.0           # passage anglais plus court : ignoré
MAX_CHARS = 60          # au-delà, une réplique est coupée en plusieurs sous-titres (selon les mots)
FONT, PITCH, LINE = 'Albertus MT', 18, 13
WIDTH = 90                      # au-delà, le sous-titre passe sur deux lignes (Line 12 et 13)
LINE_TABLE = ' '.join(f'{0.08 + 0.06 * i:.2f}' for i in range(15))
COLS = ['clé', 'vidéo', 'fichier', 'début', 'fin', 'VO', 'FR']


def english_ranges(row):
    """Passages gardés en anglais par cinematiques_vf.py : [(début, fin)] en secondes."""
    out = []
    for m in row['morceaux'].split(' | '):
        g = re.match(r'([\d.]+)-([\d.]+) AotR', m)
        if g:
            a, b = float(g[1]), float(g[2])
            if out and abs(out[-1][1] - a) < 0.01:
                out[-1][1] = b
            else:
                out.append([a, b])
    return [(a, b) for a, b in out if b - a >= MIN_GAP]


def chunks(words):
    """Coupe une réplique (liste de mots horodatés) en morceaux d'au plus MAX_CHARS caractères."""
    cur = []
    for w in words:
        if cur and len(''.join(x.word for x in cur + [w]).strip()) > MAX_CHARS:
            yield cur
            cur = []
        cur.append(w)
    if cur:
        yield cur


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f, delimiter=';'))


def write_csv(path, rows):
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLS, delimiter=';')
        w.writeheader()
        w.writerows(rows)


def transcrit(liste, out):
    from faster_whisper import WhisperModel
    model = WhisperModel(MODEL, device='cpu', compute_type='int8')
    rows = read_csv(out)
    done = {r['fichier'] for r in rows}
    for r in read_csv(liste):
        ranges = english_ranges(r)
        if not ranges or r['fichier'] in done:
            continue
        clip = os.path.join(SPEECH, r['fichier'] + '.mp3')
        segs, _ = model.transcribe(clip, language='en', word_timestamps=True, vad_filter=True)
        n = 0
        for s in segs:
            for part in chunks(s.words or []):
                a, b = part[0].start, part[-1].end
                if not any(lo - 0.3 <= (a + b) / 2 <= hi + 0.3 for lo, hi in ranges):
                    continue                    # réplique déjà doublée (VF des films ou d'EA)
                n += 1
                rows.append({'clé': f'AOTRFR_{r["fichier"].replace(" ", "")}_{n:02d}', 'vidéo': r['vidéo'],
                             'fichier': r['fichier'], 'début': f'{a:.2f}', 'fin': f'{b:.2f}',
                             'VO': ''.join(w.word for w in part).strip(), 'FR': ''})
        print(f'{r["fichier"]:24} {n:3} sous-titres', flush=True)
        write_csv(out, rows)


def fps(video_file):
    """Cadence de la vidéo : celle du mod, sinon celle des jeux de base du launcher (vidéos vanilla)."""
    path = next(p for base in (AOTR, r'C:\AgeoftheRing\rotwk', r'C:\AgeoftheRing\bfme2')
                for p in [os.path.join(base, 'data', 'movies', video_file + '.vp6')] if os.path.exists(p))
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate',
                          '-of', 'csv=p=0', path], capture_output=True, text=True).stdout.strip()
    num, den = out.split('/')
    return int(num) / int(den)


def video_files():
    """nom du bloc Video -> fichier (data/ini/video.ini du mod)."""
    out, name = {}, None
    with open(os.path.join(AOTR, 'data', 'ini', 'video.ini'), encoding='cp1252') as f:
        for line in f:
            s = line.split(';')[0].split('//')[0].strip()
            if s.startswith('Video '):
                name = s.split()[1]
            elif name and s.startswith('Filename') and '=' in s:
                out[name] = s.split('=', 1)[1].strip()
                name = None
    return out


def construit(table, dest):
    rows = [r for r in read_csv(table) if r['FR'].strip()]
    by_video = {}
    for r in rows:
        by_video.setdefault(r['vidéo'], []).append(r)
    files = video_files()
    movies = os.path.join(dest, 'data', 'english', 'movies')
    os.makedirs(movies, exist_ok=True)
    texts = {}                                  # étiquette -> texte ; une ligne trop longue passe sur deux lignes
    for video, subs in by_video.items():
        rate = fps(files[video])
        lines = [f'; Sous-titres FR (tools/soustitres.py) - {files[video]}.vp6, {rate:g} images/s',
                 f'SubTitles {video}', f'  FontName = "{FONT}"', f'  FontPitch = {PITCH}', '  SubTitleType = CINEMA',
                 f'  LineTable = {LINE_TABLE}']
        subs = sorted(subs, key=lambda r: float(r['début']))
        for i, r in enumerate(subs):
            start, end = float(r['début']), float(r['fin'])
            nxt = float(subs[i + 1]['début']) - 0.1 if i + 1 < len(subs) else end + 2
            end = min(nxt, max(end + 0.4, start + 1.2))       # le temps de lire, sans chevaucher le suivant
            a = max(1, round(start * rate) + 1)
            b = max(a + 1, round(end * rate) + 1)
            parts = rules.wrap(r['FR'].strip(), WIDTH).split('\\n')
            for j, part in enumerate(parts):
                label = r['clé'] + (f'_{j + 1}' if j else '')
                texts[label] = part
                lines.append(f'  SubTitle = Label:{label} Color:R:255 G:255 B:255 Style:OUTLINED Align:CENTER '
                             f'Line:{LINE - len(parts) + 1 + j} StartFrame:{a} EndFrame:{b}')
        lines.append('End')
        with open(os.path.join(movies, video + '.ini'), 'w', encoding='cp1252', newline='') as f:
            f.write('\r\n'.join(lines) + '\r\n')
    # video.ini : celle du mod, avec HasSubtitles dans les blocs concernés
    with open(os.path.join(AOTR, 'data', 'ini', 'video.ini'), encoding='cp1252', newline='') as f:
        ini = f.read()
    for video in by_video:
        ini, n = re.subn(rf'(?m)^(Video {re.escape(video)}[ \t]*\r?\n)', r'\1\tHasSubtitles = Yes\r\n', ini)
        assert n == 1, video
    os.makedirs(os.path.join(dest, 'data', 'ini'), exist_ok=True)
    with open(os.path.join(dest, 'data', 'ini', 'video.ini'), 'w', encoding='cp1252', newline='') as f:
        f.write(ini)
    # textes : ajoutés à la fin du lotr.str du submod
    path = os.path.join(dest, 'data', 'lotr.str')
    items = [i for i in strfile.read(path).items
             if not (isinstance(i, strfile.Entry) and i.lkey.startswith('subtitle:aotrfr_'))]
    items += [strfile.Entry(key=f'SUBTITLE:{label}', line=0, body=[rules.french_typography(f'"{text}"')])
              for label, text in texts.items()]
    strfile.write(path, items)
    print(f'sous-titres : {len(rows)} dans {len(by_video)} vidéos -> {movies}')


if __name__ == '__main__':
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    {'transcrit': transcrit, 'construit': construit}[sys.argv[1]](*sys.argv[2:4])
