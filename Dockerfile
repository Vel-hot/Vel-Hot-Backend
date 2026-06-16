# Vél'hot Backend — image de production pour ECS Fargate
FROM python:3.11-slim AS base

# Dépendances système minimales pour psycopg2 (libpq) et compilation des wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installer les dépendances Python d'abord (cache Docker si requirements.txt
# ne change pas, évite de réinstaller à chaque modification de code)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code de l'application
COPY app/ ./app/
COPY main.py .

# Utilisateur non-root pour la sécurité (bonne pratique conteneurs)
RUN useradd --create-home --shell /bin/bash velhot \
    && chown -R velhot:velhot /app
USER velhot

EXPOSE 8000

# Health check — utilisé par ECS pour vérifier que le conteneur répond
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

# Pas de --reload en production : un seul process géré par ECS,
# le scaling horizontal se fait via le nombre de tâches ECS, pas via workers.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
