"""
Connexion à la base de données PostgreSQL.
Utilise SQLAlchemy comme ORM (Object-Relational Mapping).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

# Le "moteur" gère la connexion à PostgreSQL
engine = create_engine(settings.database_url, echo=False)

# Fabrique de sessions : chaque requête utilise sa propre session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Classe de base dont héritent tous les modèles (tables)
Base = declarative_base()


def get_db():
    """
    Fournit une session de base de données à une route FastAPI,
    puis la ferme automatiquement après la requête.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
