# Contrat d'interface — Agent 1 (traducteur texte ⇄ pictogrammes)

Pour le coéquipier qui développe le modèle de pictogrammes. L'agent 1 est **déjà branché** dans le système (`medimcom/agents.py`, classe `Traducteur`) avec un moteur de démonstration par dictionnaire (`medimcom/pictogrammes.py`, classe `LexiquePictogrammes`). Ton travail : **remplacer ce moteur par le tien**, sans toucher au reste.

## 1. Ce que ton moteur doit fournir

Une classe Python **importable** (son dossier doit être dans le `PYTHONPATH`, ou à la racine du projet) et **constructible sans argument** (`MonModele()` ; charger les poids dans `__init__`), avec deux méthodes :

```python
class MonModele:
    def traduire(self, texte: str) -> dict:
        # texte du médecin ou de l'assistant, en français
        return {
            "pictogrammes": ["VOUS", "ENCEINTE", "QUESTION"],   # identifiants, dans l'ordre de lecture
            "non_traduits": [],                                  # mots que tu n'as pas su traduire (jamais inventer)
            "couverture": 1.0,                                   # part des mots traduits, entre 0 et 1
        }

    def interpreter(self, pictogrammes: list[str]) -> str:
        # pictogrammes choisis par le patient -> phrase simple en français pour le médecin
        return "oui"
```

Règles sur les identifiants :

- un identifiant par pictogramme, en MAJUSCULES : `DOULEUR`, `VENTRE`, `MATIN`, `OUI`, `NON`, `QUESTION`… ;
- les éléments variables utilisent `TYPE:valeur` : `MEDICAMENT:paracetamol`, `CHIFFRE:3`, `DOSE:500mg` ;
- `OUI` et `NON` doivent exister : un `OUI` ou un `NON` **seul**, en réponse à une question fermée (grossesse, urgence, accord…), devient un fait du dossier (par exemple `grossesse = vrai`) ; toute autre réponse est rapportée en texte seulement ;
- **une négation ne doit jamais disparaître** (« Ne prenez pas… ») : la démonstration utilise `NE_PAS` ; à défaut, mettre le mot dans `non_traduits` ;
- les doses gardent leur unité (`DOSE:500mg`) ;
- **images combinées** : `TETE+DOULEUR` forme UNE image (le premier pictogramme en grand, les suivants en médaillon, 3 au plus). Le lexique de démonstration combine automatiquement partie du corps + douleur (ou sang) ; ton moteur peut en produire d'autres. `NE_PAS`, `MAXIMUM`, `URGENCE` et `STOP` ne sont **jamais** combinés : ils restent des pictogrammes entiers ;
- si ton modèle **génère** des images, utilise des identifiants `GEN:nom` et ajoute à ta classe une méthode `image(self, ident) -> str` qui renvoie le SVG. Il est accepté seulement s'il s'agit d'un SVG autonome, sans script ni lien externe ; sinon il s'affiche « ? ». Une image `GEN:` n'est jamais combinée.

L'agent 1 peut aussi **choisir lui-même** ses pictogrammes (argument `pictogrammes` de `proposer_au_medecin`), par exemple pour combiner ou utiliser une image `GEN:`. Il ne peut jamais retirer de la traduction une négation, une limite, une dose, un chiffre ou un nom de médicament (refus testé), et le médecin valide toujours l'image avant l'envoi.

## 2. Comment le brancher

```bash
python main.py --pictogrammes mon_paquet.mon_module:MonModele
```

ou dans le code : `ctx.pictogrammeur = MonModele()`. Aucun autre fichier à modifier.

## 3. Ce que fait l'agent 1 (déjà codé)

| Il décide seul de… | Outil |
|---|---|
| traduire une question de l'assistant (ex. « Êtes-vous enceinte ? ») | `proposer_au_medecin` |
| expliquer une prescription jugée conforme, avec la question d'accord (consentement) | `proposer_au_medecin` |
| prévenir le médecin quand des mots n'ont pas de pictogramme | `envoyer_message` |
| rapporter la réponse du patient (exactement les pictogrammes qu'il a choisis) dans le dossier | `rapporter_reponse_patient` |
| envoyer un message validé et jugé conforme | `envoyer_au_patient` |

## 4. Garde-fous (non négociables, testés)

1. Toute proposition reste en `attente_validation` jusqu'à la **validation du médecin**.
2. Après validation, le **juriste** contrôle (le validateur doit être un médecin inscrit et actif).
3. `envoyer_au_patient` **refuse** tout message qui n'est pas validé **et** jugé `CONFORME`, ou qui explique une prescription devenue non conforme entre-temps.
4. `rapporter_reponse_patient` **refuse** des pictogrammes que le patient n'a pas envoyés.
5. Un mot non traduit est signalé au médecin, pas inventé (vérifié par le test du contrat). Ne pas ajouter d'information médicale absente du texte d'origine est une consigne de l'agent, contrôlée par la validation du médecin.

Flux : assistant → question → **agent 1 propose** → médecin valide → juriste contrôle → **agent 1 envoie** → patient répond en pictogrammes → **agent 1 rapporte** → assistant met à jour l'état → juriste revérifie.

## 5. Événements de scénario utiles pour tes tests

```json
{"type": "validation", "auteur": "medecin", "medecin": "DR-001", "contenu_type": "question"}
{"type": "reponse_patient", "pictogrammes": ["OUI"]}
```

## 6. Avant de dire « c'est branché »

```bash
# Linux / macOS
MEDIMCOM_PICTOGRAMMES=mon_paquet.mon_module:MonModele python -m pytest -q
# Windows (PowerShell)
$env:MEDIMCOM_PICTOGRAMMES="mon_paquet.mon_module:MonModele"; python -m pytest -q

python main.py --pictogrammes mon_paquet.mon_module:MonModele
```

Le test `test_moteur_pictogrammes_respecte_le_contrat` vérifie ton moteur (format, identifiants en majuscules avant les deux-points, mots inconnus non inventés, négation conservée) ; les autres tests vérifient que le système complet fonctionne toujours.

Vérifier dans la sortie : « Proposition #… soumise au médecin : … » avec tes pictogrammes, puis « Message #… envoyé au patient ». Pour la validation des pictogrammes avec des personnes sourdes, suivre la méthode de test de compréhension ISO 9186-1 (lacune L05 du rapport).
