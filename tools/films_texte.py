"""Texte français des répliques de campagne tirées des films : ce que dit le doublage (work/voix_vf).

On connaît pour chaque réplique le film et la seconde où elle commence (work/voix_vf/liste.csv, colonne « morceaux »,
pour cinematiques_vf.py --voix ; liste_texte*.csv pour films_voix.py). Pour chacune on relève :
  - « FR doublage » : la piste française du film transcrite autour de ce moment (fenêtres de ±20 s fusionnées, Whisper
    a le contexte de la scène), faster-whisper medium sur la carte graphique, noms de la VF des films en amorce ;
  - « sous-titres FR » : la piste de sous-titres français complets du même fichier (même minutage).
Le doublage donne la formulation (règle : on reprend le texte qu'on entend en VF, pas les sous-titres, reformulés pour
la lecture) ; les sous-titres donnent l'orthographe des noms et rattrapent ce que Whisper entend mal. Les deux sont
réconciliés à la relecture (lots CSV), puis --applique.

Réglages repris du projet Shire (outils/whisper_gpu.py, 15/11/2026) : medium écrit mieux les noms que large-v3 (essai du
23/11 : « athelas » juste en medium, « athélas » en large-v3 ; ni l'un ni l'autre n'entend « Grands-Pas », d'où les
sous-titres) ; pas de vad_filter (il saute du texte).

À lancer avec le Python du projet Shire (faster-whisper + CUDA) :
  ..\\Shire\\.venv\\Scripts\\python.exe tools\\films_texte.py
  ..\\Shire\\.venv\\Scripts\\python.exe tools\\films_texte.py --applique <relu.csv>   (colonnes fichier ; FR)
Résultat : work/voix_vf/texte_fr.csv. Transcriptions et sous-titres gardés dans work/voix_vf/cache/ (relance rapide).
"""
import csv
import json
import os
import re
import shutil
import subprocess
import sys

import cinematiques_vf as cv
import doublage
import films_voix

OUT = os.path.join(doublage.ROOT, 'work', 'voix_vf')
CACHE = os.path.join(OUT, 'cache')
REPORT = os.path.join(OUT, 'texte_fr.csv')
DUBBING = os.path.join(doublage.ROOT, 'work', 'doublage', 'repliques.csv')
CONTEXT = 20.0                     # secondes de contexte avant et après chaque réplique
BEFORE, AFTER = 0.15, 1.0          # un mot compte si son milieu tombe dans [début - BEFORE, fin + AFTER] (la VF déborde)
MODEL = 'medium'
PROMPT = ('Frodon Sacquet, Bilbon, Sam Gamegie, Merry, Pippin, Gandalf, Grands-Pas, Aragorn, Legolas, Gimli, Boromir, '
          'Faramir, Denethor, Saroumane, Sauron, Mordor, Gondor, Rohan, Théoden, Éowyn, Éomer, Langue de Serpent, '
          'Fondcombe, Elrond, Arwen, Galadriel, Lothlórien, Moria, Balrog, Isengard, Orthanc, Fangorn, Sylvebarbe, '
          'athelas, Dard, Sméagol, Gollum, Nazgûl, Isildur, Minas Tirith, Osgiliath, Edoras, Gouffre de Helm, Arachne, '
          'Uruk-hai, la Comté, Hobbits, Orques, Mont Destin.')


def placements():
    """{fichier: (chemin du film, début en s, durée en s)} pour les répliques de work/voix_vf."""
    wavs = {f[:-4] for f in os.listdir(OUT) if f.endswith('.wav') and '__' not in f}
    out = {}
    texte = [r for n in ('liste_texte_passe1.csv', 'liste_texte.csv')     # la 2e passe n'a repris que les restes
             if os.path.exists(os.path.join(OUT, n)) for r in doublage.read(os.path.join(OUT, n))]
    for r in texte:
        if r['retenue'] == 'oui' and r['fichier'] in wavs:
            out[r['fichier']] = (films_voix.film_path(r['film']), float(r['temps (s)']))
    for r in doublage.read(os.path.join(OUT, 'liste.csv')):           # calage par le son : prioritaire
        m = re.match(r'(.+) ([\d.]+)s corrélation', r['morceaux'])
        if m and r['fichier'] in wavs:
            path = os.path.join(cv.FILMS_DIR, m[1] + '.mkv')
            if os.path.exists(path):
                out[r['fichier']] = (path, float(m[2]))
    return {f: (p, t, doublage.duration(os.path.join(OUT, f + '.wav'))) for f, (p, t) in out.items()}


def windows(lines):
    """Fenêtres [début, fin] fusionnées autour des répliques d'un film."""
    spans = sorted((max(0.0, t - CONTEXT), t + d + CONTEXT) for t, d in lines)
    out = []
    for a, b in spans:
        if out and a <= out[-1][1] + 5:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def cache_key(path):
    return re.sub(r'[^\w]+', '_', os.path.splitext(os.path.basename(path))[0])[:60]


def load_model():
    from faster_whisper import WhisperModel
    try:
        return WhisperModel(MODEL, device='cuda', compute_type='int8_float16')
    except Exception as e:          # pas de CUDA : beaucoup plus lent
        print(f'{MODEL} sur le processeur ({str(e)[:80]})')
        return WhisperModel(MODEL, device='cpu', compute_type='int8')


def transcribe(path, wins, model):
    """[(début, fin, mot)] des fenêtres (temps du film), avec cache par film et par modèle."""
    cache_path = os.path.join(CACHE, f'whisper_{MODEL}_{cache_key(path)}.json')
    cache = json.load(open(cache_path, encoding='utf-8')) if os.path.exists(cache_path) else {}
    stream = next(i for i, lang in cv.audio_streams(path) if lang in ('fre', 'fra'))     # première piste française
    words = []
    for i, (a, b) in enumerate(wins, 1):
        wkey = f'{a:.2f}-{b:.2f}'
        if wkey not in cache:
            audio = cv.decode(path, stream, sr=16000, start=a, dur=b - a)
            segs, _ = model.transcribe(audio, language='fr', beam_size=5, word_timestamps=True,
                                       condition_on_previous_text=False, initial_prompt=PROMPT)
            cache[wkey] = [(a + w.start, a + w.end, w.word) for s in segs for w in (s.words or [])]
            os.makedirs(CACHE, exist_ok=True)
            json.dump(cache, open(cache_path, 'w', encoding='utf-8'), ensure_ascii=False)
            print(f'  {os.path.basename(path)[:40]} : fenêtre {i}/{len(wins)} ({b - a:.0f} s)', flush=True)
        words += cache[wkey]
    return words


def subtitles(path):
    """[(début, fin, texte)] de la piste de sous-titres français complets (texte) du film."""
    dest = os.path.join(CACHE, f'soustitres_fr_{cache_key(path)}.srt')
    if not os.path.exists(dest):
        info = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 's', '-show_entries',
                               'stream=codec_name:stream_tags=language,title', '-of', 'csv=p=0', path],
                              capture_output=True, text=True, encoding='utf-8').stdout.splitlines()
        tracks = [(i, ln) for i, ln in enumerate(info) if ln.startswith('subrip') and re.search(r'(?i)fre|fra', ln)]
        full = [i for i, ln in tracks if not re.search(r'(?i)forc|comment', ln)]
        if not full:
            return []
        os.makedirs(CACHE, exist_ok=True)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', path, '-map', f'0:s:{full[0]}', dest], check=True)
    out = []
    for block in re.split(r'\n\s*\n', open(dest, encoding='utf-8', errors='replace').read()):
        m = re.search(r'(\d+):(\d+):(\d+)[,.](\d+) --> (\d+):(\d+):(\d+)[,.](\d+)\s*\n(.*)', block, re.S)
        if m:
            g = [int(x) for x in m.groups()[:8]]
            text = re.sub(r'<[^>]+>|\{[^}]*\}', '', m[9]).replace('\n', ' ').strip()
            out.append((g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000, g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000,
                        text))
    return out


def text_between(words, t, d):
    said = [w for s, e, w in words if t - BEFORE <= (s + e) / 2 <= t + d + AFTER]
    text = re.sub(r'\s+', ' ', ''.join(said)).strip()
    return text[:1].upper() + text[1:]


def subs_between(subs, t, d):
    return ' / '.join(x for a, b, x in subs if a < t + d + AFTER and b > t + 0.2)


def main():
    place = placements()
    rows = {r['fichier']: r for r in doublage.read(DUBBING)}
    by_film = {}
    for f, (p, t, d) in place.items():
        by_film.setdefault(p, []).append((f, t, d))
    model, report = None, []
    for path, lines in sorted(by_film.items()):
        wins = windows([(t, d) for _, t, d in lines])
        print(f'{os.path.basename(path)} : {len(lines)} répliques, {len(wins)} fenêtres, '
              f'{sum(b - a for a, b in wins) / 60:.0f} min', flush=True)
        if model is None:
            model = load_model()
        words, subs = transcribe(path, wins, model), subtitles(path)
        for f, t, d in sorted(lines, key=lambda x: x[1]):
            r = rows.get(f, {})
            report.append({'fichier': f, 'personnage': r.get('personnage', ''), 'film': os.path.basename(path),
                           'temps (s)': f'{t:.2f}', 'durée (s)': f'{d:.1f}', 'VO': r.get('VO', ''),
                           'FR actuelle': r.get('FR', ''), 'FR doublage': text_between(words, t, d),
                           'sous-titres FR': subs_between(subs, t, d)})
    with open(REPORT, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(report[0]), delimiter=';')
        w.writeheader()
        w.writerows(report)
    print(f'{len(report)} répliques -> {REPORT} ; sans transcription : '
          f'{sum(1 for r in report if not r["FR doublage"])}, sans sous-titre : '
          f'{sum(1 for r in report if not r["sous-titres FR"])}')


def apply(reviewed):
    """Reporte la colonne FR d'un CSV relu (fichier ; FR) dans work/doublage/repliques.csv (sauvegarde avant)."""
    new = {r['fichier']: r['FR'].strip() for r in doublage.read(reviewed) if r.get('FR', '').strip()}
    shutil.copy(DUBBING, os.path.join(os.path.dirname(DUBBING), 'historique', 'repliques_avant_films_texte.csv'))
    table, n = doublage.read(DUBBING), 0
    for r in table:
        if r['fichier'] in new and new[r['fichier']] != r['FR']:
            r['FR'] = new[r['fichier']]
            r['remarque'] = re.sub(r'texte du doublage des films \([^)]*\)', '', r['remarque']).strip(' ;')
            r['remarque'] = ('texte du doublage des films (films_texte.py) ; ' + r['remarque']).strip(' ;')
            n += 1
    doublage.write(DUBBING, table)
    print(f'{n} répliques remplacées par le texte du doublage dans {DUBBING}')


if __name__ == '__main__':
    if '--applique' in sys.argv:
        apply(sys.argv[sys.argv.index('--applique') + 1])
    else:
        main()
