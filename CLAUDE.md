# AOTR-Trad-FR — Traduction française d'Age of the Ring

Traduction FR du mod **Age of the Ring (AotR)** pour BFME II / RotWK, maintenue depuis la sortie du mod.
Objectif : **une base propre et outillée** pour que chaque version (10.0 prévue le 31/10/2026) se traite
par *delta* avec des scripts, plutôt qu'à la main sur un fichier de 3 Mo.

---

## 1. Cartographie

| Élément | Chemin |
|---|---|
| Traduction FR (fichier maître) | `lotr.str` — téléchargé par les joueurs depuis laterredumilieu.fr/mods/aotr |
| Maps FR | `maps/maps/<map>/map.str` (34 maps) |
| VO de référence | `English_folder_str/lotr_<version>.str` (7.0 → 9.3.3) et `English_folder_str/maps/<map>/map.str` (VO actuelle) |
| Glossaire | `glossaire.csv` (généré depuis la traduction, puis arbitré à la main) |
| Voix validées après écoute | `audio_valides.txt` |
| Scripts | `tools/` (voir §4) |
| Travail temporaire | `work/` (non versionné : rapports, lots, submod construit, paires audio) |
| Anciennes traductions | `Ancien_fichier/` (archives, ne pas modifier) |
| Mod installé (launcher) | `C:\AgeoftheRing\aotr\` — `data/lotr.str` et `maps/*/map.str` sont la **VO** |
| Base du launcher | `C:\AgeoftheRing\bfme2`, `C:\AgeoftheRing\rotwk` (installations **anglaises**) |
| Jeux FR d'origine (EA) | `C:\Program Files (x86)\Electronic Arts\La Bataille pour la Terre du Milieu II` et `...\L'Avènement du Roi-sorcier` |
| Submods du launcher | `%APPDATA%\Age of the Ring\Mods\<nom>\<version>\source\` + `mods_manifest.json` |

## 2. Périmètre

1. **Texte** — `data/lotr.str` (23 748 entrées) et `maps/<map>/map.str`.
2. **Voix vanilla** (~11 500) — AotR les lit depuis l'`EnglishAudio.big` de la base anglaise du launcher.
   La VF officielle existe pour presque toutes → archive `!AotR_VF.big` dans le submod.
3. **Voix d'EA reprises dans `data/audio/sounds`** — les fichiers du mod passent avant les `.big`, il faut donc
   les remplacer un par un. BFME II / RotWK : 507 sûres (même durée que la VO vanilla), 166 validées
   (`audio_valides.txt` après écoute), 43 à écouter. **BFME1** (campagnes BFME1 `mghelms`, `meminas`… et unités,
   VF dans `C:\BFME1\lang\frenchaudio.big`, sans VO anglaise de référence) : 2 396 sûres (durée de la VF à ±20 % de
   celle du mod), 230 à écouter.
4. **Cinématiques** (73 extraits `data/audio/speech/*.mp3`, son lu à part de la vidéo `data/movies/*.vp6`) :
   `cinematiques_vf.py` y retrouve les plans des films (pistes eng/fre de `C:\Users\Paulr\Videos\lotr`) et les
   cinématiques EA (VO/VF des jeux) et y pose la VF → 87 min sur 97. Le reste (narration propre à AotR, montages sur
   une autre musique) est **sous-titré** via `soustitres.csv` (voir §4), en attendant un doublage.
   `CS01` (intro du jeu) : narration AotR sur musique, seulement sous-titrée ; la séparation voix/musique (Demucs)
   n'a pas trouvé de répliques des films exploitables.
5. **Doublage des campagnes** (6 200 répliques sans VF d'EA : `mgfotr_*` de la campagne 10.0, anciennes campagnes
   AotR `mgrotk`/`mgnfotr`/`mghob`/`mgtt`/`mgshadow`, ajouts à Angmar `madestr`/`macarnd`…, civils `mtciv*` ; motif
   `CAMPAIGN` de `doublage.py`, voix d'unités exclues) : 233 reprises automatiquement des films ;
   le reste est enregistré par une équipe de doubleurs. Texte : clé `SCRIPT:` de `lotr.str`, sinon nom du
   script de la carte, sinon Whisper ; traduction par lots (`doublage.py lots`) ; livraison dans
   `work/doublage/enregistrements/` (`.wav` au nom de la VO), contrôlée par `doublage.py controle` puis intégrée par
   `build_submod.py`. Guide pour les doubleurs : artifact « Doublage VF d'Age of the Ring ».
6. **Hors périmètre** : voix d'unités propres à AotR (sans équivalent EA).
7. **À vérifier** : textes en dur dans les `.apt`/`.big` d'interface (`AOTR*.big`, `MainMenu.apt`). Les `$Label` des
   `.apt` lisent `APT:Label` dans `lotr.str`. Mais le « Loading » de l'écran de chargement est **dessiné dans
   l'image** `art/compiledtextures/lo/loadpage_bg.dds` : `chargement.py` en fait une version « CHARGEMENT » (submod).

## 3. Distribution

- **Téléchargement direct** de `lotr.str` (tutoriel) : marche en multijoueur, mais le launcher voit une différence avec le patch.
- **Submod « Traduction FR »** (Submod Manager, genre *Translation*, publiable dans le Mod Workshop) : le launcher copie
  `source/` dans `C:\AgeoftheRing\aotr` au lancement et restaure à la fermeture. Contenu :
  ```
  source/data/lotr.str                   lotr.str + lotr_base.str (203 clés du jeu de base) + SUBTITLE:AOTRFR_*
  source/maps/<map>/map.str
  source/!AotR_VF.big                    voix vanilla en VF (~840 Mo)
  source/data/audio/sounds/<voix>.wav    voix modifiées par AotR, en VF ; répliques de campagne mgfotr_* tirées des
                                         films (work/voix_vf) ou doublées (work/doublage/enregistrements, contrôlées)
  source/data/audio/speech/<extrait>.mp3 cinématiques en VF (work/cinematiques/vf)
  source/data/ini/video.ini              celle du mod + HasSubtitles sur les vidéos sous-titrées
  source/data/english/movies/<Video>.ini sous-titres de vidéo (textes SUBTITLE:AOTRFR_* ajoutés au lotr.str du submod)
  ```
  D'après la FAQ, les submods sont **solo uniquement** pour l'instant (à confirmer en test pour le genre *Translation*).
- **Version 1 (01/11/2026) : « VO sous-titrée »** — pas d'alternance VF/VO dans une même scène. Texte et voix d'unités
  en FR ; dialogues de campagne en VO (toutes les missions mêlent répliques VF et ajouts d'AotR en anglais) ; cinématiques
  100 % films en VF, cinématiques mixtes (11) et intro `CS01` en VO avec sous-titres complets (texte du doublage pour les
  répliques des films). La VF des campagnes viendra avec le doublage (`build_submod.py --campagne-vf`).
- Les voix VF sont des ressources EA : **jamais dans le dépôt Git** (`*.big` est ignoré). On les génère depuis les jeux FR installés.
  Idem pour les cinématiques VF (son des films, sous droits Warner/New Line) : `work/` seulement, à ne pas publier sans réflexion.

## 4. Outils (`tools/`, Python 3 sans dépendance)

| Script | Rôle |
|---|---|
| `strfile.py` | Lecture/écriture `.str` (cp1252, CRLF, commentaires dans les entrées, doublons) |
| `bigfile.py` | Lecture/extraction des archives `.big` |
| `rules.py` | Placeholders, raccourcis `&`, typographie FR (espace insécable) |
| `check.py fr vo [csv]` | Contrôles : manquantes, obsolètes, doublons, placeholders, `&`, identiques à la VO, format |
| `diff_versions.py ancienne_vo nouvelle_vo fr [csv]` | Liste de travail d'une mise à jour : ajoutées / modifiées / supprimées |
| `rebuild.py vo sortie fr [fr2…] [--typo]` | Reconstruit la FR dans l'ordre et la structure de la VO, sans clés obsolètes |
| `hotkeys.py fr vo [--fix]` | Aligne les raccourcis `&` sur la VO (lettre VO, W → Z pour l'AZERTY, format `[&X]`) |
| `quotes.py fr [--fix]` | Guillemets non échappés dans une valeur (le jeu y coupe le texte) → « » |
| `glossary.py fr vo [csv]` | Génère `glossaire.csv` et marque les termes traduits de plusieurs façons |
| `memoire.py liste.csv… --nous vo fr` | Pré-remplit les listes de diff (`*_tm.csv`) depuis notre traduction et les VF officielles BFME1 (`C:\BFME1`), BFME II, RotWK ; répare le mojibake |
| `lots.py decoupe \| verifie \| reinjecte` | Découpe en `lot_NN.csv` (+ glossaire du lot, traduction proche de référence), contrôle un `lot_NN_fr.csv`, réunit les lots en `.str` |
| `audio_vf.py analyse \| ecoute <dir> \| build <dir>` | Classement des voix, paires à écouter, construction de l'audio VF |
| `cinematiques_vf.py <sortie> [extrait…] [--controle]` | VF des cinématiques (numpy + ffmpeg) → `<sortie>/<extrait>.mp3` + `liste.csv` (part VF, passages restés en anglais) |
| `cinematiques_vf.py <sortie> "mgfotr_*" --voix` | Même chose pour les répliques de campagne (`data/audio/sounds`) tirées des films → `work/voix_vf` (233) |
| `films_voix.py [--controle]` | Répliques de campagne tirées des films retrouvées **par le texte** (sous-titres anglais des versions longues), calées par le son dans ±20 s, VF posée → `work/voix_vf` + `liste_texte.csv` |
| `base_vf.py` | `lotr_base.str` : clés du jeu de base absentes du `lotr.str` d'AotR (sinon lues en anglais dans `English.big`), VF officielle de RotWK ; ajouté au `lotr.str` du submod par `build_submod.py` |
| `chargement.py` | Image de fond de l'écran de chargement avec « CHARGEMENT » (police Aniron à installer, DDS DXT3, Pillow) → `work/chargement/` ; copiée par `build_submod.py` |
| `mapfile.py` | Décompression RefPack des `.map` et chaînes des scripts (« Audio - Qui - Texte » avant le son joué) |
| `doublage.py <liste.csv> [--transcrit] \| lots \| reinjecte \| roles \| controle` | Répliques de campagne à doubler (`work/doublage/repliques.csv` : personnage, mission, durée, VO, FR) ; lots de traduction ; dossiers par rôle avec la VO de référence ; contrôle des `.wav` livrés |
| `saut_mission.py <départ> <voulue> \| --annule \| --liste` | Test en jeu : la mission de départ du Save Generator (`FordsofIsen`, `LordoftheRings`) charge une autre carte (INI de campagne copié dans le submod) ; **annuler après le test** |
| `soustitres.py transcrit \| construit` | Transcrit (faster-whisper) les passages anglais dans `soustitres.csv` (colonne FR à remplir) ; génère les sous-titres de vidéo du submod |
| `soustitres_cartes.py <sortie> [carte…] \| --bilan <rapport.csv> [carte…]` | Ajoute aux scripts des cartes solo un `SHOW_MILITARY_CAPTION` (« PERSONNAGE : FR ») après chaque réplique jouée sans texte (`SOUND_PLAY_NAMED`, `PLAY_SOUND_EFFECT*`) ; texte : `repliques.csv`, sinon sous-titres VF de BFME1. Appelé par `build_submod.py` (carte réécrite non compressée, ~6 000 sous-titres) ; les textes vont dans le `lotr.str` du submod (un map.str vide dans le mod n'était pas lu : MISSING à la Dernière Alliance), sauf les clés qu'un map.str définit déjà. Locuteur deviné du nom du son (`SPEAKER_CODES` pour les exceptions : `Cine` sans locuteur, Saroumane, Haldir…) ; extraits `Cine` sans parole non sous-titrés. `--bilan` : chaque son lancé par un script, sous-titré ou non. Un seul emplacement pour `SHOW_MILITARY_CAPTION` (le dernier texte remplace le précédent) : `overlapped()` date textes et sons en suivant les minuteurs de chaque scène et n'ajoute pas notre sous-titre s'il couperait un texte d'AotR de plus de 3 s ou s'il serait remplacé en moins de 1,5 s (doublon) ; `SCRIPT_FIXES` : actions ajoutées aux scripts d'AotR (Feux d'alarme : noms de lieux en pause pendant les cinématiques, sinon « RATH DÍNEN » cachait Pippin) |
| `build_submod.py --dest <dir> \| --mod "<nom>" [--sans-audio] [--campagne-vf]` | Assemble le submod (dans `work/` ou dans le dossier du launcher), avec cinématiques VF et sous-titres. Par défaut (version 1) : dialogues de campagne (`m…_*.wav`) en VO, cinématique sous-titrée = VO ; `--campagne-vf` remet la VF des campagnes |
| `paquet_test.py [sortie.zip] [--sans-audio]` | Zip du submod du launcher pour un testeur (dossier + bloc de `mods_manifest.json` + LISEZMOI) ; `--sans-audio` ≈ 50 Mo au lieu de ≈ 860 Mo. Contient des ressources EA/films : envoi privé seulement |


Lancer les scripts depuis la racine du dépôt (`python tools/...`). Sous Git Bash, ajouter `PYTHONIOENCODING=utf-8` pour l'affichage.
Exceptions au « sans dépendance » : `cinematiques_vf.py` (numpy, ffmpeg) et `soustitres.py transcrit` (faster-whisper).
Pour modifier un `.str`, réécrire `strfile.read(p).items` (pas `.entries`, qui perd lignes vides et commentaires).

**Sous-titres de vidéo** (moteur, non documenté, retrouvé dans `game.dat`) : `HasSubtitles = Yes` dans le bloc `Video`,
puis `data/english/movies/<Video>.ini` avec un bloc `SubTitles <Video>` (`FontName`, `FontPitch`, `SubTitleType`,
`LineTable` = **15** hauteurs croissantes, lignes `SubTitle = Label:<X> Color:R G B Style Align Line StartFrame EndFrame`).
Le moteur cherche `SUBTITLE:<X>` (ne pas mettre le préfixe dans `Label`). Une erreur de syntaxe fait planter le jeu au lancement.

## 5. État au 31/10/2026 (base 10.0)

- **Patch 10.0.1 (10/11/2026)** : 2 ajoutées, 4 modifiées, 1 supprimée dans `lotr.str` (objectif des Feux d'alarme scindé
  en `Objective06_BeaconsA/B`, message de version différente en ligne, `GUI:LobbyRoom2` = BFME2) + 1 réplique de Pippin
  dans `map good lighting the beacons` (dont le `.map` a changé : submod à reconstruire). Aucun son ni cinématique modifié.
  VO : `English_folder_str/lotr_10.0.1.str`.

- Mise à jour 10.0 : 2 012 ajoutées + 264 modifiées dans `lotr.str`, ~2 770 dans les maps (nouvelle campagne
  « Le Seigneur des Anneaux », 16 nouvelles maps `good`). 462 reprises par `memoire.py`, 4 586 traduites en 20 lots
  (Sonnet) puis relues (Sonnet). `lotr.str` et les 48 maps : 0 manquante, 0 obsolète, 0 placeholder.
- Maps retirées en 10.0 : `hobbit azanulbizar` (textes passés dans `lotr.str`), `mp besiege helms deep`, `sp evil fornost`.
- Noms de la Comté arbitrés (Ledoux) : Sacquet de Besace, l'Ancien (Gaffer), Ted Rouquin, Bill Fougeard, Grenouillers,
  Sanglebuc ; Sharkey et Shirriff gardés. Questions des relecteurs : `work/lots_10.0/questions.csv` (119, non versionné).
- Audio 10.0 : Aragorn n'a plus de voix modifiées ; 65 nouvelles d'Éowyn ; 11 voix d'Éomer retirées d'`audio_valides.txt`
  (fichiers remplacés). 53 paires d'unités validées à l'écoute.
- Cinématiques : 68 extraits en VF (films + VF EA d'Angmar, `CS11`, `CS15`), 53 sous-titres dans 12 vidéos
  (`soustitres.csv`). `APT:Loading` traduit. Intro `CS01` : gardée en VO, entièrement sous-titrée (répliques AotR,
  répliques des films, titres incrustés entre crochets) ; un essai avec la voix VF des films isolée par Demucs existe
  dans `work/cinematiques/essai/`.

### Nettoyage du 30/10/2026 (base 9.3.3)

- `lotr.str` reconstruit sur la VO 9.3.3 : **0 manquante, 0 obsolète, 0 problème de placeholder**, typographie harmonisée.
- Corrigé : 10 clés traduites par erreur (`OBJET : …`, `LWA:GarnisonHaradwaith`…), 5 traductions sans clé,
  29 entrées nouvellement traduites, 3 placeholders cassés (`%ls` manquant, `15%d'armure`, `%%`).
- Doublons : ce sont ceux de la VO (mise en correspondance par position).
- Raccourcis alignés sur la VO (56 corrigés) ; guillemets internes remplacés par « » (27 lignes, lotr.str et maps).
- Audio : 611 voix sûres + 124 voix d'unités validées à l'écoute (`audio_valides.txt`).
  Les 42 dialogues de campagne douteux (`ma*`, `mg*`, `me*`) restent en VO : AotR les a raccourcis, leurs sous-titres diffèrent.
  Une comparaison automatique de signal ne permet pas de trancher : AotR a retraité ses fichiers (même les voix sûres ne corrèlent pas).
- **Reste à faire** :
  - ~324 entrées identiques à la VO à passer en revue ;
  - 202 termes « à arbitrer » dans `glossaire.csv`.

---

## 6. Organisation des agents (chef d'orchestre)

La session principale est le **chef** : elle planifie, découpe, délègue, vérifie et assemble.
Elle **ne lit jamais** `lotr.str` en entier (≈ 1 M de tokens) et ne traduit pas elle-même en masse.

| Rôle | Modèle | Ce qu'il fait | Pourquoi ce modèle |
|---|---|---|---|
| **Chef** (session principale) | Opus | Plan, découpage en lots, arbitrages, petites traductions (< 50 entrées), relecture ciblée | Jugement, coût concentré sur peu de tokens |
| **Outilleur** | — (scripts `tools/`) | Parsing, diff, extraction de lots, réinjection, contrôles | Gratuit et déterministe : **toujours préférer un script à un agent** |
| **Traducteur** | Sonnet | Traduit un lot de 150–300 entrées avec l'extrait utile du glossaire | Bon rapport qualité/coût sur du texte de jeu |
| **Relecteur** | Sonnet | Relit un lot traduit : sens, glossaire, ton, longueur, `&` | Indépendant du traducteur (pas le même agent) |
| **Explorateur** | Haiku | Recherches larges et mécaniques | Lecture d'extraits, peu de jugement |

Fable/Opus en sous-agent seulement pour un lot à forte valeur littéraire (dialogues de campagne, lore) et sur demande.

### Règles d'économie de crédits

1. **Script d'abord** : comptage, diff, extraction, validation → `tools/`, jamais en lisant les fichiers dans le contexte.
2. **Travailler par delta** : ne traduire que les lignes « ajoutée » / « modifiée » de `diff_versions.py`.
3. **Lots autonomes** : un fichier `work/lot_NN.csv` (`clé ; VO ancienne ; VO nouvelle ; FR actuelle`) + les termes du glossaire qui y apparaissent. Le sous-agent ne reçoit que ça et renvoie un CSV `clé ; FR`.
4. **Lots en parallèle**, envoyés dans un seul message ; jamais plus de ~5 agents simultanés sans accord.
5. **Pas de double travail** : un lot délégué n'est pas refait par le chef ; contrôle par `check.py` + échantillon.
6. **Lecture ciblée** : `Grep` sur une clé, `Read` avec `offset/limit`. Attention : les `.str` sont en CRLF, donc `grep -x` ne trouve rien ; passer par `strfile.py`.
7. Les gros traitements (au-delà de ~20 agents) passent par un Workflow **uniquement si l'utilisateur le demande**.

---

## 7. Règles de traduction (tous les agents)

- **Encodage** : `.str` en **Windows-1252**, fins de ligne **CRLF**. Ne jamais réécrire en UTF-8. Toujours écrire via `strfile.py`.
- **Structure** : `CLÉ` / `"texte"` / `END`. **Ne jamais traduire ni modifier une clé** (même mal orthographiée dans la VO, ex. `OBJECT:ArgonathStatues"`).
- **Ne pas toucher** : placeholders `%d %s %ls %l %h %02d` (même nombre que la VO), `\n`. Ne jamais coller un `%` à une lettre (`15%d'armure` serait lu comme `%d`).
- **Raccourcis `&`** : autant de `&` que la VO, devant une lettre du libellé ou sous la forme `(&X)`.
- **Dialogues** : préfixe du locuteur avec la casse de la VO, rôle traduit (`"LEGOLAS : ..."`, `"Aragorn : ..."`, `"OFFICIER ELFE : ..."`).
- **Typographie** : espace insécable (0xA0) devant `? ! : ;` (appliquée automatiquement par `rebuild.py --typo`), majuscules accentuées (`ARMÉE`).
- **Terminologie** : `glossaire.csv` d'abord, puis la traduction existante du dépôt. Un terme inconnu est remonté au chef, pas inventé.

## 8. Procédure pour une nouvelle version (ex. 10.0)

1. Copier la VO : `C:\AgeoftheRing\aotr\data\lotr.str` → `English_folder_str/lotr_10.0.str` ; maps → `English_folder_str/maps/` (garder l'ancienne VO des maps dans `work/` pour le diff).
2. `python tools/diff_versions.py English_folder_str/lotr_9.3.3.str English_folder_str/lotr_10.0.str lotr.str work/diff_10.0.csv`
   Maps : même diff par map (ancienne VO de `work/` → VO du mod) dans `work/maps_diff_<v>/<map>.csv`.
3. `python tools/memoire.py work/diff_10.0.csv work/maps_diff_10.0/*.csv --nous English_folder_str/lotr_9.3.3.str lotr.str --nous work/maps_vo_9.3.3 maps/maps`
   (reprises exactes), puis `python tools/lots.py decoupe work/lots_10.0 work/diff_10.0_tm.csv work/maps_diff_10.0/*_tm.csv --nous …`.
   Traducteurs (Sonnet) → relecteurs (Sonnet), chacun valide son lot avec `lots.py verifie`.
4. `python tools/lots.py reinjecte work/lots_10.0 work/nouveau_10.0 work/diff_10.0_tm.csv work/maps_diff_10.0/*_tm.csv`, puis
   `python tools/rebuild.py English_folder_str/lotr_10.0.str lotr.str work/nouveau_10.0/lotr.str lotr.str --typo`
   (la première source qui contient la clé l'emporte : **les nouvelles traductions d'abord**, sinon les « modifiées » gardent l'ancienne FR).
5. `python tools/hotkeys.py lotr.str English_folder_str/lotr_10.0.str --fix`, `python tools/quotes.py lotr.str --fix`, puis
   `python tools/check.py lotr.str English_folder_str/lotr_10.0.str work/check_10.0.csv` → 0 manquante, 0 placeholder.
6. Même chose pour les maps, puis `python tools/audio_vf.py analyse` (de nouvelles voix ont pu changer).
   Cinématiques : `python tools/cinematiques_vf.py work/cinematiques/vf`, puis
   `python tools/soustitres.py transcrit work/cinematiques/vf/liste.csv soustitres.csv` et traduire les nouvelles lignes
   (colonne FR ; répliques des films : **texte du doublage français**, pas les sous-titres officiels, qui sont
   reformulés pour la lecture — on reconnaît la réplique telle qu'on l'entend en VF).
7. `python tools/build_submod.py --mod "Traduction FR"`, test en jeu, commit `update traduction 10.0`, publication.

## 9. Questions ouvertes

- Un submod de genre *Translation* fonctionne-t-il en multijoueur ? (à tester)
- `!AotR_VF.big` passe-t-il bien avant l'`EnglishAudio.big` de la base ? (à tester en jeu sur une unité vanilla)
