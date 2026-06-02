import csv
from datetime import datetime


# Charger les clients et leurs caractéristiques
def charger_clients(chemin="data/clients.csv"):
    clients = {}
    with open(chemin, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = int(row["client_id"])
            clients[cid] = {
                "age": int(row["age"]),
                "revenu": int(row["revenu_mensuel_fcfa"]),
                "anciennete": int(row["anciennete_mobile_money_mois"]),
            }
    return clients


# Charger les transactions et les organiser par client
def charger_transactions(chemin="data/transactions.csv"):
    tx_par_client = {}
    with open(chemin, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = int(row["client_id"])
            if cid not in tx_par_client:
                tx_par_client[cid] = []
            tx_par_client[cid].append({
                "montant": int(row["montant_fcfa"]),
                "date": row["date"],
            })
    return tx_par_client


# Extraction de features temporelles à partir de la date de demande
def extraire_features_temporelles(date_str):
    date = datetime.strptime(date_str, "%Y-%m-%d")
    return {
        "mois": date.month,
        "est_fin_annee": 1 if date.month in [11, 12, 1] else 0,
        "est_rentree": 1 if date.month in [8, 9] else 0,
        "est_debut_mois": 1 if date.day <= 5 else 0,
        "est_fin_mois": 1 if date.day >= 25 else 0,
    }


# Placeholder pour les fonctions de monitoring
def construire_features(client_id, clients, tx_par_client, date_demande=None):
    client = clients.get(client_id, {})
    transactions = tx_par_client.get(client_id, [])

    # Filtrer uniquement les transactions AVANT la date de demande
    if date_demande:
        transactions = [
            t for t in transactions
            if t["date"] <= date_demande
        ]

    nb_tx = len(transactions)
    montant_moyen = (
        sum(t["montant"] for t in transactions) / nb_tx if nb_tx > 0 else 0
    )
    ratio = montant_moyen / client["revenu"] if client.get("revenu") else 0

    features = {
        "age": client.get("age", 0),
        "revenu": client.get("revenu", 0),
        "anciennete": client.get("anciennete", 0),
        "nb_transactions": nb_tx,
        "montant_moyen_tx": montant_moyen,
        "ratio_depenses_revenus": ratio,
    }

    if date_demande:
        features.update(extraire_features_temporelles(date_demande))

    return features

