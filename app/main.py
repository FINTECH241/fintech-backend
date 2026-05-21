"""
Point d'entrée de l'API FINTECH Gabon.
Lancer avec :  uvicorn app.main:app --reload
"""
from fastapi import FastAPI

from app.database import Base, engine
from app import models  # noqa: F401  (import nécessaire pour enregistrer les tables)

# Crée les tables dans PostgreSQL si elles n'existent pas encore.
# NB : pour un vrai projet, on utilisera Alembic (migrations) plus tard.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FINTECH Gabon — API",
    description="Plateforme de microfinance et crowdfunding avec scoring IA.",
    version="0.1.0",
)


@app.get("/")
def racine():
    """Route d'accueil — vérifie que l'API tourne."""
    return {
        "message": "API FINTECH Gabon opérationnelle.",
        "documentation": "/docs",
    }


@app.get("/health")
def sante():
    """Route de surveillance (monitoring / disponibilité — CDC §4.4.3)."""
    return {"status": "ok"}
