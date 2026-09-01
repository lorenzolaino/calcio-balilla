from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations
import random


@dataclass(frozen=True)
class SeriesSpec:
    key: str
    round_index: int
    round_name: str
    position: int
    challenger1_id: int | None
    challenger2_id: int | None
    source1_key: str | None = None
    source2_key: str | None = None
    is_final: bool = False


def lower_power_of_two(value: int) -> int:
    if value < 1:
        raise ValueError("At least one participant is required.")
    return 1 << (value.bit_length() - 1)


def bracket_numbers(participant_count: int) -> tuple[int, int, int]:
    if participant_count < 2:
        raise ValueError("A tournament requires at least two participants.")
    target = lower_power_of_two(participant_count)
    play_ins = participant_count - target
    return target, play_ins, 0 if play_ins == 0 else 2 * target - participant_count


def select_byes(participant_ids, previous_ranking, bye_count):
    """Ranking decides byes only; missing ranks fall back to player id."""
    participants = set(participant_ids)
    ordered = [player_id for player_id in previous_ranking if player_id in participants]
    ordered.extend(sorted(participants - set(ordered)))
    return ordered[:bye_count]


def _round_name(size: int, preliminary=False) -> str:
    if preliminary:
        return "Preliminari"
    return {2: "Finale", 4: "Semifinali", 8: "Quarti"}.get(size, f"Turno da {size}")


def generate_bracket(participant_ids, previous_ranking=(), rng=None):
    participant_ids = list(dict.fromkeys(participant_ids))
    if len(participant_ids) < 2:
        raise ValueError("Select at least two different participants.")
    rng = rng or random.SystemRandom()
    target, play_in_count, bye_count = bracket_numbers(len(participant_ids))
    bye_players = select_byes(participant_ids, previous_ranking, bye_count)
    play_in_players = [p for p in participant_ids if p not in set(bye_players)]
    rng.shuffle(play_in_players)

    specs = []
    preliminary_keys = []
    for position in range(play_in_count):
        key = f"r0s{position}"
        preliminary_keys.append(key)
        specs.append(SeriesSpec(
            key, 0, _round_name(target, True), position,
            play_in_players[position * 2], play_in_players[position * 2 + 1],
        ))

    entrants = ([(player_id, None) for player_id in participant_ids] if not play_in_count
                else [(player_id, None) for player_id in bye_players] +
                     [(None, key) for key in preliminary_keys])
    rng.shuffle(entrants)
    round_index = 1 if play_in_count else 0
    current = []
    for position in range(target // 2):
        first, second = entrants[position * 2:position * 2 + 2]
        key = f"r{round_index}s{position}"
        current.append(key)
        specs.append(SeriesSpec(
            key, round_index, _round_name(target), position,
            first[0], second[0], first[1], second[1], target == 2,
        ))

    size = target // 2
    while size >= 2:
        previous = current
        round_index += 1
        current = []
        for position in range(size // 2):
            key = f"r{round_index}s{position}"
            current.append(key)
            specs.append(SeriesSpec(
                key, round_index, _round_name(size), position,
                None, None, previous[position * 2], previous[position * 2 + 1], size == 2,
            ))
        size //= 2
    return specs


def wins_required(is_final: bool) -> int:
    return 3 if is_final else 2


def series_result(winner_ids, challenger1_id, challenger2_id, is_final=False):
    wins1 = sum(player_id == challenger1_id for player_id in winner_ids)
    wins2 = sum(player_id == challenger2_id for player_id in winner_ids)
    required = wins_required(is_final)
    winner = challenger1_id if wins1 >= required else challenger2_id if wins2 >= required else None
    return wins1, wins2, winner


def valid_companion_pairs(challenger1_id, challenger2_id, present_ids, used1=(), used2=()):
    candidates = set(present_ids) - {challenger1_id, challenger2_id}
    allowed1 = candidates - set(used1)
    allowed2 = candidates - set(used2)
    return [(a, b) for a, b in permutations(candidates, 2) if a in allowed1 and b in allowed2]


def draw_companions(challenger1_id, challenger2_id, present_ids, used1=(), used2=(), rng=None):
    pairs = valid_companion_pairs(challenger1_id, challenger2_id, present_ids, used1, used2)
    if not pairs:
        raise ValueError("No valid pair: two distinct, present and not-yet-used companions are required.")
    return (rng or random.SystemRandom()).choice(pairs)


def validate_series_match(challenger1_id, challenger2_id, team_a, team_b, used1=(), used2=()):
    team_a, team_b = set(team_a), set(team_b)
    if challenger1_id in team_a and challenger2_id in team_b:
        companion1 = next(iter(team_a - {challenger1_id}), None)
        companion2 = next(iter(team_b - {challenger2_id}), None)
    elif challenger1_id in team_b and challenger2_id in team_a:
        companion1 = next(iter(team_b - {challenger1_id}), None)
        companion2 = next(iter(team_a - {challenger2_id}), None)
    else:
        raise ValueError("The two series challengers must play on opposite teams.")
    if companion1 in {challenger1_id, challenger2_id} or companion2 in {challenger1_id, challenger2_id}:
        raise ValueError("A series challenger cannot be used as a companion.")
    if companion1 == companion2:
        raise ValueError("The two companions must be different players.")
    if companion1 in set(used1):
        raise ValueError("This companion has already played with the first challenger in this series.")
    if companion2 in set(used2):
        raise ValueError("This companion has already played with the second challenger in this series.")
    return companion1, companion2
