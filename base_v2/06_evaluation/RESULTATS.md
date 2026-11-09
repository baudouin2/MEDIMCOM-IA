# Évaluation de la base_v2 — 2026-11-07

Traduction : partie « test » des phrases (jamais utilisée pour régler le système). Recherche : toutes les paires (la recherche
BM25 n'apprend rien de ces jeux). Sans IA, sans réseau : reproductible.

| Mesure | Résultat |
|---|---|
| Pictogrammes utilisables | 19925 notions avec image |
| Morceaux indexés pour la recherche | 10393 |
| **Traduction texte → pictogrammes** (385 phrases) | précision 0.893 · rappel 0.871 · F1 0.882 · rappel sur les notions illustrées 0.914 · phrases exactes 0.569 · négations conservées 2/2 |
| **Recherche juridique** (18 requêtes) | bon article au 1er rang 0.167 · dans les 3 premiers 0.167 · dans les 5 premiers 0.167 · MRR 0.172 |
| **Recherche dans les fiches OMS** (465 questions) | 1er rang 0.611 · 3 premiers 0.796 · 5 premiers 0.841 · MRR 0.718 · par langue : fr : 5 premiers 0.74 (150) ; en : 5 premiers 0.842 (177) ; ar : 5 premiers 0.949 (138) |

Limites : les phrases de test sont générées par gabarit (formulations simples) ; les requêtes juridiques viennent des
dispositions du juriste rapprochées des articles par leur numéro ; un 0 signifie souvent que le jeu de test est vide
(document non téléchargé ou pictogrammes manquants) : lire les effectifs.

## Mots-clés, sens ou hybride ?

| Méthode | Juridique : 1er · 5 premiers · MRR | OMS : 1er · 5 premiers · MRR |
|---|---|---|
| Mots-clés (BM25) | 0.167 · 0.167 · 0.172 | 0.611 · 0.841 · 0.718 |
| Sens seul (fastembed-paraphrase-multilingual-minilm-l12-v2) | 0.167 · 0.278 · 0.208 | 0.351 · 0.688 · 0.5 |
| Hybride (RRF) | 0.167 · 0.278 · 0.211 | 0.596 · 0.903 · 0.716 |
