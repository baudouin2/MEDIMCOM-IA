# Base de pictogrammes médicaux (bases existantes)

Le prototype affiche les pictogrammes des **bases existantes** dès qu'ils sont installés ici. Sinon, il affiche ses icônes de démonstration. Un mot sans image n'est jamais remplacé par une image inventée : il est signalé au médecin.

| Fichier | Rôle |
|---|---|
| `vocabulaire_medical.json` | Les 91 notions utiles en consultation (46 de base + 45 médicales : corps, symptômes, ressenti, soins, personnes), avec leurs libellés fr / en / ar (arabe à faire relire) et les mots à chercher dans les bases |
| `bases.json` | Les bases autorisées, leur licence, l'attribution obligatoire, et les conditions (SantéBD bloquée sans accord écrit) |
| `telecharger_arasaac.py` | Recherche automatique dans ARASAAC (Internet requis), 6 candidats par notion, téléchargement de l'image retenue |
| `choix_arasaac.json` | Les choix de l'équipe quand le premier candidat ne convient pas (`{"GORGE": 12345}`) |
| `importer_fichiers.py` | Ajoute les images déposées à la main (Tawasol, Mulberry, Sclera) dans `images/<base>/<IDENTIFIANT>.png` ou `.svg` |
| `manifeste_externe.json` | Résultat : pour chaque notion, l'image, sa base, son auteur, sa licence et son lien d'origine |
| `planche_candidats.html` | Planche pour comparer les candidats et choisir |

## Mode d'emploi (sur un ordinateur relié à Internet)

```bash
python pictogrammes/bases/telecharger_arasaac.py          # environ 5 minutes pour les 91 notions
# ouvrir pictogrammes/bases/planche_candidats.html, noter les meilleurs numéros dans choix_arasaac.json, puis :
python pictogrammes/bases/telecharger_arasaac.py --ids GORGE DOS   # seulement les notions corrigées
# images arabes / du Golfe (Tawasol) ou autres : déposer les fichiers, puis
python pictogrammes/bases/importer_fichiers.py
python -m pytest -q                                        # tout doit rester vert
```

Ensuite, l'écran patient propose automatiquement les nouvelles notions disponibles, y compris un onglet « ressenti » (peur, inquiétude, tristesse…). Le traducteur les utilise et les combine (gorge + douleur), et la page `/credits` du serveur affiche l'attribution exigée par chaque licence. `MEDIMCOM_PICTOS=demo` revient aux icônes de démonstration.

**Licences.**
- ARASAAC est sous licence CC BY-NC-SA : usage non commercial, citation de l'auteur, et toute image modifiée ou combinée reste sous la même licence.
- Tawasol : la licence est à clarifier avec Mada (le site indique BY-SA dans le texte et BY-NC dans le pied de page).
- SantéBD : il faut un accord écrit de l'éditeur avant tout usage.

Le choix final des pictogrammes revient à l'équipe, puis aux **tests avec des personnes sourdes** (`docs/pictogrammes/PROTOCOLE_TESTS.md`).
