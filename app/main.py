"""
Point d'entrée de l'API FINTECH Gabon.
Lancer avec :  uvicorn app.main:app --reload
"""
from fastapi import FastAPI

from app.database import Base, engine
from app import models  # noqa (import nécessaire pour enregistrer les tables)
from app.ia.scoring_api import router as scoring_router  # ← AJOUTER
from app.ia.monitoring_api import router as monitoring_router  # ← AJOUTER

# Crée les tables dans PostgreSQL si elles n'existent pas encore.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FINTECH Gabon — API",
    description="Plateforme de microfinance et crowdfunding avec scoring IA.",
    version="0.1.0",
)

app.include_router(scoring_router)  # ← AJOUTER
app.include_router(monitoring_router)  # ← AJOUTER


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