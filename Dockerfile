# MEDIMCOM IA en conteneur (Render, Koyeb, Cloud Run, serveur personnel…).
#   docker build -t medimcom .                       # sans recherche par le sens (léger, ~150 Mo de mémoire)
#   docker build --build-arg VECTEURS=1 -t medimcom .   # avec fastembed (recherche par le sens, ~1 Go de mémoire)
# La base (base_v2) n'est PAS dans l'image : montez-la (-v /chemin/base_v2:/app/base_v2) ou copiez-la sur le serveur.
# Les clés ne sont jamais dans l'image : passez XAI_API_KEY et MEDIMCOM_JETON en variables d'environnement (secrets).
FROM python:3.12-slim
ARG VECTEURS=0
WORKDIR /app
COPY requirements-vecteurs.txt ./
RUN if [ "$VECTEURS" = "1" ]; then pip install --no-cache-dir -r requirements-vecteurs.txt; fi && pip install --no-cache-dir pypdf certifi
COPY . .
ENV MEDIMCOM_HOTE=0.0.0.0 PORT=8000 PYTHONUNBUFFERED=1
EXPOSE 8000
# MEDIMCOM_ARGS : options du serveur, ex. « --fournisseur xai --effort low --donnees-fictives »
CMD ["sh", "-c", "python interface/serveur.py --interface react $MEDIMCOM_ARGS"]
