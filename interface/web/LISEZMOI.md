# Interface React de MEDIMCOM IA

Trois écrans dans une seule application : accueil (`/`), écran patient (`/patient`, tablette) et écran médecin (`/medecin?jeton=…`).
Le serveur Python (`interface/serveur.py`) sert la version compilée `dist/` et l'API ; rien ne part sur Internet
(polices IBM Plex Sans et IBM Plex Sans Arabic incluses).

## Utiliser (aucune installation)

```bash
python interface/serveur.py --demo scenarios/grossesse.json
```

## Modifier les écrans

```bash
cd interface/web
npm install          # une seule fois (Node 18 ou plus)
npm run dev          # http://localhost:5173 ; lancer en parallèle : python interface/serveur.py
npm run build        # met à jour dist/, servi par le serveur Python
```

En développement, ouvrir `http://localhost:5173/medecin?jeton=…` avec le jeton affiché par le serveur Python.

| Fichier | Rôle |
|---|---|
| `src/api.ts` | types des données et appels à l'API (jeton du médecin, règles de combinaison identiques au serveur) |
| `src/ui.tsx` | composants communs : boutons, pastilles de statut, pictogrammes, champs, boîte de dialogue, notifications |
| `src/Medecin.tsx` | écran médecin : dossier patient, conversation avec validation des traductions, panneau des agents |
| `src/Patient.tsx` | écran patient : message reçu, catégories, grille, plateau de réponse, combiner, urgence, langues |
| `src/Accueil.tsx` · `src/Marque.tsx` | page d'accueil, logo |
| `tailwind.config.js` | jetons de design : couleurs (neutres, bleu d'action, couleurs des verdicts du juriste), ombres, animations |

Les identifiants des éléments (`#message`, `#envoyerMessage`, `button[data-valider]`, `button[data-picto]`, `#combiner`, `#urgence`…)
sont utilisés par le test navigateur (`tests/test_noyau.py`) : les garder en modifiant les écrans.
Sécurité : la page est servie avec une politique de contenu stricte (aucun script en ligne ni externe) et sans
transmission de l'adresse (le jeton du médecin ne fuit pas dans les liens).
