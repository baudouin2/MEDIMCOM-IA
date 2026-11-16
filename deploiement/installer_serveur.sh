#!/usr/bin/env bash
# Installe MEDIMCOM IA sur un serveur Ubuntu toujours allumé (ex. Oracle Cloud Always Free) avec HTTPS automatique.
#   1. sur VOTRE ordinateur, copiez le projet et sa base :   rsync -avz --exclude node_modules --exclude .venv --exclude .env --exclude sortie ~/Downloads/MEDIMCOM_IA/ ubuntu@IP:~/MEDIMCOM_IA/
#      (le code ET la base base_v2, sans node_modules ni .env)
#   2. sur le serveur :   bash ~/MEDIMCOM_IA/deploiement/installer_serveur.sh
#   Mise à jour plus tard : refaire le rsync, puis sur le serveur : sudo systemctl restart medimcom
# Le script demande la clé xAI sans l'afficher et crée un lien médecin fixe. Rien de secret n'est écrit dans le dépôt.
set -euo pipefail
DEPOT="${DEPOT:-https://github.com/baudouin2/MEDIMCOM-IA.git}"
DOSSIER="$HOME/MEDIMCOM_IA"
IP="$(curl -s https://api.ipify.org || hostname -I | awk '{print $1}')"
DOMAINE="${DOMAINE:-${IP//./-}.sslip.io}"          # nom gratuit qui pointe vers l'IP du serveur (HTTPS possible)

sudo apt-get update -y
sudo apt-get install -y python3 python3-venv git rsync debian-keyring debian-archive-keyring apt-transport-https curl
if ! command -v caddy >/dev/null; then              # Caddy : HTTPS automatique (certificat Let's Encrypt)
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
  sudo apt-get update -y && sudo apt-get install -y caddy
fi
# Code : déjà copié par rsync depuis votre ordinateur, sinon cloné depuis GitHub (dépôt public, ou privé avec un jeton)
if [ ! -f "$DOSSIER/interface/serveur.py" ]; then git clone "$DEPOT" "$DOSSIER"; fi
cd "$DOSSIER"
[ -d .git ] && git pull --ff-only || true
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements-vecteurs.txt pypdf certifi || echo "fastembed indisponible : recherche par mots-clés seulement"

# Secrets : fichier lisible par root seulement, hors du dépôt
if [ ! -f /etc/medimcom.env ]; then
  read -s -p "Clé xAI (rien ne s'affiche ; Entrée pour s'en passer) : " CLE; echo
  JETON="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  sudo tee /etc/medimcom.env >/dev/null <<FIN
XAI_API_KEY=$CLE
MEDIMCOM_JETON=$JETON
MEDIMCOM_HOTES=$DOMAINE
MEDIMCOM_URL_PUBLIQUE=https://$DOMAINE
MEDIMCOM_HOTE=127.0.0.1
PORT=8000
MEDIMCOM_ARGS=--interface react
FIN
  sudo chmod 600 /etc/medimcom.env; unset CLE
fi
# Avec une clé : Grok pour l'assistant, patients fictifs seulement. Options modifiables ensuite dans /etc/medimcom.env
if sudo grep -q '^XAI_API_KEY=.\+' /etc/medimcom.env && sudo grep -q '^MEDIMCOM_ARGS=--interface react$' /etc/medimcom.env; then
  sudo sed -i 's/^MEDIMCOM_ARGS=.*/MEDIMCOM_ARGS=--interface react --fournisseur xai --effort low --donnees-fictives --agents-ia assistant/' /etc/medimcom.env
fi

sudo tee /etc/systemd/system/medimcom.service >/dev/null <<FIN
[Unit]
Description=MEDIMCOM IA
After=network-online.target
[Service]
User=$USER
WorkingDirectory=$DOSSIER
EnvironmentFile=/etc/medimcom.env
ExecStart=$DOSSIER/.venv/bin/python interface/serveur.py \$MEDIMCOM_ARGS
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
FIN
echo "$DOMAINE {
  reverse_proxy 127.0.0.1:8000
}" | sudo tee /etc/caddy/Caddyfile >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now medimcom
sudo systemctl restart caddy
# Pare-feu de la machine (Oracle ouvre aussi les ports 80 et 443 dans la « Security List » du réseau, voir le guide)
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT; sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo sh -c 'command -v netfilter-persistent >/dev/null && netfilter-persistent save' || true
sleep 3
echo
echo "Écran PATIENT  : https://$DOMAINE/patient"
echo "Écran MÉDECIN  : https://$DOMAINE/medecin?jeton=$(sudo grep MEDIMCOM_JETON /etc/medimcom.env | cut -d= -f2)"
echo "Journal du service : sudo journalctl -u medimcom -f"
