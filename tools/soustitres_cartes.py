"""Sous-titres des répliques de campagne qu'AotR joue sans texte (scènes de la campagne 10.0).

Dans les scripts d'une carte, une réplique est jouée par SOUND_PLAY_NAMED (son « mgfotr_theoden077 ») ; les cartes
d'EA affichent le sous-titre avec SHOW_MILITARY_CAPTION (« SCRIPT:<clé> », durée). On ajoute cette action juste après
chaque réplique qui n'en a pas, avec la clé SCRIPT:<son> ajoutée au map.str (« PERSONNAGE : texte FR » tiré de
work/doublage/repliques.csv, ou des sous-titres VF officiels de la campagne BFME1). La carte est réécrite au format
RefPack (blocs littéraux seulement : valide, non compressé).

Format (.map décompressé) : « CkMp », table des noms (int32 n ; uint8 long, nom, uint32 id), puis des blocs
(uint32 id, uint16 version, int32 taille, données). PlayerScriptsList > ScriptList > ScriptGroup / Script >
OrCondition / ScriptAction / ScriptActionFalse. ScriptAction v3 : uint32 type, uint32 clé du nom ((id << 8) | 3),
uint32 nb d'arguments, par argument uint32 type, int32, float32, uint16 long + chaîne ; puis 4 octets de fin.

Usage : python tools/soustitres_cartes.py <dossier de sortie> [carte…]     (ex. "map good helms deep")
        python tools/soustitres_cartes.py --bilan <rapport.csv> [carte…]   (chaque son lancé par un script : sous-titré ?)
"""
import collections
import csv
import difflib
import glob
import os
import re
import struct
import sys
import unicodedata

import doublage
import mapfile
import rules
import strfile

ROOT = doublage.ROOT
MOD_MAPS = os.path.join(doublage.AOTR, 'maps')
CONTAINERS = {'PlayerScriptsList', 'ScriptList', 'ScriptGroup', 'Script', 'OrCondition'}
ACTIONS = ('ScriptAction', 'ScriptActionFalse')
SPEAK = ('SOUND_PLAY_NAMED', 'PLAY_SOUND_EFFECT', 'PLAY_SOUND_EFFECT_AT', 'PLAY_SOUND_EFFECT_AT_TEAM')
CAPTION = 'SHOW_MILITARY_CAPTION'
# actions qui affichent déjà un texte : sous-titre en haut de l'écran ou fenêtre avec portrait (cartes d'AotR)
SHOWN = (CAPTION, 'DISPLAY_NOTIFICATION_BOX', 'DISPLAY_NOTIFICATION_BOX_WITH_OBJECT_TYPE_IMAGE_OVERRIDE')
BFME1_SUBTITLES = (r'C:\BFME1\_wwspatch108campaignefr.big', 'data/lotr.str')   # sous-titres VF de la campagne BFME1
# locuteur imposé pour un code de son (« mgfotr_saruman012 » -> saruman) ; None = pas de locuteur affiché.
# Les extraits de films (Cine) et textes de mission mêlent plusieurs personnages ; les autres codes sont mal devinés
# depuis les textes d'AotR (Saroumane y est « Sharkey » dans la Comté, Haldir n'a qu'un exemple « Elladan : »…).
SPEAKER_CODES = {'cine': None, 'missiontext': None, 'missionhint': None,
                 'saruman': 'SAROUMANE', 'haldir': 'HALDIR', 'gollum': 'GOLLUM', 'hurin': 'HÚRIN',
                 'wulfgar': 'WULFGAR', 'beaconguard': "GARDE DU FEU D'ALARME"}
# Actions ajoutées à la fin de scripts d'AotR (bugs des cartes qui cachent un sous-titre) : carte -> [(cible, action,
# arguments)]. Cible : titre d'un script, ou « @ACTION » = chaque script qui contient cette action. L'action est copiée
# d'une action de même nom de la carte ; arguments dans l'ordre : chaîne -> texte, entier -> valeur, None -> inchangé.
# Feux d'alarme : les noms de lieux (« Area Label - … », SHOW_MILITARY_CAPTION de 5 s à l'entrée d'une zone, même
# emplacement que les sous-titres) s'affichaient pendant les scènes où Pippin est déplacé et remplaçaient ses répliques
# (entrée de Rath Dínen : mgfotr_pippin077 caché par « RATH DÍNEN »). On les met en pause pendant chaque scène avec le
# drapeau d'AotR (« Flag - Area Labels Pause ») ; « Area Label - Reset », qui le remet à 0 5 s après un nom de lieu, est
# désactivé pendant la scène (« Area Label - Reset Run » le réactive au nom suivant). « Area Label - Reset » réactive
# aussi toujours « Area Label - RathDinen » : désactivé à l'entrée de Rath Dínen, « Area Label - RathDinen First »
# l'affiche et le réactive 2 s après la scène.
SCRIPT_FIXES = {
    'map good lighting the beacons': [
        ('@CAMERA_LETTERBOX_BEGIN', 'SET_FLAG', ['Flag - Area Labels Pause', 1]),
        ('@CAMERA_LETTERBOX_BEGIN', 'DISABLE_SCRIPT', ['Area Label - Reset']),
        ('@CAMERA_LETTERBOX_END', 'SET_FLAG', ['Flag - Area Labels Pause', 0]),
        ('Cinematic - Rath Dinen - Trigger', 'DISABLE_SCRIPT', ['Area Label - RathDinen']),
    ],
}
# Un texte d'AotR affiché pendant une réplique (même scène, enchaînement de minuteurs) : on n'ajoute pas notre
# sous-titre s'il couperait ce texte de plus de CUT_MAX secondes, ni s'il ne resterait pas au moins SHOW_MIN secondes
# avant le texte d'AotR suivant (doublon : AotR sous-titre la réplique sous sa propre clé, dans un script voisin).
CUT_MAX, SHOW_MIN = 3.0, 1.5
FPS = 30.0                                              # SET_TIMER compte en images, SET_MILLISECOND_TIMER en secondes


class Chunk:
    def __init__(self, cid, ver, head, children=None, raw=None):
        self.cid, self.ver, self.head, self.children, self.raw = cid, ver, head, children, raw

    def data(self):
        if self.children is None:
            return self.raw
        return self.head + b''.join(c.encode() for c in self.children)

    def encode(self):
        d = self.data()
        return struct.pack('<IHi', self.cid, self.ver, len(d)) + d


def tile(d, names, a, b):
    """Blocs qui couvrent exactement [a, b), ou None."""
    out, p = [], a
    while p < b:
        if p + 10 > b:
            return None
        cid, ver, size = struct.unpack_from('<IHi', d, p)
        if cid not in names or size < 0 or p + 10 + size > b:
            return None
        out.append((cid, ver, p + 10, p + 10 + size))
        p += 10 + size
    return out


def parse(d, names, a, b):
    chunks = []
    for cid, ver, s, e in tile(d, names, a, b) or []:
        name = names[cid]
        if name in CONTAINERS:
            # en-tête propre au bloc (nom, commentaires, drapeaux…) puis des sous-blocs : on cherche où ils commencent
            for h in range(0, min(e - s, 8192) + 1):
                sub = tile(d, names, s + h, e)
                if sub is not None and (h == e - s or all(names[c] in CONTAINERS | set(ACTIONS) | {'Condition'}
                                                          for c, *_ in sub)):
                    chunks.append(Chunk(cid, ver, d[s:s + h], parse(d, names, s + h, e)))
                    break
            else:
                raise ValueError(f'bloc {name} illisible à {s}')
        else:
            chunks.append(Chunk(cid, ver, None, raw=d[s:e]))
    return chunks


def load(path):
    d = mapfile.refpack(open(path, 'rb').read())
    if d[:4] != b'CkMp':
        raise ValueError(f'{path} : pas une carte CkMp')
    n = struct.unpack_from('<i', d, 4)[0]
    p, names = 8, {}
    for _ in range(n):
        ln = d[p]
        names[struct.unpack_from('<I', d, p + 1 + ln)[0]] = d[p + 1:p + 1 + ln].decode('ascii')
        p += 1 + ln + 4
    return names, parse(d, names, p, len(d))


def save(path, names, chunks):
    toc = struct.pack('<i', len(names)) + b''.join(
        bytes([len(n)]) + n.encode('ascii') + struct.pack('<I', i) for i, n in names.items())
    raw = b'CkMp' + toc + b''.join(c.encode() for c in chunks)
    packed = refpack(raw)
    if mapfile.refpack(packed) != raw:              # ne jamais livrer une carte mal compressée
        packed = refpack_literal(raw)
    with open(path, 'wb') as f:
        f.write(packed)


def refpack(raw):
    """Compression RefPack (LZ77 glouton : dernière occurrence de chaque séquence de 4 octets, fenêtre de 128 Ko).
    Moins serrée que celle d'EA mais du même ordre ; vérifiée par décompression dans save()."""
    big = len(raw) > 0xFFFFFF
    out = bytearray(b'EAR\0' + struct.pack('<I', len(raw)) + (b'\x90\xfb' if big else b'\x10\xfb') +
                    len(raw).to_bytes(4 if big else 3, 'big'))
    last, n, pos, lit = {}, len(raw), 0, 0          # lit : début des octets pas encore écrits

    def flush(upto):                                # littéraux par blocs de 4 à 112, il en reste 0 à 3
        nonlocal lit
        while upto - lit >= 4:
            k = min(112, (upto - lit) // 4 * 4)
            out.append(0xE0 | (k // 4 - 1))
            out.extend(raw[lit:lit + k])
            lit += k

    while pos + 4 <= n:
        key = raw[pos:pos + 4]
        cand = last.get(key)
        last[key] = pos
        if cand is None or pos - cand > 131072:
            pos += 1
            continue
        length, limit = 4, min(1028, n - pos)
        while length < limit and raw[cand + length:cand + length + 16] == raw[pos + length:pos + length + 16] \
                and length + 16 <= limit:
            length += 16
        while length < limit and raw[cand + length] == raw[pos + length]:
            length += 1
        off = pos - cand
        if off > 16384 and length < 5:
            pos += 1
            continue
        flush(pos)
        plain, o = pos - lit, off - 1
        if length <= 10 and off <= 1024:
            out += bytes([((o >> 8) & 3) << 5 | (length - 3) << 2 | plain, o & 0xFF])
        elif length <= 67 and off <= 16384:
            out += bytes([0x80 | (length - 4), plain << 6 | (o >> 8) & 0x3F, o & 0xFF])
        else:
            out += bytes([0xC0 | ((o >> 16) & 1) << 4 | ((length - 5) >> 8) << 2 | plain, (o >> 8) & 0xFF, o & 0xFF,
                          (length - 5) & 0xFF])
        out += raw[lit:pos]
        pos += length
        lit = pos
    flush(n)
    out.append(0xFC | (n - lit))
    out += raw[lit:]
    return bytes(out)


def refpack_literal(raw):
    """RefPack sans compression (blocs littéraux de 112 octets) : lu par le jeu comme une carte compressée."""
    big = len(raw) > 0xFFFFFF                       # au-delà de 16 Mo : drapeau 0x80 et taille sur 4 octets
    out = bytearray(b'EAR\0' + struct.pack('<I', len(raw)) + (b'\x90\xfb' if big else b'\x10\xfb') +
                    len(raw).to_bytes(4 if big else 3, 'big'))
    p, n = 0, len(raw)
    while n - p >= 4:
        k = min(112, (n - p) // 4 * 4)
        out.append(0xE0 | (k // 4 - 1))
        out += raw[p:p + k]
        p += k
    out.append(0xFC | (n - p))
    out += raw[p:]
    return bytes(out)


def action(data):
    """(type, clé de nom, [(type, int, float, chaîne)], fin) d'un bloc ScriptAction."""
    atype, key, nargs = struct.unpack_from('<III', data, 0)
    p, args = 12, []
    for _ in range(nargs):
        t = struct.unpack_from('<I', data, p)[0]
        if t == 16:                                 # position : 3 flottants, ni entier ni chaîne
            args.append((t, 0, 0.0, ''))
            p += 16
            continue
        t, iv, fv, ln = struct.unpack_from('<IifH', data, p)
        args.append((t, iv, fv, data[p + 14:p + 14 + ln].decode('cp1252')))
        p += 14 + ln
    return atype, key, args, data[p:]


def caption(type_id, key, text, seconds, tail):
    s = text.encode('cp1252')
    return (struct.pack('<III', type_id, key, 2) + struct.pack('<IifH', 25, 0, 0.0, len(s)) + s +
            struct.pack('<IifH', 1, 0, float(seconds), 0) + tail)


def script_title(chunk):
    ln = struct.unpack_from('<H', chunk.head, 0)[0]
    return chunk.head[2:2 + ln].decode('cp1252', errors='replace')


def fix_scripts(name, names, chunks):
    """Applique SCRIPT_FIXES à une carte chargée ; renvoie le nombre d'actions ajoutées."""
    def aname_of(c):
        return names.get(action(c.raw)[1] >> 8) if c.children is None and names[c.cid] in ACTIONS else None

    added = 0
    scripts = [c for c in walk(chunks) if c.children is not None and names[c.cid] == 'Script']
    for target, aname, values in SCRIPT_FIXES.get(name, []):
        model = next((c for c in walk(chunks) if names[c.cid] == 'ScriptAction' and aname_of(c) == aname
                      and len(action(c.raw)[2]) == len(values) and all(a[0] != 16 for a in action(c.raw)[2])), None)
        if target.startswith('@'):
            targets = [s for s in scripts if any(aname_of(c) == target[1:] for c in s.children)]
        else:
            targets = [s for s in scripts if script_title(s) == target][:1]
        if model is None or not targets:
            print(f'{name} : correctif « {target} / {aname} » non appliqué (script ou action introuvable)')
            continue
        atype, key, args, tail = action(model.raw)
        raw = struct.pack('<III', atype, key, len(args))
        for (t, iv, fv, s), v in zip(args, values):
            if isinstance(v, str):
                s = v
            elif isinstance(v, int):
                iv = v
            b = s.encode('cp1252')
            raw += struct.pack('<IifH', t, iv, fv, len(b)) + b
        for script in targets:
            if any(c.children is None and c.raw == raw + tail for c in script.children):
                continue                                # déjà présent (correctif repris par AotR)
            script.children.append(Chunk(model.cid, model.ver, None, raw=raw + tail))
            added += 1
    return added


def overlapped(names, chunks, texts):
    """Répliques qu'on ne sous-titre pas : un texte d'AotR est affiché en même temps dans la même scène.

    On suit les minuteurs depuis chaque script racine (sans condition TIMER_EXPIRED, hors Debug/Test) pour dater les
    textes (SHOW_MILITARY_CAPTION) et les sons. Renvoie {(titre du script, événement en minuscules)}."""
    scripts = [c for c in walk(chunks) if c.children is not None and names[c.cid] == 'Script']
    by_timer, roots = collections.defaultdict(list), []

    def items(sc, kind):
        for c in walk(sc.children):
            if c.children is None and names[c.cid] == kind:
                try:
                    t, k, a, _ = action(c.raw)
                except (struct.error, UnicodeDecodeError):
                    continue
                yield names.get(k >> 8), a

    for sc in scripts:
        timers = [a[0][3] for n, a in items(sc, 'Condition') if n == 'TIMER_EXPIRED' and a]
        for t in timers:
            by_timer[t].append(sc)
        if not timers and not re.search(r'(?i)debug|test', script_title(sc)):
            roots.append(sc)

    def events(sc, t0, seen):
        for n, a in items(sc, 'ScriptAction'):
            if n == CAPTION:
                label = next((x[3] for x in a if x[3]), '')
                yield t0, 'cap', label, next((x[2] for x in a if x[0] == 1), 0.0), sc
            elif n in SPEAK and a and a[0][3]:
                found = texts.get(a[0][3])
                yield t0, 'snd', a[0][3], (found[2] if found else 0.0) or 0.0, sc
            elif n in ('SET_MILLISECOND_TIMER', 'SET_TIMER') and len(a) > 1 and a[0][3] and len(seen) < 6:
                dt = a[1][2] if n == 'SET_MILLISECOND_TIMER' else a[1][1] / FPS
                for nxt in by_timer.get(a[0][3], []):
                    if id(nxt) not in seen:
                        yield from events(nxt, t0 + dt, seen | {id(nxt)})

    def key(label):
        return re.sub(r'subtitle$', '', re.sub(r'(?i)^(script|dialogevent):(subtitle_)?', '', label)).lower()

    skip = set()
    for root in roots:
        ev = list(events(root, 0.0, {id(root)}))
        caps = [e for e in ev if e[1] == 'cap']
        if not caps:
            continue
        audio = {e[2].lower(): e[3] for e in ev if e[1] == 'snd'}
        for t, _, event, length, sc in (e for e in ev if e[1] == 'snd'):
            found = texts.get(event)
            if not found or not found[1] or any(shown_label(names, c) for c in sc.children):
                continue                                    # pas de sous-titre à ajouter ici de toute façon
            line = max(length, 1.0)
            for tc, _, label, dc, csc in caps:
                if csc is sc:
                    continue
                need = audio.get(key(label)) or dc        # le texte d'AotR doit rester le temps de sa réplique
                if tc <= t < tc + need - CUT_MAX or (t <= tc < t + line and tc - t < SHOW_MIN):
                    skip.add((script_title(sc), event.lower()))
                    break
    return skip


def walk(chunks):
    for c in chunks:
        yield c
        if c.children:
            yield from walk(c.children)


def speakers():
    """Nom affiché de chaque personnage (« theoden » -> « THÉODEN »), d'après les sous-titres déjà traduits."""
    seen = collections.defaultdict(collections.Counter)
    for path in [os.path.join(ROOT, 'lotr.str')] + glob.glob(os.path.join(ROOT, 'maps', 'maps', '*', 'map.str')):
        for e in strfile.read(path).entries:
            m = re.match(r'(?i)script:(?:subtitle_)?m[a-z]+_([a-z]+?)\d', e.key)
            n = re.match(r'([^:\n]{2,30}?)\s:\s', e.text)
            if m and n:
                seen[m[1].lower()][n[1].strip().upper()] += 1                 # majuscules, comme chez EA
    who = {}
    for code, names in seen.items():
        (name, k), *rest = names.most_common(2)
        # nom retenu s'il l'emporte nettement et qu'il a au moins deux exemples, sauf s'il ressemble au code
        # (« earn » -> EÄRNUR) : un exemple isolé peut être une phrase (« Notre charge est ancienne : … »)
        if (not rest or rest[0][1] < k) and (k >= 2 or code in fold(name) or fold(name) in code):
            who[code] = name
    who.update(SPEAKER_CODES)
    return who


def fold(s):
    """« EÄRNUR » -> « earnur » (minuscules sans accents ni signes)."""
    return re.sub(r'[^a-z]', '', unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower())


class Texts:
    """Texte FR d'une réplique jouée par un script : nom d'événement -> fichiers son -> texte.

    Sources : work/doublage/repliques.csv (répliques d'AotR), puis les sous-titres officiels de la campagne BFME1
    (DIALOGEVENT:<fichier>subtitle), pour les répliques d'EA reprises par AotR (mghelms_giml026…)."""

    def __init__(self, dubbing_list):
        import memoire
        self.lines = {r['fichier'].lower(): r for r in doublage.read(dubbing_list)}
        self.events = doublage.audio_events()
        self.bfme1 = {k: memoire.unmojibake(v) for k, v in memoire.read_table(*BFME1_SUBTITLES).items()
                      if k.startswith('dialogevent:') and k.endswith('subtitle')}
        self.who = speakers()
        # clés que le map.str d'une carte définit déjà (texte d'AotR) : jamais dans lotr.str, il passerait devant
        self.map_keys = {e.lkey for p in glob.glob(os.path.join(ROOT, 'maps', 'maps', '*', 'map.str'))
                         for e in strfile.read(p).entries}
        # textes VO (clé -> texte) : comparer une réplique au texte d'une fenêtre d'AotR (already_shown)
        self.vo = {}
        for p in [doublage.latest_vo()] + glob.glob(os.path.join(ROOT, 'English_folder_str', 'maps', '*', 'map.str')):
            for e in strfile.read(p).entries:
                self.vo.setdefault(e.lkey, e.text)

    def speaker(self, sound):
        m = re.match(r'(?i)m[a-z]+_([a-z]+?)\d', sound)
        if not m:
            return None
        code = m[1].lower()
        if code in self.who:
            return self.who[code]           # None pour un code sans locuteur (Cine…)
        near = sorted(k for k in self.who if len(code) >= 4 and k.startswith(code))
        return self.who[near[0]] if len(near) == 1 else None       # « theo » : Théoden ou Théodred ? on s'abstient

    def files(self, event):
        return [event.lower()] + [f for f in self.events.get(event.lower(), []) if not f.endswith('.mp3')]

    def get(self, event):
        """(fichier, texte FR sans locuteur, durée) ; texte '' si la réplique n'a pas de texte ; None si inconnue."""
        files = self.files(event)
        for f in files:
            r = self.lines.get(f)
            if r:
                text = '' if no_speech(r) else r['FR'].strip()
                return f, text, float(r['durée (s)'] or 0)
        for f in files:
            t = self.bfme1.get(f'dialogevent:{f}subtitle')
            if t is not None:
                t = t.strip().lstrip('*').strip()
                if re.fullmatch(r'\d+', t):          # Legolas et Gimli comptent leurs ennemis abattus
                    t += ' !'
                wav = os.path.join(doublage.SOUNDS, f + '.wav')
                return f, t, doublage.duration(wav) if os.path.exists(wav) else 4.0
        return None


def no_speech(r):
    """Extrait de film (Cine) sans réplique : hallucination de Whisper sur la musique (« Merci de votre attention »,
    « Sous-titrage ST'501 »), ou son d'ambiance dont la VO n'est qu'un libellé (« Rumble », « Bow SFX », « Grond Gate »)
    et que les traducteurs ont rendu par « Hmm… » ou une phrase inventée. Le texte reste dans repliques.csv (doublage)."""
    if r['personnage'] != 'Cine':
        return False
    if re.search(r'(?i)hallucination|carton de fin', r['remarque']) or r['fichier'].lower() == 'mgfotr_cine073':
        return True                         # Cine073 : « Thank you. » sur la scène du Roi-sorcier, Whisper douteux
    return 'sans parole' in r['remarque'] and not re.search(r'[!?.…]', r['VO'])


def map_files(name):
    # copies laissées par les auteurs (« … old.map », « …_backup.map ») : jamais chargées par la campagne
    return [m for m in glob.glob(os.path.join(MOD_MAPS, name, '*.map'))
            if not m.lower().endswith((' old.map', '_backup.map'))]


def shown_label(names, chunk):
    """Clé du texte affiché par une action (« mgfotr_grimbold004 » pour SCRIPT:mgfotr_grimbold004), ou None."""
    if chunk.children is not None or names[chunk.cid] not in ACTIONS:
        return None
    atype, k, args, _ = action(chunk.raw)
    if names.get(k >> 8) not in SHOWN:
        return None
    label = next((a[3] for a in args if re.match(r'(?i)(script|dialogevent):', a[3])), None)
    return re.sub(r'^subtitle_|subtitle$', '', label.split(':', 1)[1].lower()) if label else None


def captions_shown(names, chunks):
    """Répliques déjà sous-titrées par la carte (SCRIPT:<son>, SCRIPT:SUBTITLE_<son>…)."""
    return {label for c in walk(chunks) if (label := shown_label(names, c))}


LAUNCH = ('ENABLE_SCRIPT', 'CALL_SUBROUTINE')                # argument : titre du script lancé
TIMERS = ('SET_TIMER', 'SET_MILLISECOND_TIMER')               # argument : minuteur -> scripts TIMER_EXPIRED dessus


SAME_LINE = 0.3          # ressemblance (mots de la VO) au-delà de laquelle deux textes sont la même réplique


def launched_by_text(names, chunks):
    """{titre d'un script : [(lien, clé d'un texte affiché par un script voisin)]}, lien = 'parent' (le script qui le
    lance par ENABLE_SCRIPT, CALL_SUBROUTINE ou un minuteur), 'enfant' (un script qu'il lance) ou 'frère' (lancé par
    le même parent : texte et son déclenchés ensemble par deux minuteurs).

    Conseil d'Elrond (23/11/2026) : « Rivendell - Speech - Elrond 01 » affiche la réplique dans une fenêtre avec
    portrait et active « Audio - Elrond - You have shown… », qui joue seulement le son ; « Gladden - Area 01 -
    Isildur Speech 01 » affiche « Isildur : Très bien. » et lance le minuteur « Audio - Isildur - Very well. ».
    Notre sous-titre en haut de l'écran faisait doublon. Voir already_shown()."""
    scripts = [s for s in walk(chunks) if s.children is not None and names[s.cid] == 'Script']
    by_timer = collections.defaultdict(list)
    labels, launches = {}, collections.defaultdict(set)
    for s in scripts:
        t = script_title(s)
        labels[t] = [full_label(names, c) for c in s.children if shown_label(names, c)]
        for c in walk(s.children):
            if c.children is None and names[c.cid] == 'Condition':
                try:
                    _, k, args, _ = action(c.raw)
                except (struct.error, UnicodeDecodeError):
                    continue
                if names.get(k >> 8) == 'TIMER_EXPIRED' and args and args[0][3]:
                    by_timer[args[0][3]].append(t)
    for s in scripts:
        for c in s.children:
            if c.children is None and names[c.cid] in ACTIONS:
                _, k, args, _ = action(c.raw)
                n = names.get(k >> 8)
                if n in LAUNCH and args and args[0][3]:
                    launches[script_title(s)].add(args[0][3])
                elif n in TIMERS and args and args[0][3]:
                    launches[script_title(s)].update(by_timer.get(args[0][3], []))
    out = collections.defaultdict(list)
    for parent, kids in launches.items():
        kids.discard(parent)
        for kid in kids:
            out[kid] += [('parent', l) for l in labels.get(parent, [])]
            out[parent] += [('enfant', l) for l in labels.get(kid, [])]
            for other in kids - {kid}:
                out[kid] += [('frère', l) for l in labels.get(other, [])]
    return out


def full_label(names, chunk):
    _, _, args, _ = action(chunk.raw)
    return next((a[3] for a in args if re.match(r'(?i)(script|dialogevent):', a[3])), '')


def words(text):
    text = re.sub(r'^[^:]{1,40}?\s?:\s', '', text.replace('\\n', ' '))         # sans le locuteur
    return re.sub(r'[^a-zà-ÿ0-9 ]', '', text.lower()).split()


def already_shown(texts, found, related):
    """La réplique est-elle l'un des textes affichés par un script voisin (launched_by_text) ? On compare les VO :
    les cris ou répliques enchaînées (Rhudaur, Cirith Ungol : « What's that!? He's massive! » puis « I think we made
    a mistake ») restent sous-titrés, les paraphrases d'AotR (Conseil d'Elrond, ressemblance 0,4 à 1) ne le sont pas."""
    if not related:
        return False
    r = texts.lines.get(found[0])
    if not r or not r['VO']:                         # réplique BFME1 sans VO de référence : seulement le script parent
        return any(kind == 'parent' for kind, _ in related)
    mine = content_words(r['VO'])
    return any(difflib.SequenceMatcher(None, mine, content_words(texts.vo.get(l.lower(), ''))).ratio()
               >= (SAME_LINE if kind != 'frère' else SAME_LINE_SIBLING) for kind, l in related)


SAME_LINE_SIBLING = 0.5  # texte lancé en même temps (frère) : toute une scène, il faut plus de ressemblance


def content_words(text):
    """Mots de plus de 3 lettres : « the », « of », « your » rapprochaient deux répliques courtes différentes
    (« This is the hour of your doom! » / « The world of men will fall. »)."""
    return [w for w in words(text) if len(w) > 3]


def run(name, out_dir, texts, shared=None):
    """Réécrit les cartes de <name> avec les sous-titres ajoutés. Leurs textes vont dans <shared> (dict clé -> texte,
    à ajouter au lotr.str du submod) quand il est fourni, sinon dans le map.str de la carte.

    Pourquoi lotr.str : en test (08/11/2026), « map good last alliance » (map.str vide dans le mod) affichait
    MISSING: 'SCRIPT:…' pour des clés pourtant présentes dans le map.str du submod ; lotr.str est toujours lu."""
    src_str = os.path.join(ROOT, 'maps', 'maps', name, 'map.str')
    items = strfile.read(src_str).items if os.path.exists(src_str) else []
    have = {i.lkey for i in items if isinstance(i, strfile.Entry)}
    added_keys, report = {}, collections.Counter()
    for path in map_files(name):
        names, chunks = load(path)
        before = report['sous-titres ajoutés']
        over = overlapped(names, chunks, texts)
        fixed = fix_scripts(name, names, chunks)
        if fixed:
            report['correctifs de scripts'] += fixed
        ids = {v: k for k, v in names.items()}
        if CAPTION not in ids:
            ids[CAPTION] = max(names) + 1
            names[ids[CAPTION]] = CAPTION
        key = (ids[CAPTION] << 8) | 3
        shown = captions_shown(names, chunks)
        linked = launched_by_text(names, chunks)
        cap_type = next((action(c.raw)[0] for c in walk(chunks) if c.children is None and names[c.cid] in ACTIONS
                         and names.get(action(c.raw)[1] >> 8) == CAPTION), 0x8E)
        for c in walk(chunks):
            if not c.children:
                continue
            new = []
            # le script affiche déjà un texte (fenêtre avec portrait, sous-titre), ou il est lancé par un script qui
            # en affiche un : la réplique a son texte
            title = script_title(c) if names[c.cid] == 'Script' else None
            texted = any(shown_label(names, ch) for ch in c.children)
            for ch in c.children:
                new.append(ch)
                if ch.children is not None or names[ch.cid] not in ACTIONS:
                    continue
                atype, k, args, tail = action(ch.raw)
                if names.get(k >> 8) not in SPEAK or not args or args[0][0] != 12:
                    continue
                event = args[0][3]
                found = texts.get(event)
                if not found:
                    continue
                sound, text, seconds = found
                if event.lower() in shown or sound in shown or texted or \
                        already_shown(texts, found, linked.get(title)):
                    report['déjà sous-titrées'] += 1
                    continue
                if (title, event.lower()) in over:
                    report['texte AotR en même temps'] += 1
                    continue
                if not text:
                    report['sans texte FR'] += 1
                    continue
                label = f'SCRIPT:{event}'
                new.append(Chunk(ch.cid, ch.ver, None,
                                 raw=caption(cap_type, key, label, max(3.0, seconds + 0.5), tail)))
                if label.lower() not in have:
                    spk = texts.speaker(event) or texts.speaker(sound)     # « MGHelms_Theoden010 » plus sûr que « theo »
                    line = f'{spk} : {text}' if spk else text
                    if shared is not None and label.lower() not in texts.map_keys:
                        shared.setdefault(label, line)
                    else:
                        added_keys[label] = line
                report['sous-titres ajoutés'] += 1
            c.children = new
        if report['sous-titres ajoutés'] > before or fixed:  # carte inchangée : on garde celle du mod
            os.makedirs(os.path.join(out_dir, name), exist_ok=True)
            save(os.path.join(out_dir, name, os.path.basename(path)), names, chunks)
    if added_keys:
        items = list(items) + [strfile.Entry(key=k, line=0, body=[rules.french_typography(f'"{v}"')])
                               for k, v in added_keys.items()]
        strfile.write(os.path.join(out_dir, name, 'map.str'), items)
    print(f'{name} : {dict(report)} ; {len(added_keys)} textes ajoutés au map.str'
          + (f' ({len(shared)} pour lotr.str au total)' if shared is not None else ''))
    return report


def bilan(name, texts):
    """Chaque son lancé par un script de la carte : [carte, script, action, événement, fichier, statut, VO, FR]."""
    rows = []
    for path in map_files(name):
        names, chunks = load(path)
        shown = captions_shown(names, chunks)
        over = overlapped(names, chunks, texts)
        linked = launched_by_text(names, chunks)

        def visit(chunks, script):
            texted = any(shown_label(names, c) for c in chunks)
            for c in chunks:
                if c.children is not None:
                    title = script
                    if names[c.cid] == 'Script' and len(c.head) >= 2:
                        ln = struct.unpack_from('<H', c.head, 0)[0]
                        title = c.head[2:2 + ln].decode('cp1252', errors='replace')
                    visit(c.children, title)
                    continue
                if names[c.cid] not in ACTIONS:
                    continue
                atype, k, args, _ = action(c.raw)
                aname = names.get(k >> 8, '')
                if aname not in SPEAK and aname != 'SPEECH_PLAY':
                    continue
                event = next((a[3] for a in args if a[3]), '')
                found = texts.get(event) if event else None
                r = texts.lines.get(found[0]) if found else None
                if not found:
                    status = 'son (pas une réplique connue)'
                elif event.lower() in shown or found[0] in shown or texted or \
                        already_shown(texts, found, linked.get(script)):
                    status = 'sous-titrée par AotR'
                elif (script, event.lower()) in over:
                    status = "texte d'AotR en même temps (non sous-titrée)"
                elif aname == 'SPEECH_PLAY':
                    status = 'SPEECH_PLAY (non traité)'
                elif not found[1]:
                    status = 'sans texte'
                else:
                    status = 'sous-titre ajouté'
                rows.append([name, script, aname, event, found[0] if found else ', '.join(texts.files(event)[1:]),
                             status, r['VO'] if r else '', found[1] if found else ''])
        visit(chunks, '')
    return rows


if __name__ == '__main__':
    args = sys.argv[1:]
    texts = Texts(os.path.join(ROOT, 'work', 'doublage', 'repliques.csv'))
    if args and args[0] == '--bilan':
        out, wanted = args[1], args[2:] or sorted(os.listdir(MOD_MAPS))
        rows = [r for name in wanted for r in bilan(name, texts)]
        with open(out, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(['carte', 'script', 'action', 'événement', 'fichier', 'statut', 'VO', 'FR'])
            w.writerows(rows)
        print(collections.Counter(r[5] for r in rows), '->', out)
    else:
        for name in args[1:] or sorted(os.listdir(MOD_MAPS)):
            run(name, args[0], texts)
