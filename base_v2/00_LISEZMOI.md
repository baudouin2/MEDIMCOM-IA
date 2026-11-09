# Base de connaissances MEDIMCOM IA — version 2

Constituée le 2026-11-07 par `outils/constituer_base_v2.py`. Rangée selon les exigences du hackathon UIT AI for Good :
lois et réglementations, stratégies IA / numérique / cybersécurité, protection des données, mandats institutionnels,
engagements multilatéraux, énergie et infrastructures.

| Dossier | Contenu |
|---|---|
| `01_base_juridique/` | — documents officiels obtenus sur — (Cameroun d'abord, puis ONU, OMS, UNESCO, OCDE, Conseil de l'Europe, Union africaine, pays hôte) ; — morceaux pour la recherche. Commencer par `matrice_exigences.md` |
| `02_pictogrammes/` | 19868 pictogrammes de consultation, 1052 notions illustrées ; `planches/index.html` |
| `03_references_medicales/` | fiches d'information de l'OMS en français, anglais et arabe, résumés MedlinePlus, lexique Wikidata fr / en / ar avec codes CIM-10 (— pages OMS) |
| `04_jeu_de_donnees_assistant/` | cas cas fictifs pour l'assistant médical, à faire valider par un médecin |
| `05_jeux_entrainement/` | jeux prêts pour entraîner ou évaluer un modèle (images ⇄ libellés, pictogrammes ⇄ phrases, classification et recherche juridiques, questions-réponses OMS, lexique) ; lire `FICHE_DE_DONNEES.md` |
| `entrees_manuelles/` | déposer ici `<ID>.pdf` pour les documents à télécharger à la main |
| `a_telecharger_a_la_main.md` | la liste de ces documents, avec les liens où les chercher |
| `journal.json` | chaque document et image : adresse, date, empreinte SHA-256 (auditabilité) |

**Règles.** Uniquement des documents officiels et ouverts, jamais de presse ; une lacune se documente, elle ne s'invente pas.
Pictogrammes : attribution obligatoire (`02_pictogrammes/LICENCES.md`), ARASAAC non commercial. Données de patients : fictives uniquement.

Relancer le script complète la base sans rien retélécharger.
