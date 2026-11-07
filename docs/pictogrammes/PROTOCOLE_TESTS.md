# Protocole de tests avec des personnes sourdes (partie de Fotsing)

Objectif : savoir, preuves à l'appui, si nos pictogrammes et l'écran patient sont **compris** par des personnes sourdes, y compris celles qui lisent peu, avant de les montrer au jury comme « accessibles ». Tout le matériel est prêt dans le dépôt ; ce qui reste à faire est le travail de terrain.

| Matériel | Où |
|---|---|
| Livret imprimable : consentement en pictogrammes + 46 pictogrammes + 10 messages, ordre tiré au hasard, sans les noms | `docs/pictogrammes/Livret_test_pictogrammes.pdf` (`python pictogrammes/livret.py --pdf`) |
| Clé du livret (item → pictogramme, sens attendu) — **reste chez l'animateur** | `pictogrammes/test/cle_livret.csv` |
| Modèle de fichier de réponses | `pictogrammes/test/reponses_modele.csv` |
| Analyse automatique (taux, intervalle de confiance, accord des juges, décision) | `python pictogrammes/analyse_tests.py reponses.csv` |
| Planche de tous les pictogrammes (fr / en / ar) | `docs/pictogrammes/Planche_pictogrammes.pdf` |
| Écran patient pour le test d'utilisation | `python interface/serveur.py --hote 0.0.0.0` ; ouvrir `/patient` sur la tablette (même Wi-Fi), et l'écran médecin avec le lien privé affiché dans le terminal |

## 1. Qui, combien, avec qui

- **Partenaire** : une association de personnes sourdes, qui aide au recrutement et fournit (ou indique) un **interprète en langue des signes**. Sans interprète, pas de test.
- **Participants** : adultes sourds volontaires ; viser **au moins 20 personnes**, dont une bonne part qui lisent peu (c'est le public visé). C'est un choix de l'équipe : l'analyse signale tout item vu par moins de 10 personnes.
- **Équipe le jour du test** : un animateur (pose les items), l'interprète (traduit et transcrit), un observateur (chronomètre, note les difficultés).
- **Médecin partenaire** : relit les phrases du livret et teste l'écran médecin (section 5).

## 2. Éthique, consentement, données

- **Consentement** expliqué en langue des signes, puis montré en pictogrammes (page 2 du livret) : la personne peut refuser ou **arrêter à tout moment** sans se justifier.
- **Aucune donnée de santé réelle** : on teste la compréhension d'images, pas l'état de santé des participants. Les scénarios sont fictifs.
- **Données recueillies** : un code participant (PART-001…), tranche d'âge, niveau de lecture déclaré (aucun / un peu / bien), usage d'un téléphone. Pas de nom dans les fichiers de réponses ; la liste code ↔ nom (si elle existe) est gardée à part, sous clé.
- **Cadre** : les tests ont lieu au Cameroun, où la loi n° 2024/017 sur la protection des données personnelles s'applique depuis le 23 juin 2026 (fiche `CM-DCP-2024` de la base, à relire). **Demander au comité d'éthique de la Faculté** si une autorisation est nécessaire avant de commencer.
- Défraiement du transport des participants, à prévoir.

## 3. Test 1 — compréhension des pictogrammes (≈ 30 min)

Méthode inspirée de la norme ISO 9186-1 (test de compréhension des symboles graphiques) : la personne voit le symbole **dans un contexte** et dit ce qu'il signifie, **sans choix proposé**. Les détails de la norme (catégories, seuils) n'ont pas encore été lus : à vérifier sur le texte de la norme avant de citer des chiffres.

1. L'animateur **signe** la phrase de contexte écrite en haut de la page (« Vous êtes chez le médecin… Que veut dire cette image ? »).
2. Il montre la page. **Il ne dit jamais le sens**, ne corrige pas, n'encourage pas une réponse.
3. La personne répond en signes ; l'interprète transcrit **mot pour mot** dans la colonne `reponse_transcrite`. « Je ne sais pas » est une réponse normale.
4. Pauses toutes les 15 minutes. L'ordre des pages est le même pour tous (tiré au hasard une fois) ; pour un deuxième groupe, générer un autre ordre : `python pictogrammes/livret.py --pdf --graine 7`.

**Codage** (après la séance, par **deux juges** qui travaillent séparément, avec la clé) :

| Code | Sens |
|---|---|
| C | correct : le sens attendu, ou un sens équivalent pour la consultation |
| P | partiellement correct : l'idée générale sans l'élément important (ex. « ventre » pour « douleur au ventre ») |
| F | faux |
| N | « je ne sais pas », pas de réponse |

Les réponses où les juges ne sont pas d'accord sont listées par l'analyse ; les deux juges se réunissent et écrivent le code retenu dans la colonne `code_consensus`. Sans ce code, la réponse n'est pas comptée (le résultat le signale « À TRANCHER »). Le kappa (accord des juges) peut être bas, voire nul, même quand les juges sont souvent d'accord, si presque toutes les réponses ont le même code : regarder aussi la liste des désaccords.

## 4. Test 2 — utilisation de l'écran patient (≈ 15 min)

Sur une tablette avec l'écran patient (le médecin est joué par l'animateur sur l'écran médecin) :

| Tâche | Réussie si |
|---|---|
| Répondre « oui » à la question affichée | OUI envoyé sans aide |
| Dire « j'ai mal au ventre, fort » | VENTRE + DOULEUR + un chiffre ≥ 7 envoyés |
| Corriger une erreur avant d'envoyer | un pictogramme retiré du plateau |
| Signaler une urgence | bouton rouge puis OUI |
| Lire un message de traitement (paracétamol, matin et soir, 3 jours) | la personne le redit correctement en signes |

Noter pour chaque tâche : réussie seul / avec aide / échec, temps, hésitations. À la fin, trois questions montrées en pictogrammes (COMPRENDRE, ACCORD, QUESTION) avec une échelle de visages (content / moyen / pas content).

## 5. Test 3 — écran médecin (1 à 2 médecins)

Le médecin déroule le scénario de démonstration (`python interface/serveur.py --demo scenarios/grossesse.json`) puis une consultation libre. Recueillir : ce qui est clair, ce qui manque, ce qui ferait gagner ou perdre du temps, et son avis sur les règles médicales d'exemple (ibuprofène, misoprostol, allergies) — à faire valider par écrit.

## 6. Décisions et itération

`python pictogrammes/analyse_tests.py reponses.csv` produit `resultats_tests.md` :

- **accepté** si au moins 80 % de réponses correctes ;
- **à revoir** entre 50 % et 80 % : redessiner en tenant compte des réponses fausses (elles disent ce que les gens voient) ;
- **à remplacer** sous 50 %.

Un item vu par moins de 10 personnes n'a pas de décision ; entre 10 et 19, la décision est marquée **« provisoire »** (l'intervalle de confiance est encore large). Ces seuils sont **un choix de l'équipe**, modifiables (`--seuil-accepte`, `--seuil-revoir`) quand la norme aura été lue. Corriger les dessins dans `medimcom/bibliotheque.py`, régénérer (`python pictogrammes/exporter.py --pdf`), retester les items modifiés avec de **nouveaux** participants.

## 7. Ce qu'on peut affirmer ensuite (rapport, vidéo)

Seulement ce que les résultats montrent : « N personnes sourdes, dont M lisant peu, ont testé 46 pictogrammes ; X sont compris par au moins 80 % d'entre elles ; Y ont été redessinés. » Tant que les tests ne sont pas faits, le rapport dit « à tester » — c'est le cas aujourd'hui.

## 8. Calendrier proposé

| Quand | Quoi |
|---|---|
| Semaine du 19 octobre | Contact de l'association et d'un interprète ; question au comité d'éthique ; relecture des libellés arabes |
| Semaine du 26 octobre | Séance 1 (au moins 10 personnes) ; codage ; analyse ; redessin |
| Semaine du 2 novembre | Séance 2 (items redessinés, nouvelles personnes) ; test de l'écran médecin ; chiffres pour le rapport |
