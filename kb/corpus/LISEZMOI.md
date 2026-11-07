# kb/corpus — ce que lit `outils/constituer_base_v2.py`

| Fichier | Rôle | À modifier quand… |
|---|---|---|
| `catalogue_sources.json` | 87 documents officiels et ouverts : identifiant, titre, dossier, exigences du hackathon (E1 à E6), autorité, date, liens, niveau de vérification du lien, utilité pour MEDIMCOM | vous trouvez un nouveau texte officiel : copiez une entrée, changez `id`, `titre`, `dossier`, `axes`, `urls` |
| `vocabulaire_consultation.json` | 1 287 notions en 30 catégories et 5 groupes (voir ci-dessous) | il manque un mot, une question, une consigne ou un conseil au traducteur |
| `filtres_pictogrammes.json` | tri des pictogrammes : liste blanche par catégorie, liste noire, exceptions, plafonds, catégories Mulberry et OpenMoji gardées, reclassement | `--audit-pictos` montre des étiquettes mal triées |

## Vocabulaire : organisé selon ce qu'on veut dire

| Groupe | Catégories |
|---|---|
| A. Ce qu'on veut dire | 01 accueil et politesse · 02 réponses et accord · 03 questions · 04 comprendre et se faire comprendre · 05 rassurer et soutenir · 06 consignes pendant l'examen · 07 conseils et recommandations |
| B. Le corps et la douleur | 08 personnes et soignants · 09 corps · 10 localisation (gauche, droite, haut, bas, dedans…) · 11 décrire une douleur (type, déclencheurs, soulagement, évolution, intensité : modèle clinique OPQRST) · 12 symptômes · 13 maladies et antécédents · 14 émotions et ressenti |
| C. Soins et traitements | 15 examens et actes · 16 médicaments et posologie (forme, voie, moment, durée, précautions) · 17 chirurgie et opérations · 18 matériel · 19 lieux, services et parcours de soins |
| D. Mode de vie | 20 alimentation et régime · 21 hygiène et prévention · 22 activité, sommeil et mode de vie · 23 grossesse, enfant et santé sexuelle · 24 handicap et aides techniques |
| E. Contexte | 25 vie quotidienne (maison, travail, déplacements, météo, argent) · 26 temps, fréquence, durée · 27 nombres et mesures · 28 couleurs, aspect et sensations · 29 urgence · 30 droits, consentement et données |

Trois formes d'entrée :

- `fr|en` : une notion simple, cherchée telle quelle ;
- `fr|en|formes fr/…|formes en/…` : formes supplémentaires cherchées dans les bases. Par exemple `asseyez-vous|sit down|s'asseoir/assis|sit` : les bases nomment l'action à l'infinitif ;
- `fr|en|=ID+ID+…` : **notion composée**, exprimée par une suite de pictogrammes. Par exemple `où avez-vous mal` = `OU+AVOIR_MAL`, `sans sel` = `NE_PAS+SEL`, `après le repas` = `APRES+REPAS`. Il y en a environ 200 : questions, réassurance, conseils, déclencheurs de la douleur, posologie, régime.

## Niveaux de vérification des liens

- `verifie_web_2026-11-02` / `verifie_web_2026-11-04` : le lien a été vu en recherche à cette date (46 documents).
- `a_confirmer` : adresse officielle connue, à confirmer au premier téléchargement (39 documents). Si elle a changé, le script cherche le PDF dans la page officielle (`page`), sinon le document passe dans `a_telecharger_a_la_main.md`.
- `manuel` : aucun texte officiel ouvert trouvé (2 documents : loi 2024/017 sur les données personnelles, stratégie nationale d'IA). Ce sont des **lacunes documentées** ; déposer le PDF officiel dans `entrees_manuelles/<ID>.pdf` dès qu'il est obtenu.

## Règles

- Uniquement des documents officiels (Journal officiel, ministères, ONU, OMS, UNESCO, UA, OCDE, Conseil de l'Europe…) ou leurs copies hébergées par une organisation internationale. Les copies sont signalées dans `note`. Jamais de presse ni de blog.
- Une exigence sans document camerounais apparaît comme lacune dans `matrice_exigences.md` : on la documente, on ne l'invente pas.
- Pictogrammes : ARASAAC (CC BY-NC-SA, non commercial), Mulberry (CC BY-SA 2.0 UK), OpenMoji (CC BY-SA 4.0). SantéBD reste exclue sans accord écrit ; Tawasol demande un identifiant d'application (variable d'environnement, jamais dans le dépôt).
