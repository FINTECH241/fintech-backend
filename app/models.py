"""
SCHÉMA DE LA BASE DE DONNÉES — Plateforme Fintech Gabon
=========================================================

Ce fichier définit toutes les tables, conçues d'après le cahier des charges :
  - Acteurs : Client, Investisseur, Administrateur
  - Microcrédit (EMF 2ème catégorie)
  - Financement participatif (crowdfunding)
  - Transactions Mobile Money
  - Scoring de crédit par IA

Convention : tous les montants sont en FCFA (entiers, pas de centimes).
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Boolean,
    DateTime, ForeignKey, Enum, Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


def now_utc():
    """Horodatage UTC — utile pour l'audit et la traçabilité (CDC §4.7.4)."""
    return datetime.now(timezone.utc)


# ==================================================================
# ÉNUMÉRATIONS (valeurs contrôlées)
# ==================================================================

class UserRole(str, enum.Enum):
    """Rôles du système (CDC §4.3.1)."""
    CLIENT = "client"            # Emprunteur / Porteur de projet
    INVESTOR = "investor"        # Investisseur (diaspora / local)
    ADMIN = "admin"              # Finance / Risque / Support


class KYCStatus(str, enum.Enum):
    """État de la vérification d'identité (e-KYC)."""
    PENDING = "pending"          # En attente
    VERIFIED = "verified"        # Vérifié
    REJECTED = "rejected"        # Rejeté


class LoanStatus(str, enum.Enum):
    """Cycle de vie d'une demande de microcrédit (CDC §4.3.3)."""
    SUBMITTED = "submitted"      # Demande soumise
    SCORING = "scoring"          # Analyse IA en cours
    APPROVED = "approved"        # Accordé
    REJECTED = "rejected"        # Refusé
    DISBURSED = "disbursed"      # Décaissé (fonds envoyés)
    REPAYING = "repaying"        # Remboursement en cours
    REPAID = "repaid"            # Soldé
    DEFAULTED = "defaulted"      # En défaut de paiement


class ProjectStatus(str, enum.Enum):
    """État d'une campagne de crowdfunding."""
    DRAFT = "draft"
    ACTIVE = "active"            # Collecte en cours
    FUNDED = "funded"            # Objectif atteint
    CLOSED = "closed"            # Clôturée sans succès


class TxType(str, enum.Enum):
    """Type de mouvement financier."""
    DEPOSIT = "deposit"          # Dépôt (entrée d'argent)
    WITHDRAWAL = "withdrawal"    # Retrait
    LOAN_DISBURSE = "loan_disburse"   # Décaissement de crédit
    LOAN_REPAY = "loan_repay"         # Remboursement de crédit
    INVESTMENT = "investment"         # Investissement dans un projet


class MobileOperator(str, enum.Enum):
    """Opérateurs Mobile Money au Gabon (CDC §3.4)."""
    AIRTEL = "airtel"
    MOOV = "moov"
    GIMAC = "gimac"


# ==================================================================
# TABLE : UTILISATEURS
# ==================================================================

class User(Base):
    """
    Tout utilisateur de la plateforme (client, investisseur ou admin).
    Un seul modèle, différencié par le champ `role`.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    # Identité
    full_name = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    role = Column(Enum(UserRole), default=UserRole.CLIENT, nullable=False)

    # KYC / conformité (CDC §4.7.2)
    kyc_status = Column(Enum(KYCStatus), default=KYCStatus.PENDING, nullable=False)
    id_document_type = Column(String(50), nullable=True)   # CNI, passeport...
    id_document_number = Column(String(100), nullable=True)

    # Données socio-économiques (utiles pour le scoring IA)
    city = Column(String(100), nullable=True)
    occupation = Column(String(100), nullable=True)         # commerçant, artisan...
    monthly_income_fcfa = Column(BigInteger, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=now_utc)

    # Relations
    loans = relationship("Loan", back_populates="borrower")
    projects = relationship("Project", back_populates="owner")
    transactions = relationship("Transaction", back_populates="user")
    investments = relationship("Investment", back_populates="investor")

    def __repr__(self):
        return f"<User {self.id} {self.full_name} ({self.role.value})>"


# ==================================================================
# TABLE : MICROCRÉDITS
# ==================================================================

class Loan(Base):
    """
    Une demande de microcrédit, du dépôt au remboursement (CDC §4.3.3).
    """
    __tablename__ = "loans"

    id = Column(Integer, primary_key=True, index=True)
    borrower_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Montants (FCFA)
    amount_requested = Column(BigInteger, nullable=False)
    amount_approved = Column(BigInteger, nullable=True)
    interest_rate = Column(Float, nullable=True)        # ex : 0.05 = 5 %
    duration_months = Column(Integer, nullable=False)

    purpose = Column(String(255), nullable=True)        # motif (ex : "stock")

    status = Column(Enum(LoanStatus), default=LoanStatus.SUBMITTED, nullable=False)

    # Lien vers le score IA ayant servi à la décision
    credit_score_id = Column(Integer, ForeignKey("credit_scores.id"), nullable=True)

    # Suivi du remboursement
    amount_repaid = Column(BigInteger, default=0)

    submitted_at = Column(DateTime(timezone=True), default=now_utc)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    disbursed_at = Column(DateTime(timezone=True), nullable=True)

    # Relations
    borrower = relationship("User", back_populates="loans")
    credit_score = relationship("CreditScore", back_populates="loan")

    def __repr__(self):
        return f"<Loan {self.id} {self.amount_requested} FCFA ({self.status.value})>"


# ==================================================================
# TABLE : SCORE DE CRÉDIT IA
# ==================================================================

class CreditScore(Base):
    """
    Résultat du moteur de scoring IA pour un utilisateur (CDC §4.5).
    Conserve aussi les facteurs explicatifs (Explainable AI — CDC §4.5.4).
    """
    __tablename__ = "credit_scores"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Score de 0 à 1000 (plus c'est haut, moins le risque est élevé)
    score = Column(Integer, nullable=False)
    risk_level = Column(String(20), nullable=False)     # faible / moyen / élevé
    default_probability = Column(Float, nullable=False) # 0.0 à 1.0

    # Modèle utilisé (traçabilité / gouvernance IA)
    model_version = Column(String(50), default="v0-baseline")

    # Facteurs explicatifs (Explainable AI) — stockés en texte JSON
    explanation = Column(Text, nullable=True)

    computed_at = Column(DateTime(timezone=True), default=now_utc)

    # Relation
    loan = relationship("Loan", back_populates="credit_score", uselist=False)

    def __repr__(self):
        return f"<CreditScore {self.id} score={self.score} ({self.risk_level})>"


# ==================================================================
# TABLE : PROJETS DE CROWDFUNDING
# ==================================================================

class Project(Base):
    """
    Une campagne de financement participatif portée par un client.
    """
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)       # agriculture, commerce...

    # Montants (FCFA)
    goal_amount = Column(BigInteger, nullable=False)
    amount_raised = Column(BigInteger, default=0)

    status = Column(Enum(ProjectStatus), default=ProjectStatus.DRAFT, nullable=False)

    created_at = Column(DateTime(timezone=True), default=now_utc)
    deadline = Column(DateTime(timezone=True), nullable=True)

    # Relations
    owner = relationship("User", back_populates="projects")
    investments = relationship("Investment", back_populates="project")

    def __repr__(self):
        return f"<Project {self.id} '{self.title}' ({self.status.value})>"


# ==================================================================
# TABLE : INVESTISSEMENTS
# ==================================================================

class Investment(Base):
    """
    Un investissement réalisé par un investisseur dans un projet.
    Table de liaison entre User (investisseur) et Project.
    """
    __tablename__ = "investments"

    id = Column(Integer, primary_key=True, index=True)
    investor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    amount = Column(BigInteger, nullable=False)         # FCFA
    invested_at = Column(DateTime(timezone=True), default=now_utc)

    # Relations
    investor = relationship("User", back_populates="investments")
    project = relationship("Project", back_populates="investments")

    def __repr__(self):
        return f"<Investment {self.id} {self.amount} FCFA>"


# ==================================================================
# TABLE : TRANSACTIONS (Mobile Money & flux internes)
# ==================================================================

class Transaction(Base):
    """
    Tout mouvement d'argent sur la plateforme.
    Sert aussi de source de données alternative pour le scoring IA.
    """
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    tx_type = Column(Enum(TxType), nullable=False)
    amount = Column(BigInteger, nullable=False)         # FCFA

    operator = Column(Enum(MobileOperator), nullable=True)  # si Mobile Money
    reference = Column(String(100), unique=True, nullable=True)  # réf. opérateur

    # Lien optionnel vers un crédit ou un projet concerné
    related_loan_id = Column(Integer, ForeignKey("loans.id"), nullable=True)
    related_project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), default=now_utc)

    # Relation
    user = relationship("User", back_populates="transactions")

    def __repr__(self):
        return f"<Transaction {self.id} {self.tx_type.value} {self.amount} FCFA>"
