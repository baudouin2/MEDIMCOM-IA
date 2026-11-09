# Pictogrammes de consultation médicale

19868 images rangées en 34 catégories de consultation ; 1052 notions sur 1287 illustrées (dont 201 notions composées : une suite de pictogrammes, par exemple « où avez-vous mal » = OÙ + AVOIR MAL). Objectif de volume : 3000 (atteint).

Élargissement : tout le catalogue ARASAAC : +9483.

| Catégorie | Images |
|---|---|
| `01_accueil_politesse/` Accueil, politesse, présentation | 41 |
| `02_reponses_accord/` Réponses, accord, refus | 25 |
| `03_questions/` Questions | 26 |
| `04_comprehension_communication/` Comprendre et se faire comprendre | 1826 |
| `05_reassurance_soutien/` Rassurer et soutenir | 46 |
| `06_consignes_examen/` Consignes pendant l'examen | 181 |
| `07_conseils_recommandations/` Conseils et recommandations | 43 |
| `08_personnes_soignants/` Personnes, soignants et entourage | 250 |
| `09_corps_anatomie/` Corps et anatomie | 682 |
| `10_localisation_position/` Localisation et position | 93 |
| `11_douleur_description/` Décrire une douleur | 75 |
| `12_symptomes/` Symptômes | 190 |
| `13_maladies_antecedents/` Maladies et antécédents | 71 |
| `14_emotions_ressenti/` Émotions et ressenti | 307 |
| `15_examens_actes/` Examens et actes de soin | 372 |
| `16_medicaments_posologie/` Médicaments et posologie | 553 |
| `17_chirurgie_operations/` Chirurgie et opérations | 30 |
| `18_materiel_medical/` Matériel médical | 154 |
| `19_lieux_services_parcours/` Lieux, services et parcours de soins | 186 |
| `20_alimentation_regime/` Alimentation et régime | 1361 |
| `21_hygiene_prevention/` Hygiène et prévention | 284 |
| `22_activite_sommeil_mode_de_vie/` Activité, sommeil et mode de vie | 100 |
| `23_grossesse_enfant_sexualite/` Grossesse, enfant et santé sexuelle | 29 |
| `24_handicap_aides/` Handicap et aides techniques | 99 |
| `25_vie_quotidienne_contexte/` Vie quotidienne et contexte | 512 |
| `26_temps_frequence_duree/` Temps, fréquence et durée | 436 |
| `27_nombres_quantites_mesures/` Nombres, quantités et mesures | 204 |
| `28_couleurs_aspect_sensations/` Couleurs, aspect et sensations | 113 |
| `29_urgence_securite/` Urgence et sécurité | 141 |
| `30_droits_consentement_donnees/` Droits, consentement et données | 70 |
| `90_vocabulaire_general/` Vocabulaire général (tous domaines) | 9136 |
| `91_emojis_symboles/` Émojis et symboles (OpenMoji) | 2019 |
| `98_sensible/` Contenus sensibles (sexualité, violence) — recherche seulement | 171 |
| `99_sante_divers/` Santé — divers (à trier) | 42 |

- `catalogue.csv` / `catalogue.jsonl` : chaque image, ses mots-clés fr/en, ses notions, sa licence.
- `notions.csv` : chaque notion du vocabulaire et ses images (c'est ce que lit l'agent traducteur).
- `planches/index.html` : tout voir dans le navigateur.
- `audit/rejets.csv` : ce qui a été écarté et pourquoi ; `audit/notions_sans_image.csv` : notions à illustrer.
- `LICENCES.md` : attribution obligatoire par source.

Tri : `kb/corpus/filtres_pictogrammes.json` ; vocabulaire : `kb/corpus/vocabulaire_consultation.json`. Lancer `--audit-pictos` pour voir les étiquettes ARASAAC et ajuster les listes.
