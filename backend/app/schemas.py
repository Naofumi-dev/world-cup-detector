"""Pydantic request/response models for the API."""
from __future__ import annotations

from datetime import date as date_type

from pydantic import BaseModel, ConfigDict, Field, computed_field


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    elo_rating: float
    matches_played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int

    @computed_field
    @property
    def win_pct(self) -> float:
        return round(self.wins / self.matches_played, 3) if self.matches_played else 0.0


class RankedTeam(TeamOut):
    rank: int


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date_type
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    tournament: str
    neutral: bool


class MatchCreate(BaseModel):
    home_team: str = Field(min_length=1)
    away_team: str = Field(min_length=1)
    home_score: int = Field(ge=0)
    away_score: int = Field(ge=0)
    tournament: str = "FIFA World Cup"
    neutral: bool = True
    date: date_type | None = None


class Probabilities(BaseModel):
    home_win: float
    draw: float
    away_win: float


class PredictRequest(BaseModel):
    home: str = Field(min_length=1)
    away: str = Field(min_length=1)
    neutral: bool = True
    tournament: str = "FIFA World Cup"


class PredictResponse(BaseModel):
    home: str
    away: str
    neutral: bool
    tournament: str
    home_elo: float
    away_elo: float
    home_recent: list[str] = []
    away_recent: list[str] = []
    probabilities: Probabilities
    most_likely: str


class TeamRatingChange(BaseModel):
    team: str
    elo_before: float
    elo_after: float
    delta: float


class AddResultResponse(BaseModel):
    match: MatchOut
    changes: list[TeamRatingChange]


class RatingPoint(BaseModel):
    date: date_type
    elo: float


class TeamDetail(BaseModel):
    team: TeamOut
    recent_matches: list[MatchOut]
    rating_history: list[RatingPoint]


class FixtureOut(BaseModel):
    utc_date: str
    home: str
    away: str
    stage: str | None = None
    probabilities: Probabilities
    most_likely: str


class AccuracyOut(BaseModel):
    n: int
    correct: int
    accuracy: float | None = None


class TournamentRequest(BaseModel):
    runs: int = Field(default=3000, ge=100, le=20000)


class TournamentTeamOdds(BaseModel):
    team: str
    group: str
    elo: float
    advance_group: float
    reach_quarterfinal: float
    reach_semifinal: float
    reach_final: float
    win_title: float
    known: bool


class TournamentResponse(BaseModel):
    runs: int
    teams: list[TournamentTeamOdds]
    unknown_teams: list[str] = []
