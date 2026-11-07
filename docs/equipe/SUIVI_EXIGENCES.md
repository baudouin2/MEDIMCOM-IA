# Suivi des exigences de l'appel (UIT, AI for Good Lab – Émirats arabes unis)

Mise à jour du 16 octobre 2026. Remplace le tableau du 14 octobre (dans `archives/`), qui concluait « pas encore entièrement ». Pour chaque exigence : où se trouve la preuve dans ce dossier.

## Exigences de l'appel

| # | Exigence | État | Preuve dans le dossier |
|---|---|---|---|
| 1 | Solution d'IA agentique dans un domaine (santé) | Fait | 3 agents autonomes (boucle observer → réfléchir → agir, outils, garde-fous dans les outils) : `medimcom/agents.py`, `docs/technique/ARCHITECTURE_AGENTS.md` |
| 2 | Correspondance avec les documents nationaux du pays hôte | Fait (à revérifier en partie) | 40 sources (dont 30 lues sur le texte officiel), dont les lois fédérales et normes DoH, DHA et MOHAP ; 124 dispositions : `kb/sources.json`, `kb/fiches.jsonl`. 7 sources secondaires et 3 « à confirmer » : action 7 de `REPARTITION.md`. Second pays (Cameroun) : `kb/regles_cm.json`, `--pays CM` |
| 3 | Correspondance avec les bonnes pratiques mondiales | Fait | Exemples ONU (CDPH), OMS, UE (AI Act), FDA, NHS, ISO, UA dans `kb/sources.json` ; chaque lacune a ses exemples mondiaux : `kb/lacunes.json` |
| 4 | Code de référence UIT + base vectorielle hébergée par le laboratoire | Prêt à ingérer | Les 133 morceaux `kb/index/chunks.jsonl` (texte + métadonnées) se chargent dans n'importe quelle base vectorielle ; à ingérer avec le code de l'UIT quand les organisateurs le fournissent |
| 5 | Crédits cloud du bac à sable | À utiliser plus tard | Tout tourne en local sur un portable (argument d'infrastructure légère) ; les crédits serviront à tester de plus grands modèles, avec des données fictives uniquement |
| 6 | Rôle de conseiller politique et juridique | Fait | Mode conseiller du juriste pendant la crise (pouvoirs d'urgence, obligations, lacunes), toujours avec sources : `medimcom/agents.py` (Juriste), `scenarios/crise.json` |
| 7 | Participants institutionnels | Fait | Autorité de santé, hôpital, cellule de crise, chacun avec son mandat et sans accès au dossier du patient : `medimcom/mandats.json` |
| 8 | Coordination entre agents (informations et mandats différents) | Fait | Messagerie typée (demande, information, alerte, proposition, désaccord), dossier partagé versionné, mesure seulement avec une base légale contraignante de son propre mandat : `medimcom/messagerie.py`, `medimcom/dossier.py` |
| 9 | Scénarios d'erreur à événements progressifs et fragmentés | Fait | `scenarios/crise.json` (événements libérés par étapes, chacun à des agents différents), `grossesse.json`, `allergie.json` ; erreurs injectées exprès (module externe, IA hors des Émirats, médicament contrôlé à distance, presse) |
| 10 | Journal d'audit et traces de raisonnement | Fait | Journal chaîné SHA-256 : raisonnement, action, message, verdict, source : `medimcom/journal.py`, `verifier_journal.py`, `exporter_journal.py` |
| 11 | Alignement sur la recommandation UIT-T Y.3172 | Fait | Tableau Y.3172 du rapport (section 8) : `docs/soumission/MEDIMCOM_IA_Technical_Report.pdf` |
| 12 | Cadre UIT de préparation à l'IA (version 2.0 : 6 facteurs, 13 dimensions) | Fait (21 octobre) | Rapport, section 8 : chaque nœud Y.3172 relié à ses documents et à un facteur · une dimension avec sa mesure (format montré par le mentor) ; source `ITU-AIR-2026` dans la base |

## Critères du jury

| Critère | Où le jury le voit |
|---|---|
| Qualité de la base de connaissances | `kb/` ; recherche mesurée sur 65 questions : rappel@3 = 0,94, MRR = 0,87 (`python kb/outils/evaluer_recherche.py`) ; cohérence : `python kb/outils/verifier_kb.py` |
| Capacité des agents dans les scénarios d'erreur | `python evaluer_agents.py` : 6 invariants de sécurité + attendus par scénario ; modèle « chaotique » qui ne casse jamais la sécurité. **À compléter avec un vrai modèle** (action 3) |
| Identification des lacunes | 9 lacunes du domaine avec exemples mondiaux : `docs/soumission/MEDIMCOM_IA_Gap_Analysis.pdf` |
| Traçabilité | Page « Journal lisible » de l'interface ; `python verifier_journal.py sortie/journal.json --falsifier 10` montre qu'une ligne modifiée est détectée |
| Alignement sur les normes de l'UIT | Rapport, section 8 (Y.3172 + cadre 2.0) |
| Solidité et rigueur de génie logiciel | Sémantique formelle des règles, spécification de sûreté et d'utilité, preuves par énumération exhaustive et par solveur SMT (Z3), moniteur de 10 invariants sur le journal, exploration automatique avec attaques, analyse de mutation, intégration continue : `python outils/verifier_formel.py`, `docs/technique/METHODES_FORMELLES.md`, `docs/technique/RAPPORT_VERIFICATION_FORMELLE.md` |

## Livrables du 10 novembre

| Livrable | Fichier | État |
|---|---|---|
| Liens de référence de la base (demandés par les organisateurs) | `docs/soumission/KB_reference_links.md` (généré avec le rapport) | Prêt |
| Rapport technique (5 pages au plus) | `docs/soumission/MEDIMCOM_IA_Technical_Report.pdf` (`python outils/generer_rapport.py`) | Prêt ; mettre à jour avec les résultats des tests et du vrai modèle |
| Analyse des lacunes (annexe) | `docs/soumission/MEDIMCOM_IA_Gap_Analysis.pdf` | Prêt |
| Dépôt GitHub | ce dossier, sans `archives/` | À créer (action 8) |
| Base de connaissances | `kb/` | Prête |
| Vidéo (si présélection) | `docs/video/SCRIPT_VIDEO.md` | Script prêt, tournage à faire |
