"""Models for the BoardOil API."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CardType:
    """Represents a card type in a board."""

    id: int
    name: str


@dataclass
class Column:
    """Represents a column in a board."""

    id: int
    title: str


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
