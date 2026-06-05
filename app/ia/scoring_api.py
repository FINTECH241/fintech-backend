from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import date
from app.ia.features import construire_features, charger_clients
from app.ia.features import charger_transactions
from app.ia.scoring_model import scorer_client, mettre_a_jour_modele
from app.ia.monitoring import enregistrer_prediction, enregistrer_resultat_reel

router = APIRouter(prefix="/scoring", tags=["Scoring IA"])

clients = charger_clients()
tx_par_client = charger_transactions()


# Endpoint pour scorer un client
class FeedbackSchema(BaseModel):
    client_id: int
    a_fait_defaut: int  # 0 ou 1


# Endpoint pour scorer un client à une date donnée (optionnelle)
@router.get("/{client_id}")
def scorer(client_id: int, date_demande: str = None):
    if client_id not in clients:
        raise HTTPException(status_code=404, detail="Client introuvable")

    if not date_demande:
        date_demande = date.today().strftime("%Y-%m-%d")

    features = construire_features(client_id, clients, 
                                   tx_par_client, date_demande)
    resultat = scorer_client(features)
    resultat["client_id"] = client_id

    # Enregistre pour le monitoring
    enregistrer_prediction(client_id, features, resultat)

    return resultat


# Endpoint pour recevoir le feedback du résultat réel 
# et mettre à jour le modèle
@router.post("/feedback")
def feedback(data: FeedbackSchema):
    if data.client_id not in clients:
        raise HTTPException(status_code=404, detail="Client introuvable")

    features = construire_features(data.client_id, clients, 
                                   tx_par_client)
    mettre_a_jour_modele(features, data.a_fait_defaut)

    # Enregistre le résultat réel
    enregistrer_resultat_reel(data.client_id, data.a_fait_defaut)

    return {
        "message": "Modèle mis à jour avec succès",
        "client_id": data.client_id,
        "resultat": "défaut" if data.a_fait_defaut else "remboursé"
    }

