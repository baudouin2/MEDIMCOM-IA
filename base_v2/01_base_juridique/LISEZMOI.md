# Base juridique

87 documents officiels et ouverts, rangés par juridiction puis par exigence du hackathon. 59 obtenus ; 8921 morceaux indexables dans `corpus_rag.jsonl`.

- `matrice_exigences.md` : quelles exigences sont couvertes, et les lacunes.
- `index_sources.csv` : un document par ligne (ouvrable dans un tableur).
- `corpus_rag.jsonl` : morceaux `{id, text, metadata}` pour la base vectorielle (`medimcom/vecteurs.py`).
- Chaque document : `<dossier>/<ID>/fiche.md`, `texte.md`, `articles.jsonl`, `original.pdf|html`.

## Arborescence

- `A_cameroun/` — Cameroun (pays d'application)
  - `01_lois_reglementations_sante/` (8 documents)
  - `02_strategies_ia_numerique_cybersecurite/` (10 documents)
  - `03_protection_donnees/` (1 documents)
  - `04_mandats_institutionnels/` (11 documents)
  - `05_handicap_inclusion/` (4 documents)
- `B_international/` — International (ONU, OMS, UNESCO, OCDE, Conseil de l'Europe, normes)
  - `01_onu_droits_humains/` (8 documents)
  - `02_ia_ethique_gouvernance/` (9 documents)
  - `03_oms_sante_numerique/` (6 documents)
  - `04_handicap_accessibilite/` (2 documents)
  - `05_protection_donnees/` (3 documents)
  - `06_ethique_medicale/` (3 documents)
  - `07_normes_uit/` (2 documents)
- `C_afrique_regional/` — Afrique (Union africaine)
  - `01_numerique_donnees/` (3 documents)
  - `02_ia/` (1 documents)
  - `03_droits_handicap/` (2 documents)
- `D_emirats_pays_hote/` — Émirats arabes unis (pays hôte du hackathon)
