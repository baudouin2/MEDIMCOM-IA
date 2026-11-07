# Répartition du travail et ce qui reste à faire

Équipe **ShifaMiko** (Université de Yaoundé I). Rendu du hackathon AI for Good Lab / Sandbox – Émirats arabes unis : **10 novembre 2026** (rapport de 5 pages, dépôt GitHub, base de connaissances ; vidéo de 7 minutes au plus si l'équipe est présélectionnée).

État au 16 octobre 2026 : **le prototype, la base de connaissances et tous les documents sont prêts**. Ce qui reste est du travail de terrain et de validation, que l'outil ne peut pas faire à la place de l'équipe.

## Qui fait quoi

| Membre | Partie | Fichiers principaux | État |
|---|---|---|---|
| **Baudouin Nkana Bilong** | Coordination · agent 2 (juriste) · base de connaissances · rapport | `kb/` · `medimcom/regles.py` · `medimcom/base.py` · `outils/generer_rapport.py` · `docs/soumission/` | Fait |
| **Franck Ndonkou** | Agents et collaboration : 3 agents, dossier partagé, messagerie, journal, agents institutionnels, évaluation | `medimcom/agents.py` · `dossier.py` · `messagerie.py` · `journal.py` · `orchestrateur.py` · `cerveaux.py` · `evaluation.py` · `mandats.json` · `scenarios/` · `docs/technique/ARCHITECTURE_AGENTS.md` | Fait |
| **Fotsing Engoulou** | Pictogrammes, interface et tests : bibliothèque de pictogrammes, écrans médecin et patient, tests avec des personnes sourdes, vidéo | `medimcom/bibliotheque.py` · `interface/` · `pictogrammes/` · `docs/pictogrammes/` · `docs/video/` | Outils faits ; **tests de terrain et vidéo à faire** |

Chaque partie a été relue par un relecteur indépendant, corrigée, puis relue une seconde fois. Les 87 tests automatiques passent.

## Ce qui reste à faire (par ordre de priorité)

| # | Action | Qui | Quand | Comment |
|---|---|---|---|---|
| 1 | Contacter une association de personnes sourdes et un interprète ; demander au comité d'éthique de la Faculté si une autorisation est nécessaire | Fotsing (+ Baudouin) | semaine du 19 octobre | `docs/pictogrammes/PROTOCOLE_TESTS.md`, sections 1 et 2 |
| 2 | Faire relire les libellés arabes des pictogrammes par un locuteur natif | Fotsing | semaine du 19 octobre | libellés dans `medimcom/bibliotheque.py`, planche `docs/pictogrammes/Planche_pictogrammes.pdf` |
| 3 | Lancer les vrais modèles d'IA en local et mesurer leur capacité | Franck | avant le 31 octobre | `ollama pull qwen3:8b` puis `python evaluer_agents.py --mode ollama --modele qwen3:8b --repetitions 3 --sans-repli` (guide, section 8) |
| 4 | Séance de test 1 (au moins 10 personnes), codage par deux juges, analyse, redessin | Fotsing | semaine du 26 octobre | livret `docs/pictogrammes/Livret_test_pictogrammes.pdf` ; `python pictogrammes/analyse_tests.py reponses.csv` |
| 5 | Faire valider les règles cliniques d'exemple (ibuprofène, misoprostol, allergies) par un médecin | Baudouin | avant le 2 novembre | `kb/regles_uae.json` ; test 3 du protocole |
| 6 | Séance de test 2 (items redessinés, nouvelles personnes) ; mettre les vrais chiffres dans le rapport | Fotsing + Baudouin | semaine du 2 novembre | protocole, section 7 ; `python outils/generer_rapport.py` |
| 7 | Revérifier les sources marquées « secondaires » ou « à confirmer » (dont la résolution 51/2021, la norme IA du DoH) | Baudouin | avant le 7 novembre | `kb/sources.json` (`verification`) ; `python kb/outils/verifier_kb.py` |
| 8 | Créer le dépôt GitHub public, y pousser ce dossier **sans `archives/`**, relire le README anglais | Baudouin | avant le 9 novembre | `.gitignore` exclut déjà `archives/` et `sortie/` |
| 9 | Envoyer le rapport ; si présélection, tourner la vidéo | tous | 10 novembre | `docs/soumission/` ; `docs/video/SCRIPT_VIDEO.md` |

## Règles communes

- **Données fictives uniquement**, jamais de vraies données de santé, et jamais d'envoi vers une IA en ligne.
- Les pictogrammes sont **issus de bases existantes** : noter pour chacun la base d'origine et respecter sa licence (attribution).
- **Le médecin décide toujours** ; les agents traduisent, suggèrent et contrôlent.
- On n'affirme dans le rapport et la vidéo **que ce qui a été mesuré** (tests utilisateurs, vrai modèle).
- Après toute modification : `python -m pytest -q` (doit rester vert), puis régénérer les PDF concernés.
