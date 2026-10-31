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
3. **Voix vanilla modifiées par AotR** (777 fichiers dans `data/audio/sounds`) — les fichiers du mod passent
   avant les `.big`, il faut donc les remplacer un par un :
   **611 sûres** (même durée que la VO vanilla), **166 à écouter** (`audio_valides.txt` après écoute).
4. **Hors périmètre** : voix propres à AotR (sans équivalent EA), narration `data/audio/speech` et vidéos
   (sous-titres dans `lotr.str`).
5. **À vérifier** : textes en dur dans les `.apt`/`.big` d'interface (`AOTR*.big`, `MainMenu.apt`).

## 3. Distribution

- **Téléchargement direct** de `lotr.str` (tutoriel) : marche en multijoueur, mais le launcher voit une différence avec le patch.
- **Submod « Traduction FR »** (Submod Manager, genre *Translation*, publiable dans le Mod Workshop) : le launcher copie
  `source/` dans `C:\AgeoftheRing\aotr` au lancement et restaure à la fermeture. Contenu :
  ```
  source/data/lotr.str
  source/maps/<map>/map.str
  source/!AotR_VF.big                    voix vanilla en VF (~840 Mo)
  source/data/audio/sounds/<voix>.wav    voix modifiées par AotR, en VF
  ```
  D'après la FAQ, les submods sont **solo uniquement** pour l'instant (à confirmer en test pour le genre *Translation*).
- Les voix VF sont des ressources EA : **jamais dans le dépôt Git** (`*.big` est ignoré). On les génère depuis les jeux FR installés.

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
| `audio_vf.py analyse \| ecoute <dir> \| build <dir>` | Classement des voix, paires à écouter, construction de l'audio VF |
| `build_submod.py --dest <dir> \| --mod "<nom>" [--sans-audio]` | Assemble le submod (dans `work/` ou dans le dossier du launcher) |

Lancer les scripts depuis la racine du dépôt (`python tools/...`). Sous Git Bash, ajouter `PYTHONIOENCODING=utf-8` pour l'affichage.

## 5. État au 30/10/2026 (base 9.3.3, après nettoyage)

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
- **Maps** : préfixe du locuteur en majuscules dans les dialogues (`"LEGOLAS : ..."`).
- **Typographie** : espace insécable (0xA0) devant `? ! : ;` (appliquée automatiquement par `rebuild.py --typo`), majuscules accentuées (`ARMÉE`).
- **Terminologie** : `glossaire.csv` d'abord, puis la traduction existante du dépôt. Un terme inconnu est remonté au chef, pas inventé.

## 8. Procédure pour une nouvelle version (ex. 10.0)

1. Copier la VO : `C:\AgeoftheRing\aotr\data\lotr.str` → `English_folder_str/lotr_10.0.str` ; maps → `English_folder_str/maps/` (garder l'ancienne VO des maps dans `work/` pour le diff).
2. `python tools/diff_versions.py English_folder_str/lotr_9.3.3.str English_folder_str/lotr_10.0.str lotr.str work/diff_10.0.csv`
3. Le chef découpe « ajoutée » + « modifiée » en lots → traducteurs (Sonnet) → relecteurs.
4. Les traductions sont réunies dans `work/nouveau.str`, puis `python tools/rebuild.py English_folder_str/lotr_10.0.str lotr.str work/nouveau.str lotr.str --typo` (la première source l'emporte).
5. `python tools/hotkeys.py lotr.str English_folder_str/lotr_10.0.str --fix`, `python tools/quotes.py lotr.str --fix`, puis
   `python tools/check.py lotr.str English_folder_str/lotr_10.0.str work/check_10.0.csv` → 0 manquante, 0 placeholder.
6. Même chose pour les maps, puis `python tools/audio_vf.py analyse` (de nouvelles voix ont pu changer).
7. `python tools/build_submod.py --mod "Traduction FR"`, test en jeu, commit `update traduction 10.0`, publication.

## 9. Questions ouvertes

- Un submod de genre *Translation* fonctionne-t-il en multijoueur ? (à tester)
- `!AotR_VF.big` passe-t-il bien avant l'`EnglishAudio.big` de la base ? (à tester en jeu sur une unité vanilla)
