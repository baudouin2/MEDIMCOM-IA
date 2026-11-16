#!/usr/bin/env bash
# MEDIMCOM IA — builds the large knowledge base (base_v2) YOURSELF, inside the project folder (./base_v2).
#
#   bash construire_base.sh                everything: legal texts, WHO references, pictograms, data sets
#   bash construire_base.sh essai          quick trial (few pictogram images): checks that everything works
#   bash construire_base.sh juridique      one step only: juridique, references, pictogrammes, donnees, entrainement
#   bash construire_base.sh -- --documents CM-SANTE-1996     any option of outils/constituer_base_v2.py after "--"
#
# What it builds (details: outils/constituer_base_v2.py):
#   1. legal base: Cameroonian texts first, then UN, WHO, UNESCO, African Union… (download, SHA-256 fingerprint,
#      text extraction, split by article, chunks ready for search);
#   2. medical references (WHO fact sheets fr / en / ar, MedlinePlus);
#   3. consultation pictograms (ARASAAC, Mulberry, OpenMoji, with their licences; ARASAAC: non-commercial use);
#   4. fictitious data sets for the assistant.
# Where: ./base_v2 in the project folder. It is NEVER committed to GitHub (.gitignore: large, own licences).
# Interrupted (Ctrl+C, connection cut, computer asleep)? Run the same command again: it resumes where it stopped,
# nothing already downloaded is downloaded again.
# Documents that cannot be downloaded automatically are listed in base_v2/a_telecharger_a_la_main.md: download
# them by hand, drop each one as base_v2/entrees_manuelles/<ID>.pdf, then run this script again.
# Next step: bash vectoriser.sh   (search by meaning over this base)
set -euo pipefail
cd "$(dirname "$0")"
SORTIE="base_v2"

ARGS=()
case "${1:-tout}" in
  tout|"")   ;;
  essai)     ARGS=(--max-images 60 --objectif-pictos 200 --variantes 3) ;;
  juridique|references|pictogrammes|donnees|entrainement|migration) ARGS=(--etapes "$1") ;;
  --)        ;;
  -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
  *) echo "Unknown choice: $1   (tout, essai, juridique, references, pictogrammes, donnees, entrainement, or -- OPTIONS)"; exit 1 ;;
esac
shift || true
[ "${1:-}" = "--" ] && shift
ARGS+=("$@")

# 1. Same Python environment as lancer_local.sh / vectoriser.sh (.venv in the project folder, created once)
command -v python3 >/dev/null || { echo "Python 3 is required: sudo apt install python3 python3-venv"; exit 1; }
if [ ! -x .venv/bin/python ]; then
  echo "→ Creating the Python environment (once)…"
  python3 -m venv .venv || { echo "Run: sudo apt install python3-venv   then start again."; exit 1; }
  .venv/bin/pip install -q --upgrade pip
fi
.venv/bin/pip install -q pypdf certifi ollama

# 2. Disk space (the full base with images takes a few GB)
LIBRE_GO=$(df -Pk . | awk 'NR==2 {print int($4/1024/1024)}')
echo "→ Free space here: ${LIBRE_GO} GB (the full base needs about 2 to 4 GB)."
[ "$LIBRE_GO" -ge 2 ] || echo "⚠ Little space left: try first  bash construire_base.sh essai"

# 3. Build (resumable)
echo "→ Building the base in $(pwd)/$SORTIE  (keep the computer awake; Ctrl+C then the same command resumes)…"
.venv/bin/python outils/constituer_base_v2.py --sortie "$SORTIE" "${ARGS[@]}"

echo
echo "✔ Base built in ./$SORTIE (not sent to GitHub)."
[ -f "$SORTIE/a_telecharger_a_la_main.md" ] && echo "  To finish by hand (documents the script could not download): $SORTIE/a_telecharger_a_la_main.md"
echo "  Next step: bash vectoriser.sh     then: bash lancer_demo.sh   (the application finds ./$SORTIE by itself)"
