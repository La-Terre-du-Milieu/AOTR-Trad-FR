"""Cinématiques en VF : retrouve le son des vidéos d'AotR dans les films et les jeux EA, et y pose la VF.

AotR lit le son de ses vidéos à part (data/audio/speech/<nom>.mp3, voir data/ini/speech.ini). Ces extraits sont
montés à partir des films de P. Jackson ou des cinématiques d'EA. Pour chaque extrait :
  1. chaque morceau est recherché dans les sources (flux spectral par bandes, à 10 puis 50 trames/s) ;
  2. calage fin à 8 kHz : décalage et vitesse (24 contre 23,976 i/s) ;
  3. la VF de la source est posée au même endroit, au niveau sonore d'AotR. Le reste (montage, musique
     ou narration propres à AotR) est gardé tel quel.

Usage : python tools/cinematiques_vf.py <sortie> [<extrait> ou "<motif*>"…] [--controle] [--sans-ea] [--voix]
  Sans extrait : tout data/audio/speech du mod. Écrit <sortie>/<nom>.mp3 (VF) et <sortie>/liste.csv.
  --controle : écrit aussi <nom>__VO.mp3, le même montage avec la VO de la source (doit sonner comme AotR).
  --voix : répliques isolées (data/audio/sounds/mgfotr_*.wav) : une seule recherche par fichier, sur les bandes
     de la voix, validée au signal près (corrélation > 0,5 entre 300 et 3 400 Hz) ; films seulement.
     ~4 % des répliques de la campagne 10.0 viennent des films, les autres sont enregistrées par AotR.
Sources : les films de FILMS (pistes « eng » et « fre ») et les voix VO/VF des jeux EA (EA_SPEECH).
Les VF des films sont sous droits : ne jamais les mettre dans le dépôt.
"""
import csv
import glob
import json
import os
import re
import shutil
import subprocess
import sys

import numpy as np

from bigfile import BigFile

AOTR = r'C:\AgeoftheRing\aotr'
FILMS_DIR = r'C:\Users\Paulr\Videos\lotr'
FILMS = ["Le Seigneur des Anneaux - La Communauté de l'Anneau.mkv",
         'Le Seigneur des Anneaux - Les deux Tours.mkv',
         'Le Seigneur des Anneaux - Le retour du Roi.mkv',
         'Le Hobbit - Un voyage inattendu.mkv',
         'Le Hobbit La Désolation De Smaug.mkv',
         'Le Hobbit - La Bataille des cinqs armées.mkv']
EA = r'C:\Program Files (x86)\Electronic Arts'
# (archive VO, archive VF) des voix des jeux
EA_SPEECH = [(os.path.join(r'C:\AgeoftheRing\rotwk', 'lang', 'englishaudio.big'),
              os.path.join(EA, "L'Avènement du Roi-sorcier", 'lang', 'frenchaudio.big')),
             (os.path.join(r'C:\AgeoftheRing\bfme2', 'lang', 'englishaudio.big'),
              os.path.join(EA, 'La Bataille pour la Terre du Milieu II', 'lang', 'FrenchAudio.big'))]

SR, HOP, WIN = 4000, 80, 256      # analyse : 50 trames/s
FPS = SR / HOP
COARSE = 5                        # recherche globale à 10 trames/s
BLOCK = 0.25                      # résolution du découpage en morceaux (s)
MIN_SCORE = 0.25                  # en dessous : pas de correspondance
FINE_SR = 8000
OUT_SR = 48000


def audio_streams(path):
    """[(n° de piste audio, langue)]"""
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries',
                          'stream=index:stream_tags=language', '-of', 'json', path],
                         capture_output=True, text=True).stdout
    return [(i, s.get('tags', {}).get('language', '')) for i, s in enumerate(json.loads(out)['streams'])]


def duration(path):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0',
                                 path], capture_output=True, text=True).stdout)


def decode(path, stream=0, sr=SR, start=None, dur=None, channels=1):
    cmd = ['ffmpeg', '-v', 'error']
    if start is not None:
        cmd += ['-ss', f'{start:.4f}']
    cmd += ['-i', path, '-map', f'0:a:{stream}']
    if dur is not None:
        cmd += ['-t', f'{dur:.4f}']
    cmd += ['-ac', str(channels), '-ar', str(sr), '-f', 'f32le', '-']
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def features(x):
    """Flux spectral par bandes (log) : robuste au gain et au mixage."""
    n = max(0, (len(x) - WIN) // HOP)
    idx = np.arange(WIN)[None, :] + HOP * np.arange(n)[:, None]
    win = np.hanning(WIN).astype(np.float32)
    edges = np.unique(np.geomspace(2, WIN // 2, 17).astype(int))
    feats = []
    for s in range(0, n, 200000):       # par morceaux pour la mémoire
        spec = np.abs(np.fft.rfft(x[idx[s:s + 200000]] * win, axis=1))
        bands = np.stack([spec[:, a:b].sum(1) for a, b in zip(edges[:-1], edges[1:])], 1)
        feats.append(np.log1p(bands * 100))
    f = np.concatenate(feats) if feats else np.zeros((0, len(edges) - 1), np.float32)
    flux = np.maximum(np.diff(f, axis=0, prepend=f[:1]), 0)
    return (flux - flux.mean(0)).astype(np.float32)


def coarse(F):
    n = len(F) // COARSE
    C = np.asarray(F[:n * COARSE]).reshape(n, COARSE, -1).sum(1)
    return C - C.mean(0)


class Source:
    """Une VO et sa VF calées dans le temps : (fichier, n° de piste) chacune."""

    def __init__(self, name, eng, fre, cache, bands=None):
        self.name, self.eng, self.fre = name, eng, fre
        p = os.path.join(cache, re.sub(r'[^\w.-]+', '_', name) + '_eng.npy')
        if not os.path.exists(p):
            np.save(p, features(decode(*eng)))
        self.F = np.load(p, mmap_mode='r')
        if bands is not None:                       # bandes de la voix seulement
            F = self.F[:, bands]
            self.F = np.ascontiguousarray(F - F.mean(0)).astype(np.float32)
        self.C = coarse(self.F).astype(np.float32)
        self.n = 1 << int(np.ceil(np.log2(len(self.C) + int(8 * FPS / COARSE))))
        self.spec = np.fft.rfft(self.C, self.n, axis=0)
        self.energy = np.concatenate([[0], np.cumsum((self.C.astype(np.float64) ** 2).sum(1))])

    def search(self, Wc, rW):
        """Position la plus probable (trame à 50/s) d'une fenêtre de l'extrait, à COARSE trames près."""
        t = len(Wc)
        if t > len(self.C):
            return None
        r = np.fft.irfft((self.spec * np.conj(rW)).sum(1), self.n)[:len(self.C) - t + 1]
        den = np.sqrt(np.maximum(self.energy[t:] - self.energy[:-t], 0)) * np.sqrt((Wc.astype(np.float64) ** 2).sum())
        return int(np.argmax(r / (den + 1e-9))) * COARSE

    def local(self, W, k):
        """Score de la fenêtre W posée à la trame k de la source."""
        if k < 0 or k + len(W) > len(self.F):
            return -1.0
        X = self.F[k:k + len(W)]
        return float((X * W).sum() / (np.sqrt((X ** 2).sum() * (W ** 2).sum()) + 1e-9))


def find(W, sources, cache_fft):
    """Meilleure source pour la fenêtre W : (n° de source, trame, score), calée à la trame près."""
    Wc = coarse(W)
    best = (None, 0, -1.0)
    for si, s in enumerate(sources):
        if s.n not in cache_fft:
            cache_fft[s.n] = np.fft.rfft(Wc, s.n, axis=0)
        k = s.search(Wc, cache_fft[s.n])
        if k is None:
            continue
        for kk in range(k - COARSE, k + COARSE + 1):
            sc = s.local(W, kk)
            if sc > best[2]:
                best = (si, kk, sc)
    return best


def segment(C, sources):
    """Découpe l'extrait en morceaux [(source, décalage) ou None, début, fin, score] (s)."""
    w, cands = int(4 * FPS), set()
    for a in range(0, max(1, len(C) - w + 1), int(2 * FPS)):
        si, k, s = find(C[a:a + w], sources, {})
        if s >= MIN_SCORE:
            cands.add((si, k - a))
    nb, half = int(len(C) / (BLOCK * FPS)), int(0.75 * FPS)
    choice = []
    for b in range(nb):
        c0 = int(b * BLOCK * FPS)
        lo, hi = max(0, c0 - half), min(len(C), c0 + half)
        best = (None, MIN_SCORE)
        for si, off in cands:
            s = sources[si].local(C[lo:hi], off + lo)
            if s > best[1]:
                best = ((si, off), s)
        choice.append(best)
    labels = [c[0] for c in choice]
    for i in range(1, len(labels) - 1):          # un bloc isolé prend la valeur de ses voisins
        if labels[i - 1] == labels[i + 1] != labels[i]:
            labels[i] = labels[i - 1]

    def same(x, y):      # même plan : même source et même décalage (à 0,1 s près)
        return x == y or (x is not None and y is not None and x[0] == y[0] and abs(x[1] - y[1]) <= 0.1 * FPS)
    runs = []
    for i, lab in enumerate(labels):
        if runs and same(runs[-1][0], lab):
            runs[-1][2] = i + 1
        else:
            runs.append([lab, i, i + 1])
    out = []
    for lab, a, b in runs:
        score = float(np.mean([choice[j][1] for j in range(a, b)]))
        if lab is not None and (b - a) * BLOCK < 1.0 and score < 0.4:
            lab = None                               # trop court et trop incertain
        if out and same(out[-1][0], lab):
            out[-1][2] = b * BLOCK
        else:
            out.append([lab, a * BLOCK, b * BLOCK, score])
    return out


def refine(clip8k, src, start, clip_start, dur):
    """Calage fin sur des fenêtres de 1 s, droite ajustée -> (début, vitesse, qualité).

    vitesse > 1 : la source est plus lente qu'AotR (24 contre 23,976 i/s), on l'accélère d'autant."""
    margin = 0.6
    s0 = max(0.0, start - margin)
    seg = decode(*src.eng, sr=FINE_SR, start=s0, dur=dur + 2 * margin)
    base = start - s0
    pts = []
    for t in np.arange(0, max(dur - 1, 0.01), 2.0 if dur > 6 else 1.0):
        i = int((clip_start + t) * FINE_SR)
        x = clip8k[i:i + FINE_SR]
        j0 = int((base + t - 0.5) * FINE_SR)
        y = seg[max(0, j0):j0 + 2 * FINE_SR]
        if len(x) < FINE_SR // 2 or len(y) < len(x) or np.linalg.norm(x) < 1e-3:
            continue
        r = np.correlate(y, x, 'valid')
        j = int(np.argmax(r))
        c = r[j] / (np.linalg.norm(x) * np.linalg.norm(y[j:j + len(x)]) + 1e-9)
        if c > 0.5:
            pts.append((t, (max(0, j0) + j) / FINE_SR - (base + t), c))
    if not pts:
        return start, 1.0, 0.0
    ts, ds = np.array([p[0] for p in pts]), np.array([p[1] for p in pts])
    slope = np.polyfit(ts, ds, 1)[0] if len(pts) >= 3 and np.ptp(ts) >= 4 else 0.0
    return start + float(np.median(ds - slope * ts)), 1.0 + float(slope), float(np.mean([p[2] for p in pts]))


def stereo(path, stream, start, dur, speed=1.0):
    """Morceau stéréo 48 kHz de `dur` s ; speed != 1 : lu sur dur*speed puis ramené à dur."""
    lead = max(0.0, -start)
    cmd = ['ffmpeg', '-v', 'error', '-ss', f'{max(0.0, start):.4f}', '-i', path, '-map', f'0:a:{stream}',
           '-t', f'{(dur - lead) * speed + 0.05:.4f}', '-ac', '2', '-ar', str(OUT_SR)]
    if abs(speed - 1) > 1e-5:
        cmd += ['-af', f'atempo={speed:.6f}']
    raw = subprocess.run(cmd + ['-f', 'f32le', '-'], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)
    x = np.concatenate([np.zeros((int(round(lead * OUT_SR)), 2), np.float32), x])
    n = int(round(dur * OUT_SR))
    return np.pad(x, ((0, max(0, n - len(x))), (0, 0)))[:n]


def rms(x):
    return float(np.sqrt((x ** 2).mean()) + 1e-9)


def voice_gap(vo, vf):
    """Écart VO/VF dans la bande de la voix (0 : même son, donc pas de dialogue ; ~1 : dialogue)."""
    def env(x):
        x = x.mean(1)
        n = len(x) // 1920                      # trames de 40 ms
        spec = np.abs(np.fft.rfft(x[:n * 1920].reshape(n, 1920), axis=1)) ** 2
        return np.log1p(spec[:, 12:136].sum(1) * 1e3)    # 300 à 3 400 Hz
    a, b = env(vo), env(vf)
    if len(a) < 5:
        return 0.0
    a, b = a - a.mean(), b - b.mean()
    return float(1 - (a * b).sum() / (np.sqrt((a ** 2).sum() * (b ** 2).sum()) + 1e-9))


def encode(y, dest, like):
    """mp3 224k, ou .wav au format de l'original `like` (voix de data/audio/sounds : PCM 16 bits)."""
    if dest.lower().endswith('.wav'):
        fmt = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries',
                              'stream=sample_rate,channels', '-of', 'csv=p=0', like],
                             capture_output=True, text=True).stdout.strip().split(',')
        codec = ['-c:a', 'pcm_s16le', '-ar', fmt[0], '-ac', fmt[1]]
    else:
        codec = ['-c:a', 'libmp3lame', '-b:a', '224k']
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(OUT_SR), '-ac', '2', '-i', '-',
                    *codec, dest], input=np.clip(y, -1, 1).astype(np.float32).tobytes(), check=True)


def build(clip, sources, out_dir, controle=False):
    """VF d'un extrait. Renvoie (part en VF, écart VO/VF, sources, détail des morceaux)."""
    name = os.path.splitext(os.path.basename(clip))[0]
    raw = decode(clip)
    total = len(raw) / SR
    segs = segment(features(raw), sources)
    clip8k = decode(clip, sr=FINE_SR)
    aotr = decode(clip, sr=OUT_SR, channels=2).reshape(-1, 2)
    out, out_vo = aotr.copy(), aotr.copy()
    fade = int(0.004 * OUT_SR)
    detail, used, done, gaps = [], [], 0.0, []

    def place(y, piece, start):         # chaque morceau à sa position exacte : aucune dérive aux raccords
        piece = piece[:len(y) - start].copy()
        ramp = np.linspace(0, 1, min(fade, len(piece) // 2))[:, None]
        if start > 0 and len(ramp):
            piece[:len(ramp)] = piece[:len(ramp)] * ramp + y[start:start + len(ramp)] * (1 - ramp)
        end = start + len(piece)
        if end < len(y) and len(ramp):
            piece[-len(ramp):] = piece[-len(ramp):] * ramp[::-1] + y[end - len(ramp):end] * (1 - ramp[::-1])
        y[start:end] = piece

    for lab, a, b, score in segs:
        b = total if b >= total - BLOCK else b
        dur, start = b - a, int(round(a * OUT_SR))
        if lab is None:
            detail.append(f'{a:.1f}-{b:.1f} AotR')
            continue
        si, off = lab
        src = sources[si]
        t, speed, fine = refine(clip8k, src, off / FPS + a, a, dur)
        if fine < 0.5:
            detail.append(f'{a:.1f}-{b:.1f} AotR (calage incertain)')
            continue
        vo = stereo(*src.eng, t, dur, speed)
        vf = stereo(*src.fre, t, dur, speed)
        g = rms(aotr[start:start + len(vo)]) / rms(vo)
        if not 0.1 < g < 15:            # correspondance sur un silence
            detail.append(f'{a:.1f}-{b:.1f} AotR (gain {g:.0f})')
            continue
        place(out, vf * g, start)
        place(out_vo, vo * g, start)
        done += dur
        gaps.append((dur, voice_gap(vo, vf)))
        used.append(src.name)
        detail.append(f'{a:.1f}-{b:.1f} {src.name} {t:.2f}s')
    if done:
        ext = os.path.splitext(clip)[1].lower()
        encode(out, os.path.join(out_dir, name + ext), clip)
        if controle:
            encode(out_vo, os.path.join(out_dir, name + '__VO' + ext), clip)
    gap = sum(d * g for d, g in gaps) / done if done else 0.0
    return done / total, gap, sorted(set(used), key=used.index), detail


VOICE = slice(9, 16)            # bandes ~360-2 000 Hz : la musique ajoutée par AotR y gêne moins


def bandpass(x, lo=300, hi=3400, sr=FINE_SR):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / sr)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, len(x))


def build_voice(clip, sources, out_dir, controle=False):
    """VF d'une réplique isolée tirée d'un film (mode --voix). Même retour que build()."""
    raw = decode(clip)
    if len(raw) < 0.8 * SR:
        return 0.0, 0.0, [], ['trop court']
    C = features(raw)[:, VOICE]
    si, k, _ = find(C - C.mean(0), sources, {})
    src, t = sources[si], k / FPS
    x = bandpass(decode(clip, sr=FINE_SR))
    s0 = max(0.0, t - 0.3)
    y = bandpass(decode(*src.eng, sr=FINE_SR, start=s0, dur=len(x) / FINE_SR + 0.6))
    if len(y) < len(x) or np.linalg.norm(x) < 1e-3:
        return 0.0, 0.0, [], ['pas de correspondance']
    r = np.correlate(y, x, 'valid')
    j = int(np.argmax(np.abs(r)))
    corr = abs(r[j]) / (np.linalg.norm(x) * np.linalg.norm(y[j:j + len(x)]) + 1e-9)
    if corr < 0.5:
        return 0.0, 0.0, [], [f'pas de correspondance ({corr:.2f})']
    start, dur = s0 + j / FINE_SR, len(raw) / SR
    aotr = decode(clip, sr=OUT_SR, channels=2).reshape(-1, 2)
    vo, vf = stereo(*src.eng, start, dur), stereo(*src.fre, start, dur)
    g = rms(aotr) / rms(vo)
    name, ext = os.path.splitext(os.path.basename(clip))
    encode(vf * g, os.path.join(out_dir, name + ext), clip)
    if controle:
        encode(vo * g, os.path.join(out_dir, name + '__VO' + ext), clip)
    return 1.0, voice_gap(vo, vf), [src.name], [f'{src.name} {start:.2f}s corrélation {corr:.2f}']


def ea_sources(cache):
    """Extrait les voix VO/VF présentes dans les deux archives d'EA -> [(nom, vo.mp3, vf.mp3)]."""
    out, seen = [], set()
    d = os.path.join(cache, 'ea')
    os.makedirs(d, exist_ok=True)
    for en_big, fr_big in EA_SPEECH:
        if not (os.path.exists(en_big) and os.path.exists(fr_big)):
            print('absent :', en_big if not os.path.exists(en_big) else fr_big)
            continue
        en, fr = BigFile(en_big), BigFile(fr_big)
        fr_files = {k.lower(): k for k in fr.files}
        for k in en.files:
            n = os.path.basename(k).lower()
            if not k.lower().startswith('data/audio/speech/') or k.lower() not in fr_files or n in seen:
                continue
            seen.add(n)
            pair = []
            for lang, big, inner in (('en', en, k), ('fr', fr, fr_files[k.lower()])):
                p = os.path.join(d, f'{lang}_{n}')
                if not os.path.exists(p):
                    with open(p, 'wb') as f:
                        f.write(big.read(inner))
                pair.append(p)
            out.append((n[:-4], *pair))
    return out


def videos():
    """nom de fichier en minuscules -> (vidéo, description) d'après data/ini/video.ini."""
    out, cur = {}, {}
    with open(os.path.join(AOTR, 'data', 'ini', 'video.ini'), encoding='cp1252') as f:
        for line in f:
            s = line.split(';')[0].strip()
            if s.startswith('Video '):
                cur = {'video': s.split()[1]}
            elif s.startswith('Filename') and '=' in s:
                cur['file'] = s.split('=', 1)[1].strip()
            elif s.startswith('Comment') and '=' in s:
                cur['comment'] = s.split('=', 1)[1].strip().strip('"')
            elif s == 'End' and 'file' in cur:
                out.setdefault(cur['file'].lower(), (cur['video'], cur.get('comment', '')))
                cur = {}
    return out


def main(argv):
    controle, voix = '--controle' in argv, '--voix' in argv
    sans_ea = voix or '--sans-ea' in argv
    argv = [a for a in argv if a not in ('--controle', '--sans-ea', '--voix')]
    out_dir = argv[0]
    clips = [c for a in argv[1:] for c in (sorted(glob.glob(a)) if '*' in a else [a])] \
        or sorted(glob.glob(os.path.join(AOTR, 'data', 'audio', 'speech', '*.mp3')))
    cache = os.path.join(out_dir, 'cache')
    os.makedirs(cache, exist_ok=True)
    sources = []
    for f in FILMS:
        path = os.path.join(FILMS_DIR, f)
        if not os.path.exists(path):
            print('absent :', path)
            continue
        st = dict((lang, i) for i, lang in reversed(audio_streams(path)))
        if 'eng' not in st or not ({'fre', 'fra'} & st.keys()):
            print('ignoré (pas de piste anglaise et française) :', f)
            continue
        print('analyse :', f, flush=True)
        sources.append(Source(os.path.splitext(f)[0], (path, st['eng']), (path, st.get('fre', st.get('fra'))), cache,
                              VOICE if voix else None))
    for name, en, fr in ([] if sans_ea else ea_sources(cache)):
        sources.append(Source('EA ' + name, (en, 0), (fr, 0), cache))
    print(f'{len(sources)} sources', flush=True)
    vids = videos()
    rows = []
    ea = {s.name[3:]: s for s in sources if s.name.startswith('EA ')}
    for clip in clips:
        name = os.path.splitext(os.path.basename(clip))[0]
        src = ea.get(name.lower())
        if src and abs(duration(clip) - duration(src.eng[0])) < 0.15:
            # extrait vanilla non retouché par AotR : la VF d'EA telle quelle
            shutil.copyfile(src.fre[0], os.path.join(out_dir, name + '.mp3'))
            part, gap, used, detail = 1.0, 1.0, [src.name], ['VF EA complète']
        else:
            part, gap, used, detail = (build_voice if voix else build)(clip, sources, out_dir, controle)
        video, comment = vids.get(name.lower(), ('', ''))
        rows.append({'fichier': name, 'durée (s)': f'{duration(clip):.0f}', 'vidéo': video, 'description': comment,
                     'part VF (%)': f'{100 * part:.0f}', 'écart VO/VF': f'{gap:.2f}', 'sources': ', '.join(used),
                     'morceaux': ' | '.join(detail)})
        print(f"{name:28} {rows[-1]['durée (s)']:>4}s  VF {rows[-1]['part VF (%)']:>3}%  écart {gap:.2f}  "
              f"{rows[-1]['sources'][:70]}", flush=True)
    with open(os.path.join(out_dir, 'liste.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=';')
        w.writeheader()
        w.writerows(rows)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
