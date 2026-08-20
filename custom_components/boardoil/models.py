"""Models for the BoardOil API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Me:
    """Represents a BoardOil account."""

    id: int
    username: str
    display_name: str
    role: str


@dataclass
class Version:
    """Represents a BoardOil version."""

    version: str
    channel: str
    build: str
    commit: str


@dataclass
class BoardSummary:
    """Represents a board summary."""

    id: int
    name: str
    description: str


@dataclass
class Board:
    """Represents a board."""

    id: int
    name: str
    description: str
    columns: list[ColumnWithCards]


@dataclass
class Column:
    """Represents a column."""

    id: int
    title: str


@dataclass
class CardType:
    """Represents a card type in a board."""

    id: int
    name: str


@dataclass
class ColumnWithCards:
    """Represents a column with it's cards in a board."""

    id: int
    title: str
    cards: list[Card]


@dataclass
class Member:
    """Represents a user in a board."""

    id: int
    username: str
    display_name: str


@dataclass
class Card:
    """Represents a card."""

    id: int
    card_type_id: int
    card_type_name: str
    card_type_emoji: str
    title: str
    description: str
    sort_key: str
    tag_names: list[str]
    updated_at_utc: str
    assigned_user_id: int | None
    assigned_user_display_name: str | None
    external_url: str | None
    slick_id: int | None
    slick_name: str | None
    raw_data: dict[str, Any]


@dataclass
class Tag:
    """Represents a tag in a board."""

    id: int
    name: str


@dataclass
class Slick:
    """Represents a slick in a board."""

    id: int
    name: str
