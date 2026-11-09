# Fiche de données — jeux d'entraînement MEDIMCOM IA

Générée le 2026-11-07 par `outils/constituer_base_v2.py`. Partition stable 80 / 10 / 10 (champ `split`),
calculée sur l'empreinte de l'identifiant : relancer le script ne fait pas passer un exemple d'une partition à l'autre.

| Jeu | Exemples | Origine | Réel ou synthétique | Usage visé | Licence |
|---|---|---|---|---|---|
| `pictogrammes_images.jsonl` (+ `../02_pictogrammes/metadata.jsonl`) | 19868 | ARASAAC, Mulberry, OpenMoji | réel (images officielles des bases) | classification d'images, modèle image-texte (CLIP), recherche de pictogramme | par image (`licence`) ; ARASAAC et donc le jeu : **non commercial**, partage à l'identique |
| `phrases_pictogrammes.jsonl` | 3903 | gabarits sur le vocabulaire de consultation | **synthétique**, à relire | traduction pictogrammes ⇄ texte (agent traducteur) | celle des images citées |
| `juridique_classification.jsonl` | 6201 | articles des textes officiels téléchargés | réel ; étiquettes **faibles** (niveau document) | classer un article par juridiction, exigence, thème | textes officiels (domaine public ou conditions de l'éditeur) |
| `juridique_recherche.jsonl` | 18 | dispositions du juriste (`kb/fiches.jsonl`) rapprochées des articles | réel (paires vérifiées par numéro d'article) | entraîner / évaluer le moteur de recherche du juriste | idem |
| `references_qr.jsonl` | 465 | fiches d'information de l'OMS (fr, en, ar) | réel (réponse = texte OMS) ; question par gabarit | assistant médical : réponses de référence, évaluation RAG | © OMS, non commercial |
| `lexique_traduction.jsonl` | 1287 | vocabulaire MEDIMCOM + Wikidata | réel ; rapprochement Wikidata automatique | traduction fr / en / ar, synonymes, codes CIM-10 | CC0 (Wikidata) |
| `../04_jeu_de_donnees_assistant/` | 300 cas | présentations cliniques du projet | **synthétique** | conversations d'entraînement de l'assistant | à faire valider par un médecin |

## Usages interdits
- Diagnostiquer ou prescrire sans médecin : MEDIMCOM aide à communiquer, **le médecin décide**.
- Usage commercial des jeux qui contiennent des images ARASAAC ou des textes de l'OMS.
- Présenter les phrases synthétiques comme des propos réels de patients.

## Limites connues
- Les étiquettes juridiques sont faibles : un article hérite des exigences de tout son document.
- Les phrases synthétiques couvrent des formulations simples ; pas de dialectes, peu de négations complexes.
- L'arabe n'est disponible que pour une partie des notions (vocabulaire historique + Wikidata).
- Aucune donnée de patient réel : tout cas clinique est fictif.

## Traçabilité
Chaque document et image a son adresse d'origine, sa date et son empreinte SHA-256 dans `../journal.json`.
