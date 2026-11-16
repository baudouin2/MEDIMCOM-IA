#!/usr/bin/env bash
# MEDIMCOM IA — vectorises the knowledge base for search by meaning (keywords + meaning), LOCALLY, without an API key.
#
#   bash vectoriser.sh              multilingual e5 model (recommended; ~2.2 GB downloaded once)
#   bash vectoriser.sh mpnet        faster model (~1 GB), slightly less accurate
#   bash vectoriser.sh minilm       small model (~0.2 GB): slow connection
#   bash vectoriser.sh ollama       Ollama bge-m3 (if Ollama is installed: ollama pull bge-m3)
#   bash vectoriser.sh hachage      no model at all (test only: keyword vectors)
#   bash vectoriser.sh e5 --exporter    also writes JSONL files {id, text, metadata, embedding} for Chroma / the ITU vector store
#
# What is encoded: the verified provisions and gaps of kb/ (kb/index/), and, if the large base base_v2 is present,
# the official texts, the WHO fact sheets and the pictograms (base_v2/07_vecteurs/).
# Interrupted (Ctrl+C, connection cut)? Run the same command again: it resumes where it stopped.
# Afterwards, lancer_local.sh and lancer_demo.sh use the search by meaning automatically (kb/index/RECHERCHE.txt).
set -euo pipefail
cd "$(dirname "$0")"

CHOIX="${1:-e5}"; shift || true
case "$CHOIX" in
  e5|mpnet|minilm) ENC="fastembed:$CHOIX" ;;
  ollama)          ENC="ollama:bge-m3" ;;
  hachage)         ENC="hachage" ;;
  fastembed:*|ollama:*) ENC="$CHOIX" ;;
  *) echo "Unknown choice: $CHOIX (e5, mpnet, minilm, ollama, hachage)"; exit 1 ;;
esac

# 1. Same Python environment as the launch scripts (.venv, created once)
command -v python3 >/dev/null || { echo "Python 3 is required: sudo apt install python3 python3-venv"; exit 1; }
if [ ! -x .venv/bin/python ]; then
  echo "→ Creating the Python environment (once)…"
  python3 -m venv .venv || { echo "Run: sudo apt install python3-venv   then start again."; exit 1; }
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q ollama pypdf certifi
fi
.venv/bin/pip install -q "numpy>=1.24"             # the vector matrices (needed by every encoder, "hachage" included)
if [ "$ENC" != hachage ] && [ "${ENC%%:*}" = fastembed ]; then
  echo "→ Installing the embedding library (fastembed, ONNX: no PyTorch, no GPU needed)…"
  .venv/bin/pip install -q -r requirements-vecteurs.txt
fi
if [ "${ENC%%:*}" = ollama ]; then
  command -v ollama >/dev/null || { echo "Ollama is not installed: https://ollama.com/download (or use: bash vectoriser.sh e5)"; exit 1; }
  ollama pull bge-m3
fi

# 2. Encode (resumable; only new or modified texts are re-encoded after an update of the base)
echo "→ Vectorising with $ENC (the first run downloads the model; keep the computer awake)…"
.venv/bin/python outils/vectoriser_base.py --encodeur "$ENC" "$@"

# 3. Remember the encoder: the launch scripts pass --recherche with it
mkdir -p kb/index
echo "$ENC" > kb/index/RECHERCHE.txt
echo
echo "✔ Done. Search by meaning is now on for:  bash lancer_local.sh   and   bash lancer_demo.sh"
echo "  (to switch it off: rm kb/index/RECHERCHE.txt)"
