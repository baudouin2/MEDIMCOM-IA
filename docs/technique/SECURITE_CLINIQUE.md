# Sécurité clinique des prescriptions

Ce que le juriste et l'assistant vérifient sur chaque prescription, avec quelles sources, et ce qui n'est pas couvert.

## Principe

1. **Le juriste** applique des règles écrites, chacune rattachée à une citation exacte d'une notice officielle
   (`kb/fiches.jsonl`, sources dans `kb/sources.json`, rôle `clinical_reference`).
2. **Il rapproche la prescription de la fiche du patient** : âge, sexe, grossesse, poids, allergies, traitements en cours,
   antécédents (texte libre, lu par `medimcom/faits.py` : maladie des reins, du foie, ulcère, anticoagulant, maladie du cœur).
3. **Il lit la dose et le rythme** (`medimcom/regles.py`, `lire_dose`) : « 50 mg » × « 3 fois par jour » = 150 mg/j ; il lit
   aussi « 7fois parjours », « 3x/j », « toutes les 6 h », « matin et soir ».
4. **L'assistant** (veille déterministe, sans modèle) explique au médecin pourquoi ne pas prescrire en l'état et propose une
   alternative sourcée, **après l'avoir fait contrôler par le moteur du juriste pour ce patient**.
5. Rien n'est expliqué au patient tant que la prescription n'est pas conforme (ou maintenue par le médecin, nominativement).

## Niveaux

| Situation | Verdict | Qui peut passer outre |
|---|---|---|
| Contre-indication d'une notice (référence étrangère, non contraignante aux Émirats) | À REVOIR | le médecin, en le justifiant (nom enregistré) |
| Au-delà de la dose maximale par jour | À REVOIR | le médecin, en le justifiant |
| Plus du double de la dose maximale, ou unité impossible (« 1 kg ») | BLOQUÉ (garde-fou de sûreté) | personne |
| Dose ou rythme illisible, fiche incomplète (grossesse, allergies, traitements) | Information manquante | — compléter |
| Antécédents non renseignés | Information (rappel) | — |

Les antécédents sont en **monde fermé** : une maladie qui n'est pas écrite dans la fiche est supposée absente. C'est pourquoi le
juriste rappelle de remplir « Maladies connues, antécédents » (même « aucun ») avant un médicament concerné. La grossesse,
elle, reste en monde ouvert : non renseignée chez une femme de 12 à 50 ans, elle doit être demandée.

## Médicaments couverts

| Médicament | Règles | Sources (citation exacte dans `kb/fiches.jsonl`) |
|---|---|---|
| Tramadol | grossesse ; moins de 12 ans ; mineur ; 400 mg/j | Notice FDA (DailyMed, 3/2021) |
| Paracétamol | maladie du foie ; anticoagulant (surveiller l'INR) ; 4 000 mg/j | Étiquette OTC FDA (copie NDC List) |
| Ibuprofène | grossesse (20 semaines, 3 derniers mois) ; ulcère ; anticoagulant ; reins ; cœur ; après 60 ans ; 3 200 mg/j | FDA 2020, étiquettes OTC et Rx |
| Aspirine | moins de 18 ans (syndrome de Reye) ; grossesse ; ulcère ; anticoagulant ; 3 900 mg/j | Étiquette OTC FDA (copie NDC List) |
| Amoxicilline | allergie aux pénicillines / bêta-lactamines ; insuffisance rénale sévère (pas de 875 mg) | Notice FDA (DailyMed, 01/2024) |
| Metformine | maladie des reins (DFG) ; foie ; 2 550 mg/j adulte, 2 000 mg/j enfant | Notice FDA (DailyMed, 6/2026) |
| Misoprostol | grossesse | Notice Cytotec (FDA) |

Les notices DailyMed sont aussi téléchargées dans `base_v2` (dossier `B_international/09_securite_medicaments`) pour que les
agents puissent en citer les passages : `python outils/constituer_base_v2.py --sortie base_v2 --etapes juridique`
(les documents déjà présents ne sont pas retéléchargés).

## Limites (à dire au jury)

- **Références étrangères** : ce sont des notices américaines. Un déploiement aux Émirats doit les remplacer par les notices
  de l'Emirates Drug Establishment et le formulaire national ; au Cameroun, par la liste nationale des médicaments essentiels.
- **Couverture** : sept médicaments. Les autres n'ont que les contrôles généraux (dose lisible, fiche complète, allergie
  déclarée au nom du produit). Il n'y a pas de base d'interactions médicamenteuses complète.
- **Pas de calcul au poids** pour l'enfant (mg/kg), sauf la dose maximale de la metformine chez l'enfant.
- **Trois étiquettes** (paracétamol, ibuprofène, aspirine) viennent d'une copie fidèle du texte FDA (NDC List, MedLibrary),
  marquées `secondary_source` : à vérifier sur DailyMed.
- Règles cliniques d'exemple : **à valider par un médecin et un pharmacien** avant tout usage réel.
