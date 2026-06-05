from river import linear_model, metrics, preprocessing, optim
import pickle
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
CHEMIN_MODELE = os.path.join(BASE_DIR, "data", "scoring_model.pkl")


# Création du modèle de scoring
def creer_modele():
    """Crée un pipeline River avec Logistic Regression."""
    modele = (
        preprocessing.StandardScaler() |
        linear_model.LogisticRegression(
            optimizer=optim.SGD(0.01)
        )
    )
    return modele


# Sauvegarde et chargement du modèle
def sauvegarder_modele(modele):
    """Sauvegarde le modèle sur disque."""
    with open(CHEMIN_MODELE, "wb") as f:
        pickle.dump(modele, f)


# Chargement du modèle existant ou création d'un nouveau si pas trouvé
def charger_modele():
    """Charge le modèle existant ou en crée un nouveau."""
    if os.path.exists(CHEMIN_MODELE):
        with open(CHEMIN_MODELE, "rb") as f:
            return pickle.load(f)
    return creer_modele()


# Scoring d'un client à partir de ses features
def scorer_client(features: dict) -> dict:
    """Prédit le risque de défaut d'un client."""
    modele = charger_modele()
    proba = modele.predict_proba_one(features)
    proba_defaut = proba.get(1, 0.5)
    score = round((1 - proba_defaut) * 100)

    if score >= 70:
        decision = "ACCORDÉ"
        risque = "FAIBLE"
    elif score >= 50:
        decision = "À ÉTUDIER"
        risque = "MOYEN"
    else:
        decision = "REFUSÉ"
        risque = "ÉLEVÉ"

    return {
        "score": score,
        "decision": decision,
        "risque": risque,
        "proba_defaut": round(proba_defaut * 100, 1),
    }


# Mise à jour du modèle avec le résultat réel (apprentissage en ligne)
def mettre_a_jour_modele(features: dict, a_fait_defaut: int):
    """Met à jour le modèle avec le résultat réel — apprentissage en ligne."""
    modele = charger_modele()
    modele.learn_one(features, a_fait_defaut)
    sauvegarder_modele(modele)


# Entraînement du modèle sur l'historique avec séparation train/test
def entrainer_sur_historique(clients, tx_par_client, 
                             loans_chemin="data/loans.csv"):
    """
    Entraîne le modèle sur l'historique.
    - Trié par date_demande (ordre chronologique) 
    - 80% train / 20% test 
    - Transactions filtrées avant date_demande 
    """
    import csv
    from app.ia.features import construire_features

    # Charger et trier par date chronologique
    credits = []
    with open(loans_chemin, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            credits.append(row)

    credits.sort(key=lambda x: x["date_demande"])

    # Séparation 80% train / 20% test
    split = int(len(credits) * 0.80)
    train = credits[:split]
    test = credits[split:]

    print(f"  Train : {len(train)} crédits")
    print(f"  Test  : {len(test)} crédits")

    # Entraînement sur le train
    modele = creer_modele()
    for row in train:
        cid = int(row["client_id"])
        features = construire_features(
            cid, clients, tx_par_client, row["date_demande"]
        )
        modele.learn_one(features, int(row["a_fait_defaut"]))

    # Évaluation sur le test — données jamais vues 
    # et transactions filtrées avant date_demande
    metric = metrics.Accuracy()
    for row in test:
        cid = int(row["client_id"])
        features = construire_features(
            cid, clients, tx_par_client, row["date_demande"]
        )
        cible = int(row["a_fait_defaut"])
        prediction = modele.predict_one(features)
        if prediction is not None:
            metric.update(cible, prediction)

    sauvegarder_modele(modele)
    print(f"Modèle entraîné — Précision réelle : {metric.get():.2%}")
    return modele

