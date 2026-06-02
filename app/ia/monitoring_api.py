from fastapi import APIRouter
from app.ia.monitoring import calculer_metriques, charger_logs

router = APIRouter(prefix="/monitoring", tags=["Monitoring IA"])


# Endpoint pour récupérer les métriques de performance du modèle
@router.get("/metriques")
def metriques():
    """
    Retourne les métriques de performance du modèle en temps réel.
    """
    return calculer_metriques()


# Endpoint pour récupérer l'historique des prédictions et des défauts réels
@router.get("/historique")
def historique(limit: int = 20):
    """
    Retourne les dernières prédictions effectuées.
    """
    logs = charger_logs()
    logs_tries = sorted(logs, key=lambda x: x["timestamp"], reverse=True)
    return {
        "total": len(logs),
        "predictions": logs_tries[:limit],
    }


# Endpoint pour vérifier les alertes basées sur les métriques
@router.get("/alertes")
def alertes():
    """
    Vérifie si le modèle montre des signes de dégradation.
    """
    metriques = calculer_metriques()
    alertes = []

    if metriques.get("alerte_drift"):
        alertes.append({
            "type": "DRIFT",
            "message": "Ecart important entre défauts prédits et réels" 
            "— possible dérive du modèle",   
            "niveau": "CRITIQUE"
        })

    if isinstance(metriques.get("score_moyen"), float):
        if metriques["score_moyen"] < 55:
            alertes.append({
                "type": "SCORE_BAS",
                "message": "Score moyen trop bas — modèle trop restrictif",
                "niveau": "AVERTISSEMENT"
            })
        if metriques["score_moyen"] > 85:
            alertes.append({
                "type": "SCORE_ELEVE",
                "message": "Score moyen trop élevé — modèle trop permissif",
                "niveau": "AVERTISSEMENT"
            })

    if not alertes:
        alertes.append({
            "type": "OK",
            "message": "Modèle stable — aucune anomalie détectée",
            "niveau": "OK"
        })

    return {"alertes": alertes}