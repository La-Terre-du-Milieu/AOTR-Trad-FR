"""Assemble le dossier source/ du submod « Traduction FR » pour le Submod Manager du launcher.

source/ reproduit l'arborescence de C:\\AgeoftheRing\\aotr ; le launcher la copie dans le jeu
au lancement et restaure les originaux à la fermeture.

Usage :
  python tools/build_submod.py --dest <dossier>            (ex. work/submod/source)
  python tools/build_submod.py --mod "Traduction FR"       (dossier du mod créé dans le launcher)
  options : --sans-audio
            --campagne-vf : dialogues de campagne en VF (films, EA, doublage) ; par défaut ils restent en VO
                            sous-titrée, pour ne pas alterner VF et VO dans une même mission (version 1)

Une cinématique qui a des sous-titres dans soustitres.csv est livrée en VO : son mix VF éventuel (films + VO d'AotR)
mélangerait les deux langues.
"""
import json
import os
import re
import shutil
import subprocess
import sys

import audio_vf
import chargement
import doublage
import rules
import soustitres
import soustitres_cartes
import strfile

ROOT = audio_vf.ROOT
MOD_MAPS = os.path.join(audio_vf.AOTR, 'aotr', 'maps')
SUBTITLES = os.path.join(ROOT, 'soustitres.csv')
BASE_STRINGS = os.path.join(ROOT, 'lotr_base.str')
CINEMATICS = os.path.join(ROOT, 'work', 'cinematiques', 'vf')
FILM_VOICES = os.path.join(ROOT, 'work', 'voix_vf')
DUBBING_LIST = os.path.join(ROOT, 'work', 'doublage', 'repliques.csv')
RECORDINGS = os.path.join(ROOT, 'work', 'doublage', 'enregistrements')   # livraisons des doubleurs (.wav)
# cartes solo dont les scènes reçoivent des sous-titres (tools/soustitres_cartes.py) ; pas les cartes multijoueur,
# qui seraient différentes de celles des joueurs sans le submod
CAPTION_MAPS = sorted(m for m in os.listdir(MOD_MAPS) if re.match(r'(?i)map (good|evil|ang|hobbit|sp) ', m)) \
    if os.path.isdir(MOD_MAPS) else []
LAUNCHER_MODS =os.path.join(os.environ.get('APPDATA', ''), 'Age of the Ring', 'Mods')
# dialogues de campagne (mg*, me*, ma*, mt*…) ; pas les répliques d'escarmouche (mskirmi_) ni les voix d'unités
# (mublorc_voiatba…) ; les cinématiques (.mp3) suivent la règle des sous-titres
CAMPAIGN_DIALOGUE = re.compile(r'(?i)^m(?!skirmi_)[a-z]+_(?!voi).*\.wav$')


def campaign_line(name):
    return bool(CAMPAIGN_DIALOGUE.match(name if '.' in name else name + '.wav'))


def wrap_dialogues(path):
    """Textes affichés par les scripts de carte (SCRIPT:, DIALOGEVENT:) : le moteur ne les enroule pas et ils
    sortent de l'écran -> \\n ajoutés dans le .str du submod (pas dans le dépôt, qui suit les \\n de la VO)."""
    items = strfile.read(path).items
    n = 0
    for e in items:
        if not isinstance(e, strfile.Entry) or not re.match(r'(?i)(script|dialogevent):', e.key) \
                or 'objective' in e.lkey:
            continue
        values = [i for i, b in enumerate(e.body) if b.strip().startswith('"')]
        if len(values) != 1:
            continue
        i = values[0]
        line = e.body[i]
        start, end = line.index('"'), line.rindex('"')
        new = rules.wrap(line[start + 1:end])
        if new != line[start + 1:end]:
            e.body[i] = line[:start + 1] + new + line[end:]
            n += 1
    if n:
        strfile.write(path, items)
    return n


def launcher_source(display_name):
    with open(os.path.join(LAUNCHER_MODS, 'mods_manifest.json'), encoding='utf-8') as f:
        submods = json.load(f)['submods']
    for key, mod in submods.items():
        if display_name in (key, mod.get('display_name')):
            return os.path.join(LAUNCHER_MODS, key, mod['active_version'], 'source')
    sys.exit(f'Mod « {display_name} » introuvable : le créer d\'abord dans le launcher (Create Mod). '
             f'Mods existants : {", ".join(m.get("display_name", k) for k, m in submods.items())}')


def build(dest, audio=True, campaign_vf=False):
    keep = (lambda name: True) if campaign_vf else (lambda name: not campaign_line(name))
    for sub in ('data', 'maps', 'art'):    # repartir propre (maps supprimées du mod, voix retirées…)
        shutil.rmtree(os.path.join(dest, sub), ignore_errors=True)
    os.makedirs(os.path.join(dest, 'data'), exist_ok=True)
    shutil.copy(os.path.join(ROOT, 'lotr.str'), os.path.join(dest, 'data', 'lotr.str'))
    maps = os.path.join(ROOT, 'maps', 'maps')
    for name in os.listdir(maps):
        src = os.path.join(maps, name, 'map.str')
        # seulement les maps dont le mod a encore un map.str (les autres ont été supprimées ou fusionnées)
        if os.path.exists(src) and os.path.exists(os.path.join(MOD_MAPS, name, 'map.str')):
            os.makedirs(os.path.join(dest, 'maps', name), exist_ok=True)
            shutil.copy(src, os.path.join(dest, 'maps', name, 'map.str'))
    print(f'texte : lotr.str + {len(os.listdir(os.path.join(dest, "maps")))} maps -> {dest}')
    if os.path.exists(BASE_STRINGS):
        # clés du jeu de base absentes du lotr.str d'AotR (tools/base_vf.py), sinon lues en anglais dans English.big
        with open(os.path.join(dest, 'data', 'lotr.str'), 'ab') as out, open(BASE_STRINGS, 'rb') as src:
            out.write(b'\r\n' + src.read())
    if CAPTION_MAPS:
        # sous-titres ajoutés aux scènes qu'AotR joue sans texte : carte modifiée + map.str complété
        # textes dans lotr.str (toujours lu ; un map.str vide dans le mod n'était pas relu : MISSING en jeu)
        texts, shared = soustitres_cartes.Texts(DUBBING_LIST), {}
        for name in CAPTION_MAPS:
            soustitres_cartes.run(name, os.path.join(dest, 'maps'), texts, shared)
        lotr = os.path.join(dest, 'data', 'lotr.str')
        items = strfile.read(lotr).items
        have = {i.lkey for i in items if isinstance(i, strfile.Entry)}
        new = [strfile.Entry(key=k, line=0, body=[rules.french_typography(f'"{v}"')])
               for k, v in shared.items() if k.lower() not in have]
        strfile.write(lotr, items + new)
        print(f'sous-titres des cartes : {len(new)} textes ajoutés à lotr.str')
    strs = [os.path.join(dest, 'data', 'lotr.str')] + [os.path.join(dest, 'maps', m, 'map.str')
                                                        for m in os.listdir(os.path.join(dest, 'maps'))]
    wrapped = sum(wrap_dialogues(p) for p in strs if os.path.exists(p))
    print(f'dialogues coupés sur plusieurs lignes : {wrapped}')
    # écran de chargement : « Loading » est dessiné dans l'image de fond (tools/chargement.py)
    art = os.path.join(dest, 'art', 'compiledtextures', 'lo')
    os.makedirs(art, exist_ok=True)
    if not os.path.exists(chargement.OUT):
        chargement.build(chargement.OUT)
    shutil.copy(chargement.OUT, os.path.join(art, 'loadpage_bg.dds'))
    if os.path.exists(SUBTITLES):
        soustitres.construit(SUBTITLES, dest)
    if audio and os.path.isdir(CINEMATICS):
        # cinématiques en VF (tools/cinematiques_vf.py) : jamais dans le dépôt, voir CLAUDE.md
        speech = os.path.join(dest, 'data', 'audio', 'speech')
        os.makedirs(speech, exist_ok=True)
        subtitled = {r['fichier'] for r in soustitres.read_csv(SUBTITLES)} if os.path.exists(SUBTITLES) else set()
        clips = [f for f in os.listdir(CINEMATICS) if f.endswith('.mp3') and '__' not in f]
        vo = [f for f in clips if f[:-4] in subtitled]       # sous-titrée : reste en VO
        for f in clips:
            if f not in vo:
                shutil.copy(os.path.join(CINEMATICS, f), os.path.join(speech, f))
        print(f'cinématiques : {len(clips) - len(vo)} extraits en VF, {len(vo)} laissés en VO sous-titrée -> {speech}')
    if audio and os.path.isdir(FILM_VOICES):
        # répliques de la campagne tirées des films (cinematiques_vf.py --voix), même nom que dans data/audio/sounds
        sounds = os.path.join(dest, 'data', 'audio', 'sounds')
        os.makedirs(sounds, exist_ok=True)
        lines = [f for f in os.listdir(FILM_VOICES) if f.endswith('.wav') and '__' not in f and keep(f)]
        for f in lines:
            shutil.copy(os.path.join(FILM_VOICES, f), os.path.join(sounds, f))
        print(f'répliques des films : {len(lines)} en VF -> {sounds}')
    if audio and os.path.isdir(RECORDINGS) and os.path.exists(DUBBING_LIST):
        # doublage de l'équipe VF (doublage.py controle), converti au format du fichier VO ; passe avant les films
        sounds = os.path.join(dest, 'data', 'audio', 'sounds')
        os.makedirs(sounds, exist_ok=True)
        accepted = {n: s for n, s in doublage.controle(DUBBING_LIST, RECORDINGS).items() if keep(n)}
        for name, src in accepted.items():
            vo = doublage.wav_info(os.path.join(doublage.SOUNDS, name + '.wav'))
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-c:a', 'pcm_s16le', '-ar', str(vo['fréquence']),
                            '-ac', str(vo['canaux']), os.path.join(sounds, name + '.wav')], check=True)
        print(f'doublage VF : {len(accepted)} répliques enregistrées -> {sounds}')
    if audio:
        games, mod = audio_vf.load()
        audio_vf.build(dest, games, mod, audio_vf.analyse(games, mod), skip=lambda name: not keep(name))


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--mod' in args:
        dest = launcher_source(args[args.index('--mod') + 1])
    elif '--dest' in args:
        dest = args[args.index('--dest') + 1]
    else:
        sys.exit(__doc__)
    build(dest, audio='--sans-audio' not in args, campaign_vf='--campagne-vf' in args)
