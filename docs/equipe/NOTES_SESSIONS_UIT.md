# Ce qu'ont dit les organisateurs (sessions de suivi UIT)

Notes tirées des enregistrements d'écran des sessions Zoom du hackathon (sous-titres en direct relus automatiquement, diapositives et pages montrées à l'écran). Mise à jour du 21 octobre 2026.

**Couverture : partielle.** Seules les fins de 9 enregistrements sur 11 ont pu être lues (les morceaux de plus de 20 Mo ne passent pas). Le reste sera ajouté quand les versions légères (`alleger_videos.sh`) seront déposées dans le projet.

## 1. Critères d'évaluation (page d'un hackathon UIT précédent, montrée en séance comme modèle)

Les cas d'usage sont évalués sur :

1. une **description claire du cas d'usage selon le pipeline d'apprentissage automatique UIT-T Y.3172** ;
2. une **correspondance claire avec les facteurs et dimensions du cadre UIT de préparation à l'IA** (AI Readiness) ;
3. la **contribution à la base de connaissances**, relue par des experts de l'UIT ;
4. les **apports aux stratégies et politiques d'IA**, relus par des décideurs.

Note de la page : *les participants doivent fournir les liens de référence des documents proposés à la base de connaissances.*

→ **Fait :** le fichier `docs/soumission/KB_reference_links.md` donne les 36 sources avec leur lien officiel. Il est généré avec le rapport.

## 2. Comment décrire le cas d'usage (mentor, explication du pipeline Y.3172)

- Pour **chaque nœud** (SRC source, C collecteur, PP prétraitement, M modèle, P politique, D distribution, SINK), il faut dire concrètement **quelles données, sous quel format, avec quelles métadonnées, recueillies comment** (capteurs, caméra, son, valeurs numériques…).
- Il faut éviter le vague : le mentor a cité comme mauvais exemple « les données viennent de l'école ».
- Il a montré un **tableau modèle à 4 colonnes** : nœud · élément du cas d'usage · documents qui l'encadrent (politiques, stratégies, réglementations) · préparation à l'IA (dimensions / mesures). Son exemple (classe intelligente) :
  - SRC : stylets ;
  - C : serveur local dans l'école ;
  - PP : anonymisation avant envoi au modèle ;
  - P : relecture humaine des résultats (« human-in-the-loop », conditions pour passer outre).

→ **Fait :** la section 8 du rapport suit maintenant exactement ce format, avec les données concrètes de MEDIMCOM à chaque nœud.

## 3. Cadre UIT de préparation à l'IA, version 2.0

Il a été présenté le 17 octobre 2026 : *AI Ready – Analysis Towards a Standardized Readiness Framework*, Report 2.0, janvier 2026.

- **6 facteurs :** données, recherche, soutien au déploiement, normes, code ouvert, bacs à sable.
- **13 dimensions**, chacune avec des mesures. Pour nous, les plus utiles :
  - D11 *AI for inclusion* : son texte cite explicitement l'IA générative pour les **langues des signes** ;
  - D6 *Human interface* ;
  - D10 *AI and policies* : politiques testées en bac à sable, souveraineté des données ;
  - D8 *Collaboration with AI* ;
  - D13 *Digital infrastructure*.

→ **Fait :**
- source `ITU-AIR-2026` et 5 fiches ajoutées à la base (36 sources, 109 fiches) ;
- 2 questions de test ajoutées ;
- le rapport relie chaque nœud à un facteur · une dimension → une mesure.

Le rapport citait avant des « axes » de la version préliminaire de 2024.

## 4. Questions fréquentes (page du hackathon)

| Question | Réponse des organisateurs | Pour nous |
|---|---|---|
| Comment concevoir les scénarios d'évaluation ? | Ils doivent refléter le rôle **technique et politique** ; mieux vaut des scénarios où des **lacunes politiques** apparaissent | Déjà le cas : `scenarios/crise.json`, 9 lacunes |
| Faut-il mettre tout le code sur GitHub ? | On peut ne publier que la partie essentielle, mais **cela peut influencer la décision des juges** | Tout publier (sauf `archives/`) |
| Certificats ? | Seulement pour les équipes qui ont soumis une **solution valide** | Rendre à temps et complet |
| Et après le hackathon ? | Présenter la solution dans d'autres activités AI for Good ; **proposer les lacunes de normes aux commissions d'études de l'UIT** ; écrire un article pour **ITU Kaleidoscope** ; publier code et modèles en open source | Nos 9 lacunes et le contrat de l'agent 1 sont de bons points de départ |

## 5. Autres points entendus

- Les participants peuvent présenter en **privé** les détails de conception qu'ils ne veulent pas rendre publics.
- Des groupes AI for Good par pays peuvent être créés à la demande (exemples cités : Rwanda, RD Congo). On peut demander un groupe **Cameroun**.
- Une équipe a demandé des outils open source d'évaluation de sécurité et de gestion des accès. Le mentor UIT (Vishnu Ram OV) propose d'en discuter au cas par cas : on peut lui poser nos questions sur le stockage local des données de santé.
- Prochaine séance : **24 octobre 2026** (« Séance 4 », inscription sur la page de l'événement).

## 6. Ce qui reste à lire

| Enregistrement | Contenu repéré | État |
|---|---|---|
| BSMB9246 | Page de l'événement (calendrier, séances) | fin lue |
| CGNT4436 | Rediffusion d'une séance (1 h 07) ; critères d'évaluation | fin lue |
| DHXW6084 | Questions-réponses avec le mentor UIT | fin lue |
| FFSI1471 | Fin de séance, questions des équipes | fin lue |
| FPUC3865 | Explication du pipeline Y.3172 et du rapport technique | fin lue |
| HIQJ8983 | Cadre de préparation à l'IA (dimension 3), retours sur des soumissions | fin lue |
| KBPZ6014, SWQF2929 | Questions fréquentes | fin lue |
| SYXY0463 | Exemple de tableau Y.3172 × préparation à l'IA | fin lue |
| PQMK5517, TLIU2958 | inconnu | à lire (fichiers trop gros) |
