# Mettre MEDIMCOM IA en ligne (gratuitement) pour des testeurs à distance

Objectif : vos amis testent depuis chez eux, même quand votre ordinateur est éteint. Il faut donc une machine
**toujours allumée** chez un hébergeur. Situation des offres gratuites en novembre 2026 :

| Option | Toujours allumé | Mémoire | Base `base_v2` + recherche par le sens | Carte bancaire | Verdict |
|---|---|---|---|---|---|
| **Oracle Cloud « Always Free »** (serveur Ubuntu Arm) | oui | 12 Go (2 cœurs) | oui | oui (vérification, pas de débit) | **recommandé** |
| **Render** (offre gratuite) | non : s'endort après 15 min, réveil ≈ 1 min | 512 Mo | non (version légère) | non | dépannage rapide |
| Hugging Face Spaces (Docker) | — | — | — | — | plus gratuit depuis juillet 2026 (PRO) |
| Tunnel Cloudflare / ngrok | seulement si VOTRE machine est allumée | — | — | — | ne répond pas au besoin |

Les fichiers prêts : `deploiement/deployer.sh` (à lancer sur votre ordinateur) et `deploiement/installer_serveur.sh` (exécuté sur le serveur, Oracle ou tout Ubuntu), `Dockerfile` et `render.yaml` (Render).
Aucune clé n'est jamais écrite dans le dépôt : la clé xAI est saisie sur le serveur (fichier `/etc/medimcom.env`, lisible
par l'administrateur seul) ou dans le tableau de bord de l'hébergeur.

## Option 1 — Oracle Cloud Always Free (recommandée)

### Tout depuis le terminal (le plus simple)

Seul préalable : **créer le compte** sur cloud.oracle.com (carte et téléphone : aucun script ne peut le faire à votre place).
Puis, dans le dossier du projet (celui qui contient `base_v2`) :

```bash
cd ~/Downloads/MEDIMCOM_IA
bash deploiement/creer_serveur_oracle.sh
```

Le script installe l'outil officiel d'Oracle (`oci`), vous connecte à votre compte (une seule fois : une page de connexion
Oracle s'ouvre dans le navigateur, choisir sa **région d'origine**), crée la clé SSH, le réseau et ouvre les ports 22, 80 et
443, crée le serveur Ubuntu Arm (2 cœurs, 12 Go) en essayant chaque zone, puis lance `deployer.sh` qui copie le projet et la
base, installe tout, demande la clé xAI et affiche les deux liens. Relançable sans risque (rien n'est créé en double).
Si Oracle répond « zone pleine » partout : `INSISTER=1 bash deploiement/creer_serveur_oracle.sh` réessaie toutes les 2 minutes.
Mises à jour ensuite : `bash deploiement/deployer.sh IP ~/.ssh/medimcom_oracle`.

### Ou à la main, dans la console Oracle

1. **Compte** : créer un compte sur cloud.oracle.com. La carte sert à vérifier l'identité ; les ressources « Always Free »
   ne sont pas facturées. Choisir la région d'origine avec soin (elle ne change plus) ; une région peu chargée
   (ex. Europe) évite le message « Out of capacity ».
2. **Serveur** : Compute > Instances > Create instance.
   - Image : *Canonical Ubuntu 24.04* ; forme : *Ampere VM.Standard.A1.Flex*, **2 OCPU, 12 Go** (reste dans le gratuit).
   - Télécharger la **clé SSH privée** proposée (ex. `oracle.key`) ; noter l'**adresse IP publique**.
   - « Out of capacity » : réessayer plus tard ou changer de domaine de disponibilité (AD).
3. **Ouvrir le web** : Networking > Virtual cloud networks > votre réseau > Subnet > Security List > Add Ingress Rules :
   source `0.0.0.0/0`, TCP, ports **80** puis **443** (le script ouvre aussi le pare-feu de la machine).
4. **Tout le reste en une commande, depuis votre ordinateur** (dossier du projet, celui qui contient `base_v2`) :
   ```bash
   cd ~/Downloads/MEDIMCOM_IA
   bash deploiement/deployer.sh IP_DU_SERVEUR ~/Downloads/oracle.key
   ```
   `deployer.sh` se connecte au serveur, copie le projet **et la base** (elle n'est pas sur GitHub ; la première copie peut
   prendre plusieurs minutes), puis lance `installer_serveur.sh` sur le serveur. Celui-ci installe Python, la recherche par le
   sens (fastembed) et Caddy (HTTPS automatique avec un nom gratuit `IP-AVEC-TIRETS.sslip.io`), demande la clé xAI
   **sans l'afficher**, crée un **lien médecin fixe** et lance le service (il redémarre tout seul après une panne ou un
   redémarrage du serveur). À la fin s'affichent :
   - écran patient : `https://…sslip.io/patient`
   - écran médecin : `https://…sslip.io/medecin?jeton=…` (**lien privé**)
5. **Mettre à jour** après une modification : **la même commande**. Elle ne recopie que ce qui a changé et redémarre le
   service ; la clé, le lien médecin et les journaux du serveur sont conservés.
6. **Réglages** : suivre ce qui se passe avec `ssh -i ~/Downloads/oracle.key ubuntu@IP sudo journalctl -u medimcom -f` ;
   changer les options (modèle, pays…) avec `sudo nano /etc/medimcom.env` sur le serveur (ligne `MEDIMCOM_ARGS`), puis
   `sudo systemctl restart medimcom`.

Sous Windows : lancer ces commandes dans WSL (Ubuntu pour Windows) ou Git Bash avec rsync.

Point d'attention : Oracle peut récupérer une instance gratuite **inactive** pendant 7 jours (processeur, réseau et mémoire
très peu utilisés). Pendant la période de test, les visites suffisent en général ; vérifier la console Oracle de temps en temps.

## Option 2 — Render (sans carte, version légère)

1. Le dépôt GitHub contient `Dockerfile` et `render.yaml`. Sur dashboard.render.com : New > **Blueprint** > choisir le dépôt.
2. Saisir `XAI_API_KEY` quand Render la demande. `MEDIMCOM_JETON` est généré par Render (onglet *Environment*).
3. Liens : `https://medimcom-ia.onrender.com/patient` et `https://medimcom-ia.onrender.com/medecin?jeton=…`
   (le nom exact est affiché par Render ; le lien complet apparaît aussi dans les *Logs*).

Limites : 512 Mo de mémoire, donc **sans** `base_v2` ni recherche par le sens (vocabulaire et textes intégrés seulement) ;
le service **s'endort** après 15 minutes sans visite (première page ≈ 1 minute) et la consultation **repart à zéro** à chaque
réveil (disque non conservé). Les journaux doivent donc être exportés avant la fin d'une séance de test.

## À dire aux testeurs (et à savoir)

- **Une seule consultation partagée** : tous les testeurs voient la même conversation ; « Nouvelle consultation » la remet à
  zéro pour tout le monde. Convenir d'un ordre de passage (un « médecin » et un « patient » à la fois).
- **Patients fictifs uniquement** (`--donnees-fictives`) : aucune donnée réelle, ni dans les messages ni dans les documents joints.
- **Écran patient public** : quiconque a le lien peut répondre comme le patient. Ne le donner qu'aux testeurs.
- **Lien médecin = mot de passe** : le donner en privé ; pour le changer, modifier `MEDIMCOM_JETON` et redémarrer.
- **Coût du modèle** : chaque appel à Grok est facturé sur VOTRE compte xAI. Fixer une **limite de dépense** sur
  console.x.ai, garder `--effort low` et `--agents-ia assistant` (les autres agents suivent leurs règles écrites, sans coût).
  Après le hackathon : **révoquer la clé** et en créer une nouvelle.
- **Pictogrammes ARASAAC** : usage non commercial, crédits affichés (voir NOTICE.md) — un test entre amis est conforme.
