# FINTECH Gabon — Plateforme d'Inclusion Financière Augmentée par l'IA

Plateforme digitale (Web & Mobile) de **microfinance de 2ème catégorie (EMF)** et de
**financement participatif (crowdfunding)**, avec un moteur de **scoring de crédit basé sur l'IA**,
adaptée aux réalités du Gabon et de la zone CEMAC.

> *« Votre potentiel est notre seule garantie. »*

## Statut du projet

🚧 Phase de démarrage — MVP en construction.

## Stack technique

| Couche | Technologie |
|---|---|
| Backend API | Python + FastAPI |
| Base de données | PostgreSQL |
| Frontend Web | React.js (à venir) |
| Frontend Mobile | React Native (à venir) |
| Cache | Redis (à venir) |
| Modèle IA | scikit-learn (Random Forest / XGBoost) |

## Structure du dépôt

```
fintech-gabon/
├── app/                 # Code de l'application backend
│   ├── main.py          # Point d'entrée de l'API
│   ├── config.py        # Configuration (variables d'environnement)
│   ├── database.py      # Connexion à PostgreSQL
│   └── models.py        # Schéma de la base de données (tables)
├── scripts/
│   └── generate_data.py # Génération de données simulées pour l'IA
├── data/                # Données générées (non versionnées)
├── .env.example         # Modèle de configuration
├── requirements.txt     # Dépendances Python
└── .gitignore
```

## Installation (développement local)

### Prérequis
- Python 3.10 ou supérieur
- PostgreSQL 14 ou supérieur

### Étapes

```bash
# 1. Cloner le dépôt
git clone https://github.com/FINTECH241/fintech-backend.git
cd fintech-backend

# 2. Créer un environnement virtuel
python -m venv venv
# Windows :
venv\Scripts\activate
# macOS/Linux :
source venv/bin/activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer l'environnement
# Copier .env.example en .env et renseigner les valeurs
cp .env.example .env

# 5. Lancer l'API
uvicorn app.main:app --reload
```

L'API sera accessible sur http://localhost:8000
Documentation interactive : http://localhost:8000/docs

## Conventions d'équipe

- La branche `main` est protégée — aucun push direct, uniquement via Pull Request.
- Une branche par fonctionnalité : `feature/nom-de-la-fonctionnalite`.
- Le fichier `.env` ne doit **jamais** être commité (il contient des secrets).

## Confidentialité

Projet sous accord de confidentialité (MOU, Article 8). Dépôt privé.

---

© 2026 — Équipe fondatrice FINTECH Gabon
