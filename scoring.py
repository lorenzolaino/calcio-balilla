from __future__ import annotations

from datetime import datetime, timedelta


RECENT_DUPLICATE_MATCH_WINDOW_SECONDS = 15


def expected_score(r_team, r_opp):
    return 1.0 / (1.0 + 10 ** ((r_opp - r_team) / 400.0))


def margin_multiplier(margin):
    if margin <= 2:
        return 1.0
    if margin <= 9:
        return 1.0 + (margin - 2) * 0.1
    return 1.8


def get_k_factor(games):
    # Starts at 30.0, drops to 20.0 at 40 games, ~15 at 120 games.
    # Asymptotic to 10.0.
    return 10.0 + (20.0 / (1.0 + (games / 40.0)))


def calculate_match_updates(players, goals_a, goals_b, rating_diff_threshold):
    a1, a2, b1, b2 = [list(player) for player in players]
    margin = abs(goals_a - goals_b)

    r_a = (a1[2] + a2[2]) / 2.0
    r_b = (b1[2] + b2[2]) / 2.0
    e_a = expected_score(r_a, r_b)
    s_a = 1.0 if goals_a > goals_b else 0.0
    m = margin_multiplier(margin)

    multiplier = 1.0
    team_diff = r_a - r_b
    is_a_favored = team_diff > 0

    if abs(team_diff) > rating_diff_threshold:
        if (is_a_favored and s_a == 1.0) or (not is_a_favored and s_a == 0.0):
            multiplier = 0.5
        else:
            multiplier = 1.5

    delta_a1 = round(get_k_factor(a1[3]) * m * multiplier * (s_a - e_a), 1)
    delta_a2 = round(get_k_factor(a2[3]) * m * multiplier * (s_a - e_a), 1)
    delta_b1 = round(get_k_factor(b1[3]) * m * multiplier * ((1 - s_a) - (1 - e_a)), 1)
    delta_b2 = round(get_k_factor(b2[3]) * m * multiplier * ((1 - s_a) - (1 - e_a)), 1)
    deltas = (delta_a1, delta_a2, delta_b1, delta_b2)

    a1[2] += delta_a1
    a2[2] += delta_a2
    b1[2] += delta_b1
    b2[2] += delta_b2

    for player in [a1, a2, b1, b2]:
        player[3] += 1

    if s_a == 1:
        a1[4] += 1
        a2[4] += 1
        b1[5] += 1
        b2[5] += 1
    else:
        b1[4] += 1
        b2[4] += 1
        a1[5] += 1
        a2[5] += 1

    gd_a = goals_a - goals_b
    a1[6] += gd_a
    a2[6] += gd_a
    b1[6] -= gd_a
    b2[6] -= gd_a

    for i, player in enumerate([a1, a2, b1, b2]):
        is_win = (i < 2 and s_a == 1) or (i >= 2 and s_a == 0)
        res_char = "W" if is_win else "L"

        current_trend = player[7] if player[7] else ""
        parts = current_trend.split()
        player[7] = " ".join(([res_char] + parts)[:5])

    return [a1, a2, b1, b2], deltas


def is_same_match(candidate, existing):
    same_side = (
        {candidate["a1_id"], candidate["a2_id"]} == {existing["a1_id"], existing["a2_id"]}
        and {candidate["b1_id"], candidate["b2_id"]} == {existing["b1_id"], existing["b2_id"]}
        and candidate["goals_a"] == existing["goals_a"]
        and candidate["goals_b"] == existing["goals_b"]
    )
    swapped_side = (
        {candidate["a1_id"], candidate["a2_id"]} == {existing["b1_id"], existing["b2_id"]}
        and {candidate["b1_id"], candidate["b2_id"]} == {existing["a1_id"], existing["a2_id"]}
        and candidate["goals_a"] == existing["goals_b"]
        and candidate["goals_b"] == existing["goals_a"]
    )
    return same_side or swapped_side


def recent_duplicate_cutoff(now=None):
    now = now or datetime.now()
    return now - timedelta(seconds=RECENT_DUPLICATE_MATCH_WINDOW_SECONDS)
