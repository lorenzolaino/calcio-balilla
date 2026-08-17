from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Player:
    id: int
    name: str
    is_active: bool


@dataclass(frozen=True)
class PlayerStandings:
    name: str
    rating: float
    games: int
    wins: int
    losses: int
    goal_diff: int
    trend: str


@dataclass(frozen=True)
class PlayerStats:
    player_id: int
    rating: float
    games: int
    wins: int
    losses: int
    goal_diff: int


@dataclass(frozen=True)
class PlayerMatchStats:
    id: int
    name: str
    rating: float
    games: int
    wins: int
    losses: int
    goal_diff: int
    trend: str


@dataclass(frozen=True)
class MatchHistoryEntry:
    date: datetime
    a1: str
    a2: str
    b1: str
    b2: str
    goals_a: int
    goals_b: int
    delta_a1: float
    delta_a2: float
    delta_b1: float
    delta_b2: float
    delta_a: Optional[float]
    delta_b: Optional[float]
    id: int


@dataclass(frozen=True)
class FutureMatchEntry:
    date: datetime
    a1: str
    a2: str
    b1: str
    b2: str
    id: int


@dataclass(frozen=True)
class Leaderboard:
    id: int
    name: str
    code: str


@dataclass(frozen=True)
class UserSession:
    id: int
    username: str
    role: str
    leaderboard_id: Optional[int]


@dataclass(frozen=True)
class Season:
    id: int
    leaderboard_id: int
    number: int
    name: str
    is_active: bool


@dataclass(frozen=True)
class MatchRecord:
    a1_id: int
    a2_id: int
    b1_id: int
    b2_id: int
    goals_a: int
    goals_b: int
    delta_a1: float
    delta_a2: float
    delta_b1: float
    delta_b2: float
    leaderboard_id: int
    season_id: int


@dataclass
class MatchPlayerState:
    id: int
    name: str
    rating: float
    games: int
    wins: int
    losses: int
    goal_diff: int
    trend: str = ""

    @classmethod
    def from_match_stats(cls, player: PlayerMatchStats) -> "MatchPlayerState":
        return cls(
            id=player.id,
            name=player.name,
            rating=player.rating,
            games=player.games,
            wins=player.wins,
            losses=player.losses,
            goal_diff=player.goal_diff,
            trend=player.trend,
        )

    @classmethod
    def from_player_stats(cls, player: PlayerStats, name: str = "", trend: str = "") -> "MatchPlayerState":
        return cls(
            id=player.player_id,
            name=name,
            rating=player.rating,
            games=player.games,
            wins=player.wins,
            losses=player.losses,
            goal_diff=player.goal_diff,
            trend=trend,
        )

    def to_player_stats_update(self, leaderboard_id: int) -> dict:
        return {
            "r": self.rating,
            "g": self.games,
            "w": self.wins,
            "l": self.losses,
            "gd": self.goal_diff,
            "t": self.trend,
            "pid": self.id,
            "l_id": leaderboard_id,
        }
