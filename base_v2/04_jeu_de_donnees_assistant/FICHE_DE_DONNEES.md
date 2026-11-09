# Fiche de données — assistant MEDIMCOM IA (agent 3)

Générée le 2026-11-04 par `outils/jeu_assistant.py` (graine 2026, 30 variantes par présentation).

## Ce que contient le jeu
- 300 cas **fictifs** issus de 10 présentations cliniques (`donnees/presentations_cliniques.json`) : douleur abdominale, fièvre et toux, mal de tête, douleur à la poitrine, diarrhée, démangeaisons, boutons, vertiges, malaise, mal de gorge, femme enceinte qui a mal à la tête ou gonfle, fièvre.
- Répartition : entraînement 240, validation 30, test 30 (par variante : les mêmes présentations dans chaque partie).
- Pays alternés : Émirats (AE) et Cameroun (CM). Le contexte du pays ajoute des pistes (paludisme au Cameroun, par exemple).
- Entrée : âge, sexe, ce qui est déjà connu, message du patient en pictogrammes. Sortie attendue : questions complémentaires (avec pictogrammes), signes d'alerte présents, orientation, pistes à évoquer, rappel.

## Comment les réponses sont calculées
Par des règles explicites (`outils/jeu_assistant.py`, fonction `reponse_attendue`) :
- on demande ce qui manque, en commençant par les signes d'alerte ;
- un signe d'alerte présent ou une douleur à 7/10 ou plus donne l'orientation « urgence » ;
- une piste est écartée si une information connue la contredit ; elle est « à confirmer » si l'information manque.
Corriger une règle ou une présentation, puis relancer le script : tout le jeu est régénéré.

## Limites, à dire franchement
- Contenu de médecine générale rédigé pour le prototype : **à valider par un médecin** avant tout entraînement (`a_valider_par_medecin.csv`).
- Cas générés par règles : peu de variété de formulation ; à compléter par des cas rédigés par des médecins (toujours fictifs).
- Aucune donnée de patient réel. Ne jamais y ajouter de données réelles sans cadre légal et éthique.
- Le modèle entraîné propose des pistes au médecin ; il ne pose pas de diagnostic et ne s'adresse jamais au patient.

## Usage
- Évaluer un modèle tel quel (sans entraînement) sur `sft_test.jsonl` : comparer ses questions et ses alertes à la sortie attendue.
- Ajuster un petit modèle local (par exemple qwen3:8b) sur `sft_entrainement.jsonl`, en gardant `sft_validation.jsonl` pour régler l'entraînement.
