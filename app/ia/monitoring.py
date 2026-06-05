import json
import os
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
CHEMIN_LOGS = os.path.join(BASE_DIR, "data", "monitoring_logs.json")


# Charger les clients et les transactions (même code que dans features.py)
def charger_logs():
    """Charge l'historique des prédictions."""
    if os.path.exists(CHEMIN_LOGS):
        with open(CHEMIN_LOGS, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


# Sauvegarder l'historique des prédictions
def sauvegarder_logs(logs):
    """Sauvegarde l'historique des prédictions."""
    with open(CHEMIN_LOGS, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


# Enregistrer chaque prédiction pour traçabilité
def enregistrer_prediction(client_id, features, resultat):
    """
    Enregistre chaque prédiction pour traçabilité.
    Appelé à chaque scoring d'un client.
    """
    logs = charger_logs()
    logs.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "client_id": client_id,
        "score": resultat["score"],
        "decision": resultat["decision"],
        "risque": resultat["risque"],
        "proba_defaut": resultat["proba_defaut"],
        "features": features,
        "resultat_reel": None,  # rempli plus tard via feedback
    })
    sauvegarder_logs(logs)


# Enregistrer le résultat réel du crédit (remboursement ou défaut)
def enregistrer_resultat_reel(client_id, a_fait_defaut):
    """
    Met à jour le log avec le résultat réel du crédit.
    Appelé quand le client rembourse ou fait défaut.
    """
    logs = charger_logs()
    # On met à jour la dernière prédiction de ce client
    for log in reversed(logs):
        if log["client_id"] == client_id and log["resultat_reel"] is None:
            log["resultat_reel"] = a_fait_defaut
            break
    sauvegarder_logs(logs)


# Calcul des métriques de performance du modèle
def calculer_metriques():
    """
    Calcule les métriques de performance du modèle
    sur les prédictions qui ont un résultat réel.
    """
    logs = charger_logs()

    # Seulement les logs avec résultat réel
    evalues = [log for log in logs if log["resultat_reel"] is not None]

    if not evalues:
        return {
            "message": "Pas encore de résultats réels disponibles",
            "total_predictions": len(logs),
            "total_evalues": 0,
        }

    # Précision
    corrects = 0
    for log in evalues:
        predit_defaut = 1 if log["score"] < 70 else 0
        if predit_defaut == log["resultat_reel"]:
            corrects += 1
    precision = round(corrects / len(evalues) * 100, 2)

    # Distribution des décisions
    decisions = {"ACCORDÉ": 0, "À ÉTUDIER": 0, "REFUSÉ": 0}
    for log in logs:
        d = log["decision"]
        if d in decisions:
            decisions[d] += 1

    # Taux de défaut réel vs prédit
    taux_defaut_reel = round(
        sum(log["resultat_reel"] for log in evalues) / len(evalues) * 100, 2
    )
    taux_defaut_predit = round(
        sum(log["proba_defaut"] for log in evalues) / len(evalues), 2
    )

    # Score moyen
    score_moyen = round(sum(log["score"] for log in logs) / len(logs), 2)

    return {
        "total_predictions": len(logs),
        "total_evalues": len(evalues),
        "precision_modele": f"{precision}%",
        "score_moyen": score_moyen,
        "taux_defaut_reel": f"{taux_defaut_reel}%",
        "taux_defaut_predit": f"{taux_defaut_predit}%",
        "distribution_decisions": decisions,
        "alerte_drift": abs(taux_defaut_reel - taux_defaut_predit) > 10,
    }
    
