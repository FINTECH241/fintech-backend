from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.session import Base, engine
from app.api.v1.endpoints import auth

# Créer les tables (à remplacer par Alembic en production)
# Import des models pour que SQLAlchemy les découvre
from app.models import user, token, audit  # noqa: F401

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Plateforme FinTech Gabon — Microfinance & Crowdfunding",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENVIRONMENT == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")


@app.get("/health", tags=["Système"])
def health():
    return {"status": "ok", "version": settings.VERSION}
