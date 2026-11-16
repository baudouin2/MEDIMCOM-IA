#!/usr/bin/env bash
# Met MEDIMCOM IA en ligne sur VOTRE serveur (Oracle Always Free ou tout serveur Ubuntu), depuis VOTRE ordinateur.
#   Première fois et mises à jour, même commande :
#     bash deploiement/deployer.sh IP_DU_SERVEUR  [chemin/cle_ssh]      (clé par défaut : ~/Downloads/oracle.key)
#   1re fois : copie le projet + la base, installe tout (la clé xAI est demandée sans s'afficher), affiche les liens.
#   Ensuite  : recopie seulement ce qui a changé et redémarre le service ; la consultation et les journaux du serveur sont gardés.
set -euo pipefail
IP="${1:?Usage : bash deploiement/deployer.sh IP_DU_SERVEUR [chemin/cle_ssh]}"
CLE="${2:-$HOME/Downloads/oracle.key}"
UTIL="${UTILISATEUR:-ubuntu}"                       # utilisateur des images Ubuntu d'Oracle
ICI="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "$CLE" ] || { echo "Clé SSH introuvable : $CLE (celle téléchargée à la création du serveur)"; exit 1; }
chmod 600 "$CLE"
SSH="ssh -i $CLE -p ${PORT_SSH:-22} -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15"
command -v rsync >/dev/null || { echo "rsync manque : sudo apt install rsync (Linux) — déjà présent sur macOS"; exit 1; }
[ -d "$ICI/base_v2" ] || echo "⚠ Pas de dossier base_v2 ici : le serveur tournera avec le vocabulaire intégré seulement."

echo "→ Connexion à $UTIL@$IP…"
$SSH "$UTIL@$IP" true || { echo "Connexion impossible : vérifier l'IP, la clé, et que le serveur est démarré (console Oracle)."; exit 1; }

echo "→ Copie du projet et de la base (la première fois peut prendre plusieurs minutes)…"
rsync -az --stats -e "$SSH" \
  --exclude node_modules --exclude .venv --exclude .env --exclude '*.env' --exclude sortie --exclude archives \
  --exclude __pycache__ --exclude .pytest_cache --exclude .git \
  "$ICI/" "$UTIL@$IP:~/MEDIMCOM_IA/" | grep -E "Number of (regular )?files transferred|Total transferred file size" || true

if $SSH "$UTIL@$IP" "systemctl is-enabled medimcom >/dev/null 2>&1"; then
  echo "→ Déjà installé : redémarrage avec la nouvelle version…"
  $SSH "$UTIL@$IP" "cd ~/MEDIMCOM_IA && .venv/bin/pip install -q pypdf >/dev/null 2>&1; sudo systemctl restart medimcom && sleep 3 && systemctl is-active medimcom"
else
  echo "→ Première installation sur le serveur…"
  $SSH -t "$UTIL@$IP" "bash ~/MEDIMCOM_IA/deploiement/installer_serveur.sh"
fi

URL="$($SSH "$UTIL@$IP" "sudo grep '^MEDIMCOM_URL_PUBLIQUE=' /etc/medimcom.env | cut -d= -f2-")"
JETON="$($SSH "$UTIL@$IP" "sudo grep '^MEDIMCOM_JETON=' /etc/medimcom.env | cut -d= -f2-")"
echo
echo "Écran PATIENT (à donner aux testeurs) : $URL/patient"
echo "Écran MÉDECIN (lien privé)            : $URL/medecin?jeton=$JETON"
echo "Si la page ne s'ouvre pas : ports 80 et 443 ouverts dans la Security List d'Oracle ? (voir docs/DEPLOIEMENT.md)"
echo "Voir ce qui se passe sur le serveur   : $SSH $UTIL@$IP sudo journalctl -u medimcom -f"
