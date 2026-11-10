"""Répliques de campagne tirées des films, retrouvées par le texte (complète cinematiques_vf.py --voix).

La recherche par le son seule rate beaucoup de répliques courtes. Ici on cherche d'abord le texte anglais de la
réplique (work/doublage/repliques.csv) dans les sous-titres anglais des films, puis on cale le son dans une fenêtre
de 40 s autour du sous-titre (corrélation de la forme d'onde, bande 300–3400 Hz). Si le son correspond, la VF du
même passage remplace la réplique -> work/voix_vf/<fichier>.wav (au format du fichier d'origine).

Usage : python tools/films_voix.py [--controle] [--seuil 0.5]
  --controle : écrit aussi <fichier>__VO.wav (passage VO des films) pour vérifier à l'écoute.
Résultat : work/voix_vf/liste_texte.csv (fichier ; film ; temps ; texte ; corrélation ; retenue).
"""
import collections
import csv
import difflib
import glob
import os
import re
import subprocess
import sys

import numpy as np

import cinematiques_vf as cv
import doublage

FILMS = {   # versions longues avec sous-titres anglais en texte ; le son VF est pris dans le même fichier
    'fotr': 'lotr 1.mkv',
    'tt': '*Two Towers*Extended*.mkv',
    'rotk': '*Return of the King*Extended*.mkv',
    'hob1': 'Le Hobbit - Un voyage inattendu.mkv',
    'hob3': 'Le Hobbit - La Bataille des cinqs armées.mkv',
}
OUT = os.path.join(doublage.ROOT, 'work', 'voix_vf')
SRT = os.path.join(doublage.ROOT, 'work', 'cinematiques', 'srt_en')
BEFORE, AFTER = 15.0, 25.0          # fenêtre de recherche autour du début du sous-titre
PROCHE = 0.3                        # corrélation suffisante si le son tombe à moins de 2,5 s du sous-titre


def words(t):
    return re.sub(r'[^a-z ]', '', re.sub(r'<[^>]+>|\[.*?\]|-', ' ', t.lower())).split()


def film_path(key):
    return glob.glob(os.path.join(cv.FILMS_DIR, FILMS[key]))[0]


def subtitles():
    """[(film, début en s, mots)] ; extrait les pistes de sous-titres anglaises (texte, sans SDH) si besoin."""
    os.makedirs(SRT, exist_ok=True)
    out = []
    for key in FILMS:
        dest = os.path.join(SRT, key + '.srt')
        if not os.path.exists(dest):
            info = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 's', '-show_entries',
                                   'stream=index,codec_name:stream_tags=language,title', '-of', 'csv=p=0',
                                   film_path(key)], capture_output=True, text=True, encoding='utf-8').stdout
            idx = [ln.split(',')[0] for ln in info.splitlines()
                   if ',subrip,eng' in ln and 'SDH' not in ln]
            if not idx:
                print(f'{key} : pas de sous-titres anglais en texte')
                continue
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', film_path(key), '-map', f'0:{idx[0]}', dest],
                           check=True)
        for block in re.split(r'\n\s*\n', open(dest, encoding='utf-8-sig', errors='replace').read()):
            lines = block.strip().splitlines()
            if len(lines) >= 3 and '-->' in lines[1]:
                h, m, s = lines[1].split(' --> ')[0].replace(',', '.').split(':')
                out.append((key, int(h) * 3600 + int(m) * 60 + float(s), words(' '.join(lines[2:]))))
    return out


def contained(w, sub):
    """Part des mots de la réplique retrouvés dans l'ordre dans le sous-titre (la réplique peut n'en être qu'un
    morceau, mais pas un sous-titre bien plus long)."""
    if len(sub) > len(w) + 12:
        return 0.0
    blocks = difflib.SequenceMatcher(None, w, sub, autojunk=False).get_matching_blocks()
    return sum(b.size for b in blocks) / len(w)


def match_text(rows, subs, threshold=0.85):
    """{fichier: [(film, temps, score)…]} : jusqu'à 5 suites de 1 à 3 sous-titres qui contiennent la réplique
    (une phrase courte peut se trouver dans plusieurs films : le son tranche)."""
    windows = []
    for i in range(len(subs)):
        for n in (1, 2, 3):
            if i + n <= len(subs) and len({s[0] for s in subs[i:i + n]}) == 1:
                windows.append((subs[i][0], subs[i][1], sum((s[2] for s in subs[i:i + n]), [])))
    index = collections.defaultdict(set)
    for j, (_, _, w) in enumerate(windows):
        for x in set(w):
            index[x].add(j)
    out = {}
    for r in rows:
        w = words(r['VO'])
        if len(w) < 3:
            continue
        cand = collections.Counter(j for x in set(w) if len(index[x]) < 400 for j in index[x])
        scored = sorted(((contained(w, windows[j][2]), j) for j, _ in cand.most_common(30)), reverse=True)
        found, seen = [], set()
        for score, j in scored:
            film, t, _ = windows[j]
            if score >= threshold and (film, round(t)) not in seen and len(found) < 5:
                seen.add((film, round(t)))
                found.append((film, t, score))
        if found:
            out[r['fichier']] = found
    return out


def locate(clip, path, eng, t):
    """Position (s) du clip dans la VO du film près de t, et corrélation normalisée (bande de la voix)."""
    x = cv.bandpass(cv.decode(clip, sr=cv.FINE_SR))
    s0 = max(0.0, t - BEFORE)
    y = cv.bandpass(cv.decode(path, eng, sr=cv.FINE_SR, start=s0, dur=BEFORE + AFTER + len(x) / cv.FINE_SR))
    n = len(x)
    if len(y) < n or np.linalg.norm(x) < 1e-3:
        return t, 0.0
    size = 1 << int(np.ceil(np.log2(len(y) + n)))
    num = np.fft.irfft(np.fft.rfft(y, size) * np.conj(np.fft.rfft(x, size)), size)[:len(y) - n + 1]
    energy = np.concatenate([[0.0], np.cumsum(y.astype(np.float64) ** 2)])
    den = np.sqrt(energy[n:] - energy[:-n]) * np.linalg.norm(x) + 1e-9
    corr = np.abs(num) / den
    j = int(np.argmax(corr))
    return s0 + j / cv.FINE_SR, float(corr[j])


def main(argv):
    controle = '--controle' in argv
    seuil = float(argv[argv.index('--seuil') + 1]) if '--seuil' in argv else 0.5
    rows = [r for r in doublage.read(os.path.join(doublage.ROOT, 'work', 'doublage', 'repliques.csv'))
            if r['statut'] == 'à doubler' and r['source'] != 'à transcrire']
    os.makedirs(OUT, exist_ok=True)
    done = {os.path.splitext(f)[0].lower() for f in os.listdir(OUT) if f.endswith('.wav')}
    hits = match_text([r for r in rows if r['fichier'].lower() not in done], subtitles())
    print(f'{len(hits)} répliques retrouvées dans les sous-titres des films')
    streams = {k: dict((lang, i) for i, lang in cv.audio_streams(film_path(k))) for k in FILMS}
    by = {r['fichier']: r for r in rows}
    report, kept = [], 0
    for n, (name, found) in enumerate(sorted(hits.items()), 1):
        clip = os.path.join(doublage.SOUNDS, name + '.wav')
        tried = []
        for f, t, s in found:
            start, corr = locate(clip, film_path(f), streams[f]['eng'], t)
            # le son colle franchement, ou moins nettement (musique d'AotR par-dessus) mais juste au moment du sous-titre
            good = corr >= seuil or (corr >= PROCHE and abs(start - t) <= 2.5)
            tried.append((good, corr, start, f, t, s))
        ok, corr, start, film, t, score = max(tried)
        path, st = film_path(film), streams[film]
        if ok:
            dur = doublage.duration(clip)
            aotr = cv.decode(clip, sr=cv.OUT_SR, channels=2).reshape(-1, 2)
            vo, vf = cv.stereo(path, st['eng'], start, dur), cv.stereo(path, st['fre'], start, dur)
            g = cv.rms(aotr) / cv.rms(vo)
            cv.encode(vf * g, os.path.join(OUT, name + '.wav'), clip)
            if controle:
                cv.encode(vo * g, os.path.join(OUT, name + '__VO.wav'), clip)
            kept += 1
        report.append([name, film, f'{t:.1f}', by[name]['VO'], f'{score:.2f}', f'{corr:.2f}', 'oui' if ok else 'non'])
        if n % 50 == 0:
            print(f'{n}/{len(hits)} ; {kept} retenues', flush=True)
    with open(os.path.join(OUT, 'liste_texte.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['fichier', 'film', 'temps (s)', 'texte', 'score texte', 'corrélation', 'retenue'])
        w.writerows(report)
    print(f'{kept} répliques en VF des films sur {len(hits)} retrouvées par le texte -> {OUT}')


if __name__ == '__main__':
    main(sys.argv[1:])
