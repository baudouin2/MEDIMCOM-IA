#!/usr/bin/env bash
# MEDIMCOM IA — starts everything needed to film the demo (docs/video/MEDIMCOM_IA_Demo_script_EN.docx uses port 8000 only):
#   port 8000  conversations 1 and 2 (live)          port 8001  conversation 3 (replayed scenario: injected errors)
#   port 8002  conversation 4 (replayed contagion case)      sortie/journal.json  for the tamper-evidence proof
#
#   bash lancer_demo.sh            agents on their written rules: what appears matches the script exactly
#   bash lancer_demo.sh modele     conversations 1-2 use the language model of CLE_API.txt (fictitious patients only)
#
# The three doctor links share one private token for this session; Ctrl+C stops everything.
set -euo pipefail
cd "$(dirname "$0")"

# 1. Python environment (same as lancer_local.sh, created once)
command -v python3 >/dev/null || { echo "Python 3 is required: sudo apt install python3 python3-venv"; exit 1; }
if [ ! -x .venv/bin/python ]; then
  echo "→ Creating the Python environment (once)…"
  python3 -m venv .venv || { echo "Run: sudo apt install python3-venv   then start again."; exit 1; }
fi
if [ ! -f .venv/.pret2 ]; then
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q ollama pypdf certifi
  if [ -d base_v2 ]; then .venv/bin/pip install -q -r requirements-vecteurs.txt || true; fi
  touch .venv/.pret2
fi
if [ ! -f interface/web/dist/index.html ]; then
  command -v npm >/dev/null || { echo "Interface not built and npm missing: sudo apt install nodejs npm"; exit 1; }
  (cd interface/web && npm install --silent && npm run build --silent)
fi
PY=.venv/bin/python

# 2. One private token for the three doctor links; free ports
export MEDIMCOM_JETON="${MEDIMCOM_JETON:-$($PY -c 'import secrets; print(secrets.token_urlsafe(18))')}"
for p in 8000 8001 8002; do
  if (exec 3<>/dev/tcp/127.0.0.1/$p) 2>/dev/null; then
    echo "Port $p is already in use (a server is still running?). Stop it, e.g.: fuser -k $p/tcp"; exit 1
  fi
done
MODE_LIVE=(--mode simule)
[ "${1:-}" = modele ] && MODE_LIVE=()                 # no --mode: the key of CLE_API.txt chooses the model
# Search by meaning (optional): RECHERCHE=fastembed:e5, or the encoder recorded by vectoriser.sh
RECHERCHE="${RECHERCHE:-$(cat kb/index/RECHERCHE.txt 2>/dev/null || true)}"
[ -n "$RECHERCHE" ] && MODE_LIVE+=(--recherche "$RECHERCHE") && echo "Search by meaning: $RECHERCHE"
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"; IP="${IP:-127.0.0.1}"
mkdir -p sortie

# 3. Start the three servers (logs in sortie/demo_*.log)
PIDS=()
arreter() { echo; echo "Stopping the demo servers…"; kill "${PIDS[@]}" 2>/dev/null || true; wait 2>/dev/null || true; echo "Stopped."; }
trap arreter EXIT INT TERM
$PY interface/serveur.py --interface react --hote 0.0.0.0 --port 8000 "${MODE_LIVE[@]}" > sortie/demo_live.log 2>&1 & PIDS+=($!)
$PY interface/serveur.py --interface react --hote 0.0.0.0 --port 8001 --mode simule --demo scenarios/grossesse.json > sortie/demo_erreurs.log 2>&1 & PIDS+=($!)
$PY interface/serveur.py --interface react --hote 0.0.0.0 --port 8002 --mode simule --demo scenarios/contagion.json > sortie/demo_crise.log 2>&1 & PIDS+=($!)

# 4. Journal for the final proof (conversation 5)
$PY main.py --scenario scenarios/contagion.json --silencieux > /dev/null 2>&1 || echo "⚠ sortie/journal.json not created (see: python3 main.py --scenario scenarios/contagion.json)"

# 5. Wait until the servers answer
for p in 8000 8001 8002; do
  for _ in $(seq 1 40); do (exec 3<>/dev/tcp/127.0.0.1/$p) 2>/dev/null && break; sleep 0.5; done
  (exec 3<>/dev/tcp/127.0.0.1/$p) 2>/dev/null || { echo "The server on port $p did not start. Log:"; tail -20 sortie/demo_*.log; exit 1; }
done

J="$MEDIMCOM_JETON"
cat <<EOF

=====================================================================
 MEDIMCOM IA — demo ready ($( [ "${1:-}" = modele ] && echo "conversations 1-2 with the language model of CLE_API.txt" || echo "written rules: matches the script exactly" ))
=====================================================================
 Conversations 1 and 2 (live)
   DOCTOR  (this computer, private):  http://127.0.0.1:8000/medecin?jeton=$J
   PATIENT (tablet, same Wi-Fi)    :  http://$IP:8000/patient
 Conversation 3 (injected errors, "Étape suivante" button)
   DOCTOR :  http://127.0.0.1:8001/medecin?jeton=$J
 Conversation 4 (suspected contagious disease, "Étape suivante" button)
   DOCTOR :  http://127.0.0.1:8002/medecin?jeton=$J
 Final proof (paste in a terminal):
   .venv/bin/python verifier_journal.py sortie/journal.json --falsifier 10
---------------------------------------------------------------------
 Fictitious patients only. Do not film the address bar of a DOCTOR link.
 If the tablet cannot connect: same Wi-Fi, then  sudo ufw allow 8000:8002/tcp
 Logs: sortie/demo_live.log, demo_erreurs.log, demo_crise.log — Ctrl+C stops everything.
=====================================================================
EOF

# 6. Open the doctor screens in the browser (one tab per conversation)
if command -v xdg-open >/dev/null; then
  for p in 8000 8001 8002; do xdg-open "http://127.0.0.1:$p/medecin?jeton=$J" >/dev/null 2>&1 || true; sleep 1; done
fi
wait
