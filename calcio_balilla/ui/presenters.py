def format_history_row(record):
    is_new_match = record.delta_a is None

    if is_new_match:
        da1 = f"{record.delta_a1:+g}" if record.delta_a1 is not None else "+0"
        da2 = f"{record.delta_a2:+g}" if record.delta_a2 is not None else "+0"
        db1 = f"{record.delta_b1:+g}" if record.delta_b1 is not None else "+0"
        db2 = f"{record.delta_b2:+g}" if record.delta_b2 is not None else "+0"

        team_a = f"{record.a1} ({da1}) + {record.a2} ({da2})"
        team_b = f"{record.b1} ({db1}) + {record.b2} ({db2})"
        delta_a_display = "-"
        delta_b_display = "-"
    else:
        team_a = f"{record.a1} + {record.a2}"
        team_b = f"{record.b1} + {record.b2}"
        delta_a_display = f"{record.delta_a:+g}" if record.delta_a is not None else "-"
        delta_b_display = f"{record.delta_b:+g}" if record.delta_b is not None else "-"

    return {
        "Date": record.date.strftime("%d/%m/%Y"),
        "Match": f"{team_a} vs {team_b}",
        "Score": f"{record.goals_a} - {record.goals_b}",
        "Δ A/B": f"{delta_a_display} / {delta_b_display}",
    }


def format_future_match_row(record):
    return {
        "Date": record.date.strftime("%d/%m/%Y %H:%M"),
        "Match": f"{record.a1} + {record.a2} vs {record.b1} + {record.b2}",
    }


def format_leaderboard_row(index, player):
    return {
        "Rank": index + 1,
        "Player": player.name,
        "Rating": round(player.rating, 1),
        "Matches": player.games,
        "W": player.wins,
        "L": player.losses,
        "GD": player.goal_diff,
        "Win %": (player.wins / player.games * 100) if player.games > 0 else 0.0,
        "Trend": player.trend if player.trend else "-",
    }
