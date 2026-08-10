"""Import tập trung để mọi model được đăng ký vào Base.metadata."""

from app.models.base import Base
from app.models.jobs import AgentCache, IngestionCandidate, IngestionJob
from app.models.lexical import (
    ConfusionCluster,
    ConfusionClusterMember,
    ExampleSentence,
    LexicalItem,
    Mnemonic,
    Sense,
)
from app.models.production import ProductionAttempt
from app.models.srs import Card, ReviewLog
from app.models.user import Deck, User

__all__ = [
    "Base",
    "AgentCache",
    "Card",
    "ConfusionCluster",
    "ConfusionClusterMember",
    "Deck",
    "ExampleSentence",
    "IngestionCandidate",
    "IngestionJob",
    "LexicalItem",
    "Mnemonic",
    "ProductionAttempt",
    "ReviewLog",
    "Sense",
    "User",
]
