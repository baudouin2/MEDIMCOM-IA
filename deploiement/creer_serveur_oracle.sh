#!/usr/bin/env bash
# Crée le serveur gratuit Oracle (Always Free) DEPUIS VOTRE TERMINAL, puis y installe MEDIMCOM IA.
#   bash deploiement/creer_serveur_oracle.sh
# Seul préalable hors du terminal : le compte Oracle lui-même (inscription sur cloud.oracle.com avec carte et téléphone,
# qu'aucun script ne peut faire à votre place). Ensuite tout se fait ici :
#   1. installe l'outil officiel d'Oracle (« oci ») si besoin, dans ~/.oci-cli ;
#   2. connexion à votre compte : une seule fois, une page de connexion Oracle s'ouvre dans le navigateur, puis l'outil
#      crée et enregistre lui-même sa clé d'accès (~/.oci) ;
#   3. crée la clé SSH (~/.ssh/medimcom_oracle), le réseau, ouvre les ports 22, 80 et 443 ;
#   4. crée le serveur Ubuntu 24.04 Arm (2 cœurs, 12 Go : dans le gratuit) en essayant chaque zone si l'une est pleine ;
#   5. lance deploiement/deployer.sh (copie du projet et de la base, installation, HTTPS, liens).
# Relançable sans risque : ce qui existe déjà (réseau, serveur « medimcom ») est réutilisé, rien n'est créé en double.
# Options : INSISTER=1 (réessaie toutes les 2 min tant qu'Oracle n'a pas de place), OCPU=2, MEMOIRE=12, DISQUE=50.
set -euo pipefail
ICI="$(cd "$(dirname "$0")/.." && pwd)"
NOM=medimcom
OCPU="${OCPU:-2}"; MEMOIRE="${MEMOIRE:-12}"; DISQUE="${DISQUE:-50}"
CLE_SSH="$HOME/.ssh/medimcom_oracle"

json() { python3 -c "import sys,json
t=sys.stdin.read().strip()
try: d=json.loads(t) if t else {}
except ValueError: d={}
try: v=eval(sys.argv[1])
except Exception: v=''
print('' if v is None else (' '.join(map(str,v)) if isinstance(v,list) else v))" "$1"; }

# 1. Outil oci
if command -v oci >/dev/null; then OCI=oci
else
  OCI="$HOME/.oci-cli/bin/oci"
  if [ ! -x "$OCI" ]; then
    echo "→ Installation de l'outil Oracle « oci » dans ~/.oci-cli (une fois)…"
    python3 -m venv "$HOME/.oci-cli" && "$HOME/.oci-cli/bin/pip" install -q --upgrade pip oci-cli
  fi
fi

# 2. Connexion au compte (une fois)
if [ ! -f "$HOME/.oci/config" ]; then
  echo "→ Connexion à votre compte Oracle : une page va s'ouvrir dans le navigateur."
  echo "  Choisissez votre région d'origine (celle de l'inscription), connectez-vous, puis revenez ici."
  "$OCI" setup bootstrap
fi
T="$(sed -n 's/^tenancy *= *//p' "$HOME/.oci/config" | head -1)"
[ -n "$T" ] || { echo "Configuration ~/.oci/config incomplète : relancer « $OCI setup bootstrap »"; exit 1; }
"$OCI" iam region-subscription list >/dev/null || { echo "Accès refusé par Oracle : relancer « $OCI setup bootstrap »"; exit 1; }
echo "✓ Connecté au compte Oracle"

# 3. Clé SSH et réseau
[ -f "$CLE_SSH" ] || ssh-keygen -q -t rsa -b 4096 -N "" -f "$CLE_SSH" -C medimcom
VCN="$("$OCI" network vcn list --compartment-id "$T" --display-name "$NOM-vcn" | json "d['data'][0]['id'] if d.get('data') else ''")"
if [ -z "$VCN" ]; then
  echo "→ Création du réseau…"
  VCN="$("$OCI" network vcn create --compartment-id "$T" --cidr-block 10.0.0.0/16 --display-name "$NOM-vcn" --dns-label "$NOM" \
         --wait-for-state AVAILABLE | json "d['data']['id']")"
fi
INFO="$("$OCI" network vcn get --vcn-id "$VCN")"
RT="$(json "d['data']['default-route-table-id']" <<<"$INFO")"
SL="$(json "d['data']['default-security-list-id']" <<<"$INFO")"
IGW="$("$OCI" network internet-gateway list --compartment-id "$T" --vcn-id "$VCN" | json "d['data'][0]['id'] if d.get('data') else ''")"
[ -n "$IGW" ] || IGW="$("$OCI" network internet-gateway create --compartment-id "$T" --vcn-id "$VCN" --is-enabled true \
                        --display-name "$NOM-internet" --wait-for-state AVAILABLE | json "d['data']['id']")"
"$OCI" network route-table update --rt-id "$RT" --force \
  --route-rules "[{\"destination\":\"0.0.0.0/0\",\"destinationType\":\"CIDR_BLOCK\",\"networkEntityId\":\"$IGW\"}]" >/dev/null
port() { echo "{\"source\":\"0.0.0.0/0\",\"protocol\":\"6\",\"tcpOptions\":{\"destinationPortRange\":{\"min\":$1,\"max\":$1}}}"; }
"$OCI" network security-list update --security-list-id "$SL" --force \
  --ingress-security-rules "[$(port 22),$(port 80),$(port 443),{\"source\":\"0.0.0.0/0\",\"protocol\":\"1\",\"icmpOptions\":{\"type\":3,\"code\":4}}]" \
  --egress-security-rules '[{"destination":"0.0.0.0/0","protocol":"all"}]' >/dev/null
SUB="$("$OCI" network subnet list --compartment-id "$T" --vcn-id "$VCN" | json "d['data'][0]['id'] if d.get('data') else ''")"
[ -n "$SUB" ] || SUB="$("$OCI" network subnet create --compartment-id "$T" --vcn-id "$VCN" --cidr-block 10.0.0.0/24 \
                        --display-name "$NOM-public" --dns-label public --wait-for-state AVAILABLE | json "d['data']['id']")"
echo "✓ Réseau prêt (ports 22, 80 et 443 ouverts)"

# 4. Serveur
ID="$("$OCI" compute instance list --compartment-id "$T" --display-name "$NOM" --lifecycle-state RUNNING | json "d['data'][0]['id'] if d.get('data') else ''")"
if [ -z "$ID" ]; then
  IMG="$("$OCI" compute image list --compartment-id "$T" --operating-system "Canonical Ubuntu" --operating-system-version "24.04" \
         --shape VM.Standard.A1.Flex --sort-by TIMECREATED --sort-order DESC | json "d['data'][0]['id'] if d.get('data') else ''")"
  [ -n "$IMG" ] || { echo "Image Ubuntu 24.04 Arm introuvable dans cette région."; exit 1; }
  ZONES="$("$OCI" iam availability-domain list --compartment-id "$T" | json "[z['name'] for z in d.get('data', [])]")"
  while [ -z "$ID" ]; do
    for AD in $ZONES; do
      echo "→ Création du serveur ($OCPU cœurs, $MEMOIRE Go) dans $AD…"
      if SORTIE="$("$OCI" compute instance launch --compartment-id "$T" --availability-domain "$AD" --display-name "$NOM" \
            --shape VM.Standard.A1.Flex --shape-config "{\"ocpus\":$OCPU,\"memoryInGBs\":$MEMOIRE}" --image-id "$IMG" \
            --subnet-id "$SUB" --assign-public-ip true --boot-volume-size-in-gbs "$DISQUE" \
            --ssh-authorized-keys-file "$CLE_SSH.pub" --wait-for-state RUNNING 2>&1)"; then
        ID="$(json "d['data']['id']" <<<"$(sed -n '/^{/,$p' <<<"$SORTIE")")"; break
      fi
      case "$SORTIE" in
        *"Out of host capacity"*|*OutOfCapacity*|*"out of capacity"*) echo "  zone pleine pour l'instant" ;;
        *LimitExceeded*|*"service limit"*) echo "Limite gratuite dépassée : un autre serveur Arm existe déjà sur ce compte (console > Compute)."; exit 1 ;;
        *) echo "$SORTIE" | tail -15; exit 1 ;;
      esac
    done
    if [ -z "$ID" ]; then
      [ "${INSISTER:-0}" = 1 ] || { echo "Oracle n'a pas de place en ce moment. Relancer plus tard, ou : INSISTER=1 bash $0"; exit 1; }
      echo "  nouvel essai dans 2 minutes (Ctrl+C pour arrêter)…"; sleep 120
    fi
  done
  echo "✓ Serveur créé"
else
  echo "✓ Serveur « $NOM » déjà en marche : réutilisé"
fi
IP="$("$OCI" compute instance list-vnics --instance-id "$ID" | json "d['data'][0]['public-ip']")"
echo "✓ Adresse IP publique : $IP"

# 5. Attendre que le serveur accepte SSH, puis installer MEDIMCOM IA
echo "→ Démarrage du serveur (1 à 3 minutes)…"
for _ in $(seq 1 40); do
  ssh -i "$CLE_SSH" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 -o BatchMode=yes "ubuntu@$IP" true 2>/dev/null && break
  sleep 6
done
bash "$ICI/deploiement/deployer.sh" "$IP" "$CLE_SSH"
echo
echo "Mises à jour plus tard : bash deploiement/deployer.sh $IP $CLE_SSH"
