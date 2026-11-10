"""Liste des répliques à doubler de la campagne (data/audio/sounds/mgfotr_*.wav) pour l'équipe de doublage.

Pour chaque fichier : personnage, mission, durée, texte anglais et traduction, statut.
  - texte : clé SCRIPT:<fichier> de lotr.str (dialogues sous-titrés), sinon nom du script de la carte qui joue
    le son (« Audio - Sauron - No escape! No quarter! », lu par mapfile.py), sinon transcription Whisper
    (soustitres.py) ; « source » le précise (script tronqué = à vérifier à l'écoute) ;
  - traduction : lotr.str si la réplique est sous-titrée, sinon colonne « FR » de doublage.csv (à remplir) ;
  - statut : « VF films » si cinematiques_vf.py --voix l'a déjà doublée (work/voix_vf), sinon « à doubler ».

Usage : python tools/doublage.py <sortie.csv> [--transcrit]
  --transcrit : transcrit avec Whisper les répliques sans texte ou au texte tronqué (long : ~1 s par réplique).
  Garde les colonnes FR / remarque déjà remplies dans <sortie.csv>.
        python tools/doublage.py lots <liste.csv> <dossier>        lots de traduction (format de lots.py ;
            vérifier chaque lot_NN_fr.csv avec « lots.py verifie »), après reprise des phrases déjà dans lotr.str
        python tools/doublage.py reinjecte <liste.csv> <dossier>   reporte les traductions dans la colonne FR
        python tools/doublage.py roles <liste.csv> <dossier>       un dossier par personnage (texte + VO de référence)
        python tools/doublage.py controle <liste.csv> <enregistrements> [rapport.csv]
            contrôle les .wav livrés (nom, format, durée, niveau) ; build_submod.py intègre les acceptés
"""
import csv
import glob
import os
import re
import shutil
import struct
import sys

import mapfile
import strfile

AOTR = r'C:\AgeoftheRing\aotr'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOUNDS = os.path.join(AOTR, 'data', 'audio', 'sounds')
FILM_VOICES = os.path.join(ROOT, 'work', 'voix_vf')
COLS = ['fichier', 'personnage', 'mission', 'durée (s)', 'VO', 'source', 'FR', 'statut', 'remarque']
OLD = re.compile(r'(?i)backup|_old|old\.|archive|crash| - old')
CAMPAIGN = r'(?i)^(mg[a-z]+_|ma(destr?|carnd|rhuda|gunda|bardo|wight|caw)_|mtciv)'   # pas les voix d'unités (mahud_, mablung_…)


INCOMPLETE = ('à transcrire', 'script tronqué', 'script douteux')     # sources à passer par Whisper
SILENT = 'sans parole (Whisper)'


def suspicious(text, seconds):
    """Nom de script qui n'est sans doute pas la réplique : trop peu de mots pour la durée, ou libellé
    (« Durin 07 », « Bow SFX », « Ettenmoors - Outro »…)."""
    return ((seconds > 2.5 and len(text.split()) / seconds < 0.9)
            or bool(re.search(r'(?i)\b(intro|outro|speech|timer|chart|sfx|grunt|wounded|cine|\d+)\s*$', text)))


def speaker(name):
    if name.lower().startswith('mtciv'):
        return 'Civil ' + re.sub(r'\d+$', '', name[5:]).title()
    m = re.match(r'[^_]+_(.+?)-?(\d+)\w?$', name)
    return (m[1] if m else name.split('_', 1)[-1]).replace('_', ' ').title()


def candidates():
    """Répliques de campagne du mod sans VF : mgfotr_* (campagne 10.0), anciennes campagnes AotR (mgrotk, mgnfotr,
    mghob, mgtt, mgshadow…), ajouts d'AotR à Angmar (madestr, macarnd…), civils de Minas Tirith (mtciv*).
    Les répliques reprises de BFME1 / BFME II / RotWK (VF d'EA, voir audio_vf.py) sont exclues."""
    import audio_vf
    games, _ = audio_vf.load()
    vf = {os.path.splitext(os.path.basename(p))[0] for _, _, fr in games for p in fr.files}
    # fichiers joués par un événement de campagne sous un autre nom (mgtt_gimli079 -> top_hrc2b, jeux EA des films)
    via = {f for name, files in audio_events().items() if re.match(CAMPAIGN, name) for f in files}
    return {os.path.splitext(f)[0]: os.path.join(SOUNDS, f) for f in os.listdir(SOUNDS)
            if (re.match(CAMPAIGN, f) or os.path.splitext(f)[0].lower() in via)
            and f.lower().endswith('.wav') and os.path.splitext(f)[0].lower() not in vf}


def audio_events():
    """Événements audio des INI du mod -> fichiers son (un script de carte joue un événement, souvent du même nom)."""
    events = {}
    for path in glob.glob(os.path.join(AOTR, 'data', 'ini', '**', '*.in[ic]'), recursive=True):
        cur = None
        for line in open(path, encoding='cp1252', errors='replace'):
            line = line.split(';')[0].split('//')[0].strip()
            m = re.match(r'(?i)(AudioEvent|DialogEvent)\s+(\S+)', line)
            if m:
                cur = events.setdefault(m[2].lower(), [])
            elif cur is not None and re.match(r'(?i)end\b', line):
                cur = None
            elif cur is not None:
                m = re.match(r'(?i)(Sounds\w*|Attack|Decay|Filename)\s*=\s*(.+)', line)
                if m:
                    cur += [s.lower() for s in m[2].split()]
    return events


def script_text(label):
    """Texte d'un nom de script « [Carte - ]Audio - Qui - Texte » ; '' si ce n'en est pas un."""
    m = re.search(r'(?i)audio\s*-\s*(?:[^-]{1,30}-\s*)?(.+)$', label)
    if not m or not re.search(r'[a-z]{2}', m[1]):
        return ''
    return m[1].strip()


def maps(wanted):
    """fichier son -> [(mission, texte du script)] d'après toutes les cartes du mod (sauf sauvegardes).

    wanted : noms de fichiers recherchés (minuscules) ; une chaîne de la carte peut aussi être un événement audio."""
    import pickle
    events = audio_events()
    cache_path = os.path.join(ROOT, 'work', 'doublage', 'cartes.pkl')   # chaînes des cartes (décompression lente)
    try:
        with open(cache_path, 'rb') as f:
            cache = pickle.load(f)
    except (OSError, EOFError, pickle.UnpicklingError):
        cache = {}
    out = {}
    for path in sorted(glob.glob(os.path.join(AOTR, 'maps', '**', '*.map'), recursive=True)):
        if OLD.search(path):
            continue
        stamp = os.path.getmtime(path)
        if cache.get(path, (None,))[0] != stamp:
            try:
                cache[path] = (stamp, mapfile.strings(path))
            except ValueError:
                cache[path] = (stamp, [])
        strs = cache[path][1]
        mission = os.path.basename(os.path.dirname(path))
        if mission.startswith('_') or mission.startswith('Cine'):
            mission = os.path.splitext(os.path.basename(path))[0]
        for i, s in enumerate(strs):
            s = s.lower()
            files = [f for f in events.get(s, [s]) if f in wanted]
            if files:
                labels = [x for x in strs[max(0, i - 4):i] if 'audio' in x.lower()]
                text = script_text(labels[-1]) if labels and len(files) == 1 else ''
                for f in files:
                    out.setdefault(f, []).append((mission, text))
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, 'wb') as f:
        pickle.dump(cache, f)
    return out


def wav_info(path):
    """En-tête RIFF d'un .wav (PCM ou ADPCM : le module wave ne lit que le PCM).

    Renvoie dict(format, canaux, fréquence, bits, durée, data) ; data = (début, taille) des échantillons."""
    with open(path, 'rb') as f:
        d = f.read()
    if d[:4] != b'RIFF' or d[8:12] != b'WAVE':
        raise ValueError('pas un fichier WAV')
    pos, info, avg, frames = 12, {}, 0, None
    while pos + 8 <= len(d):
        cid, n = d[pos:pos + 4], struct.unpack('<I', d[pos + 4:pos + 8])[0]
        if cid == b'fmt ':
            tag, ch, rate, avg, _, bits = struct.unpack('<HHIIHH', d[pos + 8:pos + 24])
            if tag == 0xFFFE and n >= 40:                # WAVE_FORMAT_EXTENSIBLE : vrai format dans le sous-type
                tag = struct.unpack('<H', d[pos + 32:pos + 34])[0]
            info.update(format=tag, canaux=ch, fréquence=rate, bits=bits)
        elif cid == b'fact':
            frames = struct.unpack('<I', d[pos + 8:pos + 12])[0]
        elif cid == b'data':
            info['data'] = (pos + 8, min(n, len(d) - pos - 8))
        pos += 8 + n + (n & 1)
    if 'format' not in info or 'data' not in info:
        raise ValueError('en-tête WAV incomplet')
    info['durée'] = frames / info['fréquence'] if frames else info['data'][1] / avg
    return info


def duration(path):
    return wav_info(path)['durée']


def main(out, transcribe=False):
    vo = strfile.read(os.path.join(ROOT, 'English_folder_str', sorted(
        f for f in os.listdir(os.path.join(ROOT, 'English_folder_str')) if f.startswith('lotr_'))[-1])).index()
    fr = strfile.read(os.path.join(ROOT, 'lotr.str')).index()
    old = {r['fichier']: r for r in (csv.DictReader(open(out, encoding='utf-8-sig'), delimiter=';')
                                      if os.path.exists(out) else [])}
    lines = candidates()
    used = maps({n.lower() for n in lines})
    films = {os.path.splitext(f)[0].lower() for f in os.listdir(FILM_VOICES)} if os.path.isdir(FILM_VOICES) else set()
    rows = []
    for name, path in sorted(lines.items(), key=lambda x: x[0].lower()):
        key = 'script:' + name.lower()
        places = used.get(name.lower(), [])
        texts = [t for _, t in places if t]
        r = {'fichier': name, 'personnage': speaker(name),
             'mission': ', '.join(sorted({m for m, _ in places})) or '(non utilisée dans les cartes)',
             'durée (s)': f'{duration(path):.1f}', 'statut': 'VF films' if name.lower() in films else 'à doubler',
             'FR': '', 'remarque': ''}
        if key in vo:
            r['VO'], r['source'] = re.sub(r'^[^:]{1,25}:\s*', '', vo[key].text), 'lotr.str'
            r['FR'] = re.sub(r'^[^:]{1,25}\s:\s*', '', fr[key].text) if key in fr else ''
        elif texts:
            t = max(texts, key=len)
            r['VO'] = t
            r['source'] = ('script tronqué' if len(t) >= 40 and not re.search(r'[.!?…"\')]$', t) else
                           'script douteux' if suspicious(t, float(r['durée (s)'])) else 'script')
        else:
            r['VO'], r['source'] = '', 'à transcrire'
        prev = old.get(name)
        if prev:
            r['FR'] = r['FR'] or prev.get('FR', '')
            r['remarque'] = prev.get('remarque', '')
            if prev.get('source') == 'whisper' and r['source'] in INCOMPLETE:
                r['VO'], r['source'] = prev['VO'], 'whisper'
        rows.append(r)
    if transcribe:
        from faster_whisper import WhisperModel
        model = WhisperModel('medium.en', device='cpu', compute_type='int8')
        todo = [r for r in rows if r['source'] in INCOMPLETE and SILENT not in r['remarque']]
        for i, r in enumerate(todo, 1):
            segs, _ = model.transcribe(os.path.join(SOUNDS, r['fichier'] + '.wav'), language='en', vad_filter=True)
            text = ' '.join(s.text.strip() for s in segs).strip()
            if text:
                r['VO'], r['source'] = text, 'whisper'
            else:                       # cri, bruit… : ne pas retenter à chaque passage
                r['remarque'] = (r['remarque'] + ' ; ' + SILENT).strip(' ;')
            if i % 100 == 0:
                print(f'{i}/{len(todo)} transcrites', flush=True)
                write(out, rows)
    write(out, rows)
    by = {}
    for r in rows:
        by[r['source']] = by.get(r['source'], 0) + 1
    print(f'{len(rows)} répliques -> {out} ; texte : {by}')


def write(path, rows):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLS, delimiter=';')
        w.writeheader()
        w.writerows(rows)


LOT_COLS = ['clé', 'fichier', 'statut', 'VO ancienne', 'VO nouvelle', 'FR actuelle', 'réf VO', 'réf FR',
            'personnage', 'mission', 'durée (s)', 'source']


def read(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f, delimiter=';'))


def lots(table, out_dir, max_lines=250, max_words=2500):
    """Répliques à doubler sans traduction -> lots au format de lots.py (clé = nom du fichier son).

    Les textes déjà traduits ailleurs dans lotr.str (même phrase anglaise) sont repris directement."""
    import lots as lotsmod
    from memoire import Memoire, adapt, alert, read_pairs
    vo_path = os.path.join(ROOT, 'English_folder_str', sorted(
        f for f in os.listdir(os.path.join(ROOT, 'English_folder_str')) if f.startswith('lotr_'))[-1])
    mem = Memoire()
    for k, en, fr in read_pairs(vo_path, os.path.join(ROOT, 'lotr.str')):
        mem.add('nous', k, re.sub(r'^[^:]{1,25}:\s*', '', en), fr)
    rows = read(table)
    reused, todo = 0, []
    for r in rows:
        if (r['FR'].strip() or r['statut'] != 'à doubler' or not r['VO'].strip()
                or r['source'] in INCOMPLETE):   # texte incomplet : attendre Whisper
            continue
        fr, _ = mem.propose('', r['VO'])
        fr = re.sub(r'^[^:]{1,25}\s:\s*', '', adapt(r['VO'], fr)) if fr else ''
        if fr and not alert(r['VO'], fr):
            r['FR'], r['remarque'] = fr, (r['remarque'] + ' ; reprise de lotr.str').strip(' ;')
            reused += 1
        else:
            todo.append(r)
    write(table, rows)
    todo.sort(key=lambda r: (r['personnage'], r['fichier']))
    batches, cur, words = [], [], 0
    for r in todo:
        n = len(r['VO'].split())
        if cur and (len(cur) >= max_lines or words + n > max_words):
            batches.append(cur)
            cur, words = [], 0
        cur.append(r)
        words += n
    if cur:
        batches.append(cur)
    os.makedirs(out_dir, exist_ok=True)
    for i, batch in enumerate(batches, 1):
        base = os.path.join(out_dir, f'lot_{i:02d}')
        with open(base + '.csv', 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=LOT_COLS, delimiter=';')
            w.writeheader()
            for r in batch:
                w.writerow({'clé': r['fichier'], 'fichier': 'doublage', 'statut': 'ajoutée', 'VO ancienne': '',
                            'VO nouvelle': r['VO'], 'FR actuelle': '', 'réf VO': '', 'réf FR': '',
                            'personnage': r['personnage'], 'mission': r['mission'], 'durée (s)': r['durée (s)'],
                            'source': r['source']})
        terms = lotsmod.glossary_terms(r['VO'] for r in batch)
        with open(base + '_glossaire.csv', 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(['VO', 'FR retenue', 'statut'])
            w.writerows((t['VO'], t['FR retenue'], t['statut']) for t in terms)
        who = sorted({r['personnage'] for r in batch})
        print(f'lot_{i:02d}: {len(batch):3} répliques — {", ".join(who)[:90]}')
    print(f'{reused} reprises de lotr.str ; {len(todo)} répliques à traduire en {len(batches)} lots')


def reinjecte(table, lots_dir):
    """Reporte les lot_NN_fr.csv (clé ; fichier ; FR) dans la colonne FR de la liste, et les lot_NN_remarques.csv
    dans « remarque ». Une traduction dont la VO a changé depuis (nouvelle transcription) n'est pas reprise."""
    fr, vo, notes = {}, {}, {}
    for path in sorted(glob.glob(os.path.join(lots_dir, 'lot_[0-9][0-9].csv'))):
        vo.update({r['clé']: r['VO nouvelle'] for r in read(path)})
        fr.update({r['clé']: r['FR'].strip().replace('’', "'") for r in read(path[:-4] + '_fr.csv') if r['FR'].strip()})
        if os.path.exists(path[:-4] + '_remarques.csv'):
            for r in read(path[:-4] + '_remarques.csv'):
                if r.get('clé') and r.get('remarque'):
                    notes.setdefault(r['clé'], []).append(r['remarque'].strip())
    rows = read(table)
    n = stale = 0
    for r in rows:
        k = r['fichier']
        if k not in fr or r['FR'].strip():
            continue
        if vo.get(k, '').strip() != r['VO'].strip():
            stale += 1
            continue
        r['FR'] = fr[k]
        r['remarque'] = ' ; '.join([r['remarque']] * bool(r['remarque']) + notes.get(k, []))
        n += 1
    write(table, rows)
    print(f'{n} traductions reportées dans {table} ; {stale} écartées (VO changée depuis le lot)')


def safe(name):
    return re.sub(r'[^\w\- ]', '_', name).strip() or 'inconnu'


def roles(table, out_dir):
    """Un dossier par personnage pour les doubleurs : repliques.csv (texte, durée, traduction) + vo/<fichier>.wav."""
    rows = [r for r in read(table) if r['statut'] == 'à doubler']
    by = {}
    for r in rows:
        by.setdefault(r['personnage'], []).append(r)
    summary = []
    for who, lines in sorted(by.items(), key=lambda x: -sum(float(r['durée (s)']) for r in x[1])):
        d = os.path.join(out_dir, safe(who))
        os.makedirs(os.path.join(d, 'vo'), exist_ok=True)
        with open(os.path.join(d, 'repliques.csv'), 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(['fichier', 'mission', 'durée VO (s)', 'VO', 'FR à dire', 'remarque'])
            for r in lines:
                w.writerow([r['fichier'], r['mission'], r['durée (s)'], r['VO'], r['FR'], r['remarque']])
                dst = os.path.join(d, 'vo', r['fichier'] + '.wav')
                if not os.path.exists(dst):
                    shutil.copy(os.path.join(SOUNDS, r['fichier'] + '.wav'), dst)
        minutes = sum(float(r['durée (s)']) for r in lines) / 60
        summary.append([who, len(lines), f'{minutes:.1f}', sum(1 for r in lines if r['FR'].strip())])
    with open(os.path.join(out_dir, 'roles.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['personnage', 'répliques', 'minutes', 'traduites'])
        w.writerows(summary)
    print(f'{len(summary)} rôles, {len(rows)} répliques -> {out_dir} (roles.csv : du plus gros au plus petit)')


def peak_db(path, info):
    """Crête en dBFS d'un WAV PCM 16/24/32 bits ou flottant."""
    import numpy as np
    start, size = info['data']
    with open(path, 'rb') as f:
        f.seek(start)
        raw = f.read(size)
    bits = info['bits']
    if info['format'] == 3:
        x = np.frombuffer(raw[:size // 4 * 4], '<f4')
    elif bits == 24:
        b = np.frombuffer(raw[:size // 3 * 3], np.uint8).reshape(-1, 3)
        x = (b[:, 0].astype(np.int32) | b[:, 1].astype(np.int32) << 8 | b[:, 2].astype(np.int8).astype(np.int32) << 16)
        x = x / 2 ** 23
    else:
        x = np.frombuffer(raw[:size // (bits // 8) * (bits // 8)], {16: '<i2', 32: '<i4', 8: 'u1'}[bits])
        x = (x.astype(np.float64) - (128 if bits == 8 else 0)) / 2 ** (bits - 1)
    p = float(np.abs(x).max()) if len(x) else 0.0
    return 20 * np.log10(p) if p > 0 else -120.0


def controle(table, rec_dir, report=None):
    """Contrôle des enregistrements livrés (tout .wav sous rec_dir, nommé comme la VO).

    Refusé : nom inconnu, pas du WAV PCM, durée hors de 0,5–2 × la VO (mauvais fichier ?).
    Remarques (accepté quand même) : stéréo, fréquence autre que 44,1/48 kHz, durée hors ±20 %, saturation, trop faible.
    Renvoie {fichier: chemin} des enregistrements acceptés ; écrit le rapport si `report`."""
    rows = {r['fichier'].lower(): r for r in read(table)}
    found, out, accepted = {}, [], {}
    for path in sorted(glob.glob(os.path.join(rec_dir, '**', '*.wav'), recursive=True)):
        found.setdefault(os.path.splitext(os.path.basename(path))[0].lower(), []).append(path)
    for name, paths in sorted(found.items()):
        path, bad, notes = paths[-1], [], []
        if len(paths) > 1:
            notes.append(f'{len(paths)} prises, gardée : {os.path.relpath(path, rec_dir)}')
        r = rows.get(name)
        if not r:
            bad.append('nom inconnu (doit être celui du fichier VO)')
        try:
            info = wav_info(path)
        except (ValueError, struct.error, OSError) as e:
            info, bad = None, bad + [f'illisible : {e}']
        if info:
            if info['format'] not in (1, 3):
                bad.append(f'format {info["format"]} (WAV PCM attendu)')
            else:
                if info['canaux'] != 1:
                    notes.append(f'{info["canaux"]} canaux (mono attendu, sera mixé)')
                if info['fréquence'] not in (44100, 48000):
                    notes.append(f'{info["fréquence"]} Hz (44,1 ou 48 kHz attendu)')
                db = peak_db(path, info)
                if db > -0.5:
                    notes.append(f'saturé ? crête {db:.1f} dB')
                elif db < -20:
                    notes.append(f'trop faible : crête {db:.1f} dB')
            if r:
                ratio = info['durée'] / max(float(r['durée (s)']), 0.1)
                text = f'{info["durée"]:.1f} s pour {r["durée (s)"]} s en VO'
                if not 0.5 <= ratio <= 2:
                    bad.append(text)
                elif not 0.8 <= ratio <= 1.2:
                    notes.append(text)
        status = 'refusé' if bad else ('accepté avec remarques' if notes else 'OK')
        if not bad:
            accepted[r['fichier']] = path
        out.append({'fichier': os.path.basename(path), 'personnage': r['personnage'] if r else '',
                    'statut': status, 'problèmes': ' ; '.join(bad + notes)})
    if report:
        os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
        with open(report, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['fichier', 'personnage', 'statut', 'problèmes'], delimiter=';')
            w.writeheader()
            w.writerows(out)
        todo = {}
        for r in rows.values():
            if r['statut'] == 'à doubler' and r['fichier'] not in accepted:
                todo[r['personnage']] = todo.get(r['personnage'], 0) + 1
        count = {s: sum(1 for o in out if o['statut'] == s) for s in ('OK', 'accepté avec remarques', 'refusé')}
        print(f'{len(out)} enregistrements : {count} -> {report}')
        print(f'reste à enregistrer : {sum(todo.values())} répliques, dont '
              + ', '.join(f'{k} {v}' for k, v in sorted(todo.items(), key=lambda x: -x[1])[:8]))
    return accepted


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == 'lots':
        lots(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'reinjecte':
        reinjecte(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'roles':
        roles(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'controle':
        controle(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else
                 os.path.join(ROOT, 'work', 'doublage', 'controle.csv'))
    else:
        main(sys.argv[1], '--transcrit' in sys.argv)
