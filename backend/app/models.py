"""ORM models: Team and Match."""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .ratings import BASE_RATING


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    elo_rating: Mapped[float] = mapped_column(Float, default=BASE_RATING)
    matches_played: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    draws: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    goals_for: Mapped[int] = mapped_column(Integer, default=0)
    goals_against: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    home_team: Mapped[str] = mapped_column(String, index=True)
    away_team: Mapped[str] = mapped_column(String, index=True)
    home_score: Mapped[int] = mapped_column(Integer)
    away_score: Mapped[int] = mapped_column(Integer)
    tournament: Mapped[str] = mapped_column(String, default="Friendly")
    neutral: Mapped[bool] = mapped_column(Boolean, default=False)
    home_elo_before: Mapped[float] = mapped_column(Float)
    away_elo_before: Mapped[float] = mapped_column(Float)
    home_elo_after: Mapped[float] = mapped_column(Float)
    away_elo_after: Mapped[float] = mapped_column(Float)
