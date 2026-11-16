#!/usr/bin/env bash
# MEDIMCOM IA — puts a new version (zip) into YOUR local project folder, IN PLACE, then publishes it on GitHub.
# The project folder is not moved or renamed; your own files stay: CLE_API.txt (API key), .venv, base_v2/,
# node_modules, sortie/, kb/index/RECHERCHE.txt. Nothing secret is ever committed.
#
#   bash mettre_a_jour_depot.sh                         zip and folder found automatically (see below)
#   bash mettre_a_jour_depot.sh ZIP [PROJECT_FOLDER]    explicit paths
#   FORCE=1 bash mettre_a_jour_depot.sh                 GitHub too slow to download? Replaces the GitHub version with
#                                                       your folder WITHOUT downloading GitHub's history (its old commits
#                                                       are replaced: use only if your folder holds the whole project)
#   PUSH=0 bash mettre_a_jour_depot.sh                  update the folder and commit, but do not publish
#
# Defaults: ZIP = the newest ~/Downloads/MEDIMCOM_IA*final*.zip ;
#           PROJECT_FOLDER = ~/Downloads/MEDIMCOM_IA_local/MEDIMCOM_IA
set -euo pipefail

DEPOT_GITHUB="https://github.com/baudouin2/MEDIMCOM-IA.git"
ZIP="${1:-$(ls -t "$HOME"/Downloads/MEDIMCOM_IA*final*.zip 2>/dev/null | head -1 || true)}"
PROJET="${2:-$HOME/Downloads/MEDIMCOM_IA_local/MEDIMCOM_IA}"
# Files of earlier versions that no longer exist (removed from the folder and from GitHub)
OBSOLETES=(
  docs/soumission/MEDIMCOM_IA_Technical_Documentation.pdf
  kb/InputDocs/AI_Use_Cases/MEDIMCOM_IA_use_case_healthcare_UAE.md
  docs/video/MEDIMCOM_IA_Script_demo_pas_a_pas.docx
  docs/video/MEDIMCOM_IA_Script_demo_pas_a_pas.pdf
)

etape() { echo; echo "━━ $*"; }
stop() { echo "✘ $*"; exit 1; }
# Refuses to commit anything that looks like an API key (CLE_API.txt itself is never committed: .gitignore)
sans_secret() {
  git rm -q --cached --ignore-unmatch CLE_API.txt .env 2>/dev/null || true
  if git diff --cached -U0 -- . ':(exclude)tests' ':(exclude)CLE_API.exemple.txt' | grep -E '^\+' \
     | grep -Eq '(gsk_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|xai-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,}|sk-ant-[A-Za-z0-9_-]{20,})'; then
    echo "Files concerned:"; git diff --cached -U0 -- . ':(exclude)tests' | grep -E '^\+\+\+ |xai-|gsk_|sk-|AIza' | grep '^+++' | sed 's/^+++ b\//  /'
    git reset -q
    stop "An API key appears in a file to commit. Nothing was committed or published. Remove the key from that file, then start again."
  fi
}

# 0. Checks
[ -n "$ZIP" ] && [ -f "$ZIP" ] || stop "Zip not found. Give its path: bash $0 ~/Downloads/MEDIMCOM_IA_version_finale.zip"
[ -d "$PROJET" ] || stop "Project folder not found: $PROJET  (give it as 2nd argument)"
command -v git >/dev/null || stop "git is missing: sudo apt install git"
command -v unzip >/dev/null || stop "unzip is missing: sudo apt install unzip"
cd "$PROJET"
[ -d .git ] || stop "$PROJET is not a git repository (no .git folder)."
echo "Zip     : $ZIP"
echo "Folder  : $PROJET   (updated in place)"

# 1. Leave any half-finished git operation of earlier attempts
git merge --abort 2>/dev/null || true
git rebase --abort 2>/dev/null || true
git remote get-url origin >/dev/null 2>&1 || git remote add origin "$DEPOT_GITHUB"
git branch -M main

# 2. Keep the current state in a commit (nothing is lost: it stays in the history)
etape "1/5 Saving the current state of the folder"
git add -A
sans_secret
git diff --cached --quiet || git commit -q -m "Sauvegarde avant mise à jour ($(date '+%Y-%m-%d %H:%M'))"
echo "✔ Saved (git log shows it)."

# 3. Unzip in a temporary folder, then copy over the project (only the files of the new version)
etape "2/5 Copying the new version into the folder"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
unzip -q "$ZIP" -d "$TMP"
AGENTS_PY="$(find "$TMP" -maxdepth 4 -path '*/medimcom/agents.py' | head -1)"
[ -n "$AGENTS_PY" ] || stop "This zip does not contain the MEDIMCOM IA project."
SRC="$(dirname "$(dirname "$AGENTS_PY")")"
[ -f "$SRC/medimcom/agents.py" ] || stop "This zip does not contain the MEDIMCOM IA project."
rm -f "$SRC/CLE_API.txt"                                  # never overwrite your key (and never ship one)
rm -rf interface/web/dist                                 # the built interface is replaced as a whole
if command -v rsync >/dev/null; then
  rsync -a --exclude CLE_API.txt --exclude .venv --exclude base_v2 --exclude node_modules --exclude sortie "$SRC"/ ./
else
  cp -a "$SRC"/. ./
fi
for f in "${OBSOLETES[@]}"; do
  [ -e "$f" ] && { git rm -q -f --ignore-unmatch "$f" 2>/dev/null || rm -f "$f"; echo "  removed (obsolete): $f"; }
done
echo "✔ Folder updated."

# 4. Safety: no API key may be committed
etape "3/5 Checking that no secret is committed"
git add -A
sans_secret
echo "✔ No key found."

# 5. Quick test (if Python is there): the server code imports and the tests pass
etape "4/5 Quick check"
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
if $PY -c "import medimcom.agents, medimcom.regles" 2>/dev/null; then echo "✔ The code loads."; else echo "⚠ The code does not load with $PY (missing packages?). Continuing."; fi
if $PY -c "import pytest" 2>/dev/null; then
  $PY -m pytest -q -x 2>&1 | tail -1 || echo "⚠ Some tests fail: check before the demo."
fi

git add -A
sans_secret
if git diff --cached --quiet; then echo "Nothing new compared with your folder."; else
  git commit -q -m "MEDIMCOM IA : version finale (Cameroun, rapport v3, démo en anglais, recherche par le sens)"
  echo "✔ Commit: $(git log -1 --format='%h %s')"
fi

# 6. Publish on GitHub
[ "${PUSH:-1}" = 0 ] && { echo; echo "PUSH=0: not published. Later: cd \"$PROJET\" && git push -u origin main"; exit 0; }
etape "5/5 Publishing on GitHub ($DEPOT_GITHUB)"
if [ "${FORCE:-0}" = 1 ]; then
  echo "FORCE=1: GitHub will hold exactly this folder."
  git push --force -u origin main
else
  echo "Downloading what GitHub has that this folder lacks. It can take several minutes on a slow connection:"
  echo "do NOT press Ctrl+C. (If it is really too slow: Ctrl+C, then FORCE=1 bash $0)"
  for essai in 1 2 3; do
    git fetch --progress origin main && break
    echo "Connection cut, new attempt ($essai/3)…"; sleep 5
  done
  if git rev-parse -q --verify origin/main >/dev/null; then
    if ! git merge -X ours --allow-unrelated-histories --no-edit origin/main; then
      # conflicts the strategy cannot settle (file deleted on one side): keep this folder's version
      git diff --name-only --diff-filter=U | while read -r f; do
        if [ -e "$f" ]; then git checkout --ours -- "$f" 2>/dev/null || true; git add -- "$f"; else git rm -q -- "$f" || true; fi
      done
      git commit -q --no-edit
    fi
    for f in "${OBSOLETES[@]}"; do git rm -q -f --ignore-unmatch "$f"; done      # an old file may come back from GitHub
    git diff --cached --quiet || git commit -q -m "Retrait des fichiers des versions précédentes"
    echo "✔ Merged with GitHub (this folder's version wins wherever both differ)."
  fi
  git push -u origin main
fi
echo
echo "✔ Published. Check: https://github.com/baudouin2/MEDIMCOM-IA"
