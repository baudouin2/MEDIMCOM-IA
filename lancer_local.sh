#!/usr/bin/env bash
# Starts MEDIMCOM IA on THIS computer (no hosting needed). Linux / macOS; on Windows use WSL or Git Bash.
#
#   bash lancer_local.sh             Uses the API key pasted in CLE_API.txt: the provider is recognised from the key
#                                    (Groq, OpenRouter, Gemini, Mistral: free tiers; xAI/Grok, Anthropic/Claude, OpenAI: paid).
#                                    No key: local Ollama model if installed, otherwise written rules only.
#   bash lancer_local.sh ollama      Open-source model qwen3:8b ON THIS COMPUTER: no key, nothing leaves the machine.
#                                    At least 8 GB of memory.
#   bash lancer_local.sh sans-ia     Written rules only (no language model): instant, to check that everything works.
#   bash lancer_local.sh diagnostic  "Model unavailable"? Tests Internet, certificates, key, quota and model, and says what to do.
#   bash lancer_local.sh cle         Shows which provider and model CLE_API.txt will give, without starting anything.
#
# Optional settings (before the command):
#   MODELE=qwen3:14b      another model (Ollama: https://ollama.com/search?c=tools); with a key, prefer MODELE= in CLE_API.txt
#   VISION=1              Ollama: also downloads qwen3-vl:8b to read PHOTOS of prescriptions, receipts, medicine boxes
#   RESEAU=1              patient screen open to the tablet on the same Wi-Fi (otherwise this computer only)
#   PAYS=CM               Cameroonian law (default: AE, United Arab Emirates)        PORT=8001   another port
#   AGENTS=tous           all agents use the model (default: the assistant; the others follow their written rules)
set -euo pipefail
cd "$(dirname "$0")"
MODE="${1:-auto}"
PORT="${PORT:-8000}"; PAYS="${PAYS:-AE}"; AGENTS="${AGENTS:-assistant}"

# 1. Python and dependencies (in .venv, once)
command -v python3 >/dev/null || { echo "Python 3.10 or newer is required: https://www.python.org/downloads/"; exit 1; }
if [ ! -x .venv/bin/python ]; then
  echo "→ Setting up Python (once)…"
  python3 -m venv .venv
fi
if [ ! -f .venv/.pret2 ]; then
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q ollama pypdf certifi
  if [ -d base_v2 ]; then .venv/bin/pip install -q -r requirements-vecteurs.txt || echo "  (semantic search unavailable: keyword search only)"; fi
  touch .venv/.pret2
fi
if [ ! -f interface/web/dist/index.html ]; then
  command -v npm >/dev/null || { echo "Interface not built and npm missing: install Node.js (https://nodejs.org)"; exit 1; }
  (cd interface/web && npm install --silent && npm run build --silent)
fi

# 2. Which language model?
ARGS=(--interface react --pays "$PAYS" --port "$PORT" --agents-ia "$AGENTS")
[ "${RESEAU:-0}" = 1 ] && ARGS+=(--hote 0.0.0.0)
[ -f CLE_API.txt ] || cp CLE_API.exemple.txt CLE_API.txt          # first start: key file to fill in
if [ "$MODE" = auto ] || [ "$MODE" = groq ] || [ "$MODE" = openrouter ]; then
  ETAT_CLE="$(.venv/bin/python -m medimcom.cle_api 2>&1)" && MODE=cle_api
  if [ "$MODE" = cle_api ]; then :
  elif command -v ollama >/dev/null && [ "${1:-auto}" = auto ]; then
    echo "CLE_API.txt: no API key. Ollama is installed: local model (nothing leaves the computer)."; MODE=ollama
  else
    echo "$ETAT_CLE"                                   # the exact reason (no key, key not recognised, PATIENTS_FICTIFS=non…)
    MODE=sans-ia
  fi
fi
case "$MODE" in
  cle_api)
    [ -n "${MODELE:-}" ] && ARGS+=(--modele "$MODELE")
    ;;
  cle) exec .venv/bin/python -m medimcom.cle_api ;;
  ollama)
    MODELE="${MODELE:-qwen3:8b}"
    if ! command -v ollama >/dev/null; then
      echo "Ollama is not installed. It runs open-source models on your computer:"
      case "$(uname)" in
        Darwin) echo "  macOS: download https://ollama.com/download (or: brew install ollama), open it, then run this script again." ;;
        *)      echo "  Linux: curl -fsSL https://ollama.com/install.sh | sh     then run this script again." ;;
      esac
      exit 1
    fi
    if [ "$(uname)" = Darwin ]; then MEM=$(( $(sysctl -n hw.memsize) / 1073741824 )); else MEM=$(( $(awk '/MemTotal/{print $2}' /proc/meminfo) / 1048576 )); fi
    [ "$MEM" -lt 8 ] && echo "⚠ $MEM GB of memory: $MODELE may be very slow. Try MODELE=qwen3:4b, or a free Groq key in CLE_API.txt"
    if ! curl -s -m 3 http://127.0.0.1:11434/api/tags >/dev/null; then
      echo "→ Starting Ollama…"; mkdir -p sortie
      (ollama serve > sortie/ollama.log 2>&1 &) ; sleep 3
    fi
    ollama list | awk 'NR>1{print $1}' | grep -qx "$MODELE" || { echo "→ Downloading $MODELE (once, several GB)…"; ollama pull "$MODELE"; }
    if [ "${VISION:-0}" = 1 ]; then
      ollama list | awk 'NR>1{print $1}' | grep -qx "qwen3-vl:8b" || { echo "→ Downloading qwen3-vl:8b (reading photos)…"; ollama pull qwen3-vl:8b; }
      export MEDIMCOM_MODELE_VISION=qwen3-vl:8b
    fi
    ARGS+=(--mode ollama --modele "$MODELE")
    echo "✓ Open-source model $MODELE on this computer: nothing leaves the machine."
    ;;
  sans-ia) ARGS+=(--mode simule); echo "✓ Written rules only (no language model)." ;;
  diagnostic) exec .venv/bin/python outils/diagnostic_modele.py "${@:2}" ;;
  *) echo "Unknown mode: $MODE (auto, ollama, sans-ia, diagnostic, cle)"; exit 1 ;;
esac
echo "  Open the DOCTOR link printed below in your browser; Ctrl+C to stop."
echo
exec .venv/bin/python interface/serveur.py "${ARGS[@]}"
