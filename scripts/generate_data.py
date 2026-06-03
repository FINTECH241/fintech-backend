"""
GÉNÉRATION DE DONNÉES SIMULÉES POUR LE SCORING IA
==================================================

Ce script crée un jeu de données réaliste de "clients fictifs" du Gabon,
afin d'entraîner et tester le premier modèle de scoring de crédit.

Pourquoi des données simulées ?
  Au démarrage, on n'a pas encore de vrais clients. Pour développer et
  tester le moteur IA (CDC §4.5), on génère des profils crédibles
  reproduisant les comportements observés sur le terrain gabonais.

Le script produit :
  - data/clients.csv        : profils des clients
  - data/transactions.csv   : historique Mobile Money de chaque client
  - data/loans.csv          : crédits passés + résultat (remboursé ou défaut)
                              => c'est la "cible" que le modèle IA apprendra.

Lancer avec :  python scripts/generate_data.py
"""
import os
import random
import csv
from datetime import datetime, timedelta

from faker import Faker

# Faker en français pour des noms cohérents
fake = Faker("fr_FR")

# Graine fixe => mêmes données à chaque exécution (reproductibilité)
random.seed(42)
Faker.seed(42)

# ------------------------------------------------------------------
# PARAMÈTRES — modifiez ces valeurs selon vos besoins
# ------------------------------------------------------------------
NB_CLIENTS = 1000          # nombre de clients à générer
DOSSIER_SORTIE = "data"    # dossier où enregistrer les CSV

VILLES_GABON = [
    "Libreville", "Port-Gentil", "Franceville", "Oyem",
    "Moanda", "Lambaréné", "Mouila", "Tchibanga",
]

METIERS = [
    "Commerçant(e)", "Artisan(e)", "Chauffeur de taxi", "Couturier(ère)",
    "Vendeur(se) au marché", "Coiffeur(se)", "Mécanicien(ne)",
    "Restaurateur(trice)", "Agriculteur(trice)", "Petit éleveur",
]

OPERATEURS = ["airtel", "moov", "gimac"]


# ==================================================================
# 1. GÉNÉRATION DES CLIENTS
# ==================================================================

def generer_clients(n):
    """Crée n profils de clients fictifs avec des caractéristiques réalistes."""
    clients = []
    for i in range(1, n + 1):
        # Revenu mensuel : la majorité gagne peu (économie informelle)
        revenu = int(random.lognormvariate(11.5, 0.6))   # ~ 50k à 500k FCFA
        revenu = max(30_000, min(revenu, 2_000_000))

        anciennete_mois = random.randint(1, 60)   # ancienneté Mobile Money

        client = {
            "client_id": i,
            "nom": fake.name(),
            "ville": random.choice(VILLES_GABON),
            "age": random.randint(18, 65),
            "metier": random.choice(METIERS),
            "revenu_mensuel_fcfa": revenu,
            "anciennete_mobile_money_mois": anciennete_mois,
            "operateur_principal": random.choice(OPERATEURS),
        }
        clients.append(client)
    return clients


# ==================================================================
# 2. GÉNÉRATION DES TRANSACTIONS MOBILE MONEY
# ==================================================================

def generer_transactions(clients):
    """
    Pour chaque client, génère un historique de transactions Mobile Money.
    Ces données sont la "donnée alternative" clé du scoring (CDC §4.5.3).
    """
    transactions = []
    tx_id = 1
    types = ["depot", "retrait", "paiement_facture", "achat_credit", "transfert"]

    for client in clients:
        # Plus le client est ancien et a un bon revenu, plus il transige
        base = 5 + client["anciennete_mobile_money_mois"] // 2
        nb_tx = random.randint(base, base + 40)

        for _ in range(nb_tx):
            jours_passe = random.randint(0, 180)
            date_tx = datetime.now() - timedelta(days=jours_passe)

            # Montant corrélé au revenu du client
            montant = int(random.uniform(0.02, 0.4) * client["revenu_mensuel_fcfa"])
            montant = max(500, montant)

            transactions.append({
                "transaction_id": tx_id,
                "client_id": client["client_id"],
                "type": random.choice(types),
                "montant_fcfa": montant,
                "operateur": client["operateur_principal"],
                "date": date_tx.strftime("%Y-%m-%d"),
            })
            tx_id += 1
    return transactions


# ==================================================================
# 3. GÉNÉRATION DES CRÉDITS PASSÉS (avec la cible à prédire)
# ==================================================================

def calculer_probabilite_defaut(client, nb_transactions):
    """
    Calcule une probabilité de défaut "réaliste" en fonction du profil.
    => C'est volontairement basé sur des règles logiques, pour que le
       modèle IA ait quelque chose de cohérent à apprendre.

    Facteurs qui RÉDUISENT le risque :
      - revenu élevé
      - ancienneté Mobile Money importante
      - activité transactionnelle régulière
    """
    proba = 0.35  # risque de base

    # Revenu : un bon revenu réduit le risque
    if client["revenu_mensuel_fcfa"] > 300_000:
        proba -= 0.15
    elif client["revenu_mensuel_fcfa"] < 80_000:
        proba += 0.15

    # Ancienneté : un historique long inspire confiance
    if client["anciennete_mobile_money_mois"] > 36:
        proba -= 0.12
    elif client["anciennete_mobile_money_mois"] < 6:
        proba += 0.12

    # Activité : beaucoup de transactions = client actif et stable
    if nb_transactions > 35:
        proba -= 0.10
    elif nb_transactions < 12:
        proba += 0.10

    # Âge : les très jeunes sont légèrement plus risqués
    if client["age"] < 25:
        proba += 0.05

    # Un peu de hasard pour le réalisme
    proba += random.uniform(-0.08, 0.08)

    # On garde la probabilité entre 2 % et 95 %
    return max(0.02, min(proba, 0.95))


def generer_credits(clients, transactions):
    """
    Génère un crédit passé pour ~70 % des clients, avec son résultat.
    La colonne 'a_fait_defaut' est la CIBLE que le modèle IA apprendra.
    """
    # Compter les transactions par client
    nb_tx_par_client = {}
    for tx in transactions:
        cid = tx["client_id"]
        nb_tx_par_client[cid] = nb_tx_par_client.get(cid, 0) + 1

    credits = []
    credit_id = 1

    for client in clients:
        # Tous les clients n'ont pas déjà eu un crédit
        if random.random() > 0.70:
            continue

        cid = client["client_id"]
        nb_tx = nb_tx_par_client.get(cid, 0)

        # Montant demandé : proportionnel au revenu
        montant = int(random.uniform(0.3, 2.5) * client["revenu_mensuel_fcfa"])
        montant = max(25_000, min(montant, 1_500_000))

        proba_defaut = calculer_probabilite_defaut(client, nb_tx)
        # Tirage au sort : le client a-t-il fait défaut ?
        a_fait_defaut = 1 if random.random() < proba_defaut else 0

        credits.append({
            "credit_id": credit_id,
            "client_id": cid,
            "montant_demande_fcfa": montant,
            "duree_mois": random.choice([3, 6, 9, 12]),
            "nb_transactions_30j": nb_tx,
            "a_fait_defaut": a_fait_defaut,   # <-- CIBLE pour l'IA
        })
        credit_id += 1
    return credits


# ==================================================================
# 4. SAUVEGARDE EN CSV
# ==================================================================

def sauvegarder_csv(donnees, chemin):
    """Écrit une liste de dictionnaires dans un fichier CSV."""
    if not donnees:
        print(f"  ⚠ Aucune donnée pour {chemin}")
        return
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=donnees[0].keys())
        writer.writeheader()
        writer.writerows(donnees)
    print(f"  ✓ {len(donnees):>5} lignes → {chemin}")


# ==================================================================
# PROGRAMME PRINCIPAL
# ==================================================================

def main():
    print("=" * 55)
    print("  GÉNÉRATION DES DONNÉES SIMULÉES — FINTECH GABON")
    print("=" * 55)

    # Créer le dossier de sortie si besoin
    os.makedirs(DOSSIER_SORTIE, exist_ok=True)

    print(f"\n[1/3] Génération de {NB_CLIENTS} clients...")
    clients = generer_clients(NB_CLIENTS)

    print("[2/3] Génération des transactions Mobile Money...")
    transactions = generer_transactions(clients)

    print("[3/3] Génération de l'historique de crédits...")
    credits = generer_credits(clients, transactions)

    print("\nSauvegarde des fichiers :")
    sauvegarder_csv(clients, os.path.join(DOSSIER_SORTIE, "clients.csv"))
    sauvegarder_csv(transactions, os.path.join(DOSSIER_SORTIE, "transactions.csv"))
    sauvegarder_csv(credits, os.path.join(DOSSIER_SORTIE, "loans.csv"))

    # Petit résumé statistique
    nb_defauts = sum(c["a_fait_defaut"] for c in credits)
    taux = (nb_defauts / len(credits) * 100) if credits else 0
    print("\n" + "-" * 55)
    print("  RÉSUMÉ")
    print("-" * 55)
    print(f"  Clients          : {len(clients)}")
    print(f"  Transactions     : {len(transactions)}")
    print(f"  Crédits accordés : {len(credits)}")
    print(f"  Taux de défaut   : {taux:.1f} %  ({nb_defauts} défauts)")
    print("\n✅ Terminé. Données prêtes pour l'entraînement du modèle IA.")


if __name__ == "__main__":
    main()
