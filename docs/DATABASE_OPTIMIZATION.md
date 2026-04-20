# Database Optimization Strategy: Server-Side Logic

This document describes how to migrate business logic (Elo calculation and statistics) directly to the PostgreSQL database using **Triggers** and **Stored Procedures**.

## Objective
Reduce traffic between the Python application and the Database from 4-5 calls per match to **1 single call** (`INSERT` into the `matches` table).

## 1. Current Architecture (Python-Heavy)
1. `SELECT` current ratings of the 4 players.
2. Calculate Elo in Python.
3. `UPDATE` the `players` table (rating, stats, trend).
4. `INSERT` into the `matches` table.
5. `INSERT` into the `player_ratings_history` table.

## 2. Proposed Architecture (DB-Centric)
The application only executes:
```sql
INSERT INTO matches (date, a1_id, a2_id, b1_id, b2_id, goals_a, goals_b)
VALUES (NOW(), 1, 2, 3, 4, 10, 8);
```

Everything else is handled by an `AFTER INSERT` Trigger on the `matches` table.

### Implementation Example (PostgreSQL)

#### A. Elo Calculation and Update Function
```sql
CREATE OR REPLACE FUNCTION update_players_stats_after_match()
RETURNS TRIGGER AS $$
DECLARE
    r_a FLOAT;
    r_b FLOAT;
    e_a FLOAT;
    s_a FLOAT;
    delta_a FLOAT;
    k_factor CONSTANT FLOAT := 20.0;
    margin INT;
    mult FLOAT;
BEGIN
    -- 1. Calculate average ratings
    SELECT AVG(rating) INTO r_a FROM players WHERE id IN (NEW.a1_id, NEW.a2_id);
    SELECT AVG(rating) INTO r_b FROM players WHERE id IN (NEW.b1_id, NEW.b2_id);

    -- 2. Calculate expected score and margin multiplier
    e_a := 1.0 / (1.0 + 10 ^ ((r_b - r_a) / 400.0));
    s_a := CASE WHEN NEW.goals_a > NEW.goals_b THEN 1.0 ELSE 0.0 END;
    margin := ABS(NEW.goals_a - NEW.goals_b);
    mult := CASE 
        WHEN margin <= 2 THEN 1.0 
        WHEN margin <= 9 THEN 1.0 + (margin - 2) * 0.1 
        ELSE 1.8 
    END;

    -- 3. Calculate Delta
    delta_a := ROUND(k_factor * mult * (s_a - e_a));

    -- 4. Update Players (Team A)
    UPDATE players SET 
        rating = rating + delta_a,
        games = games + 1,
        wins = wins + (CASE WHEN s_a = 1.0 THEN 1 ELSE 0 END),
        losses = losses + (CASE WHEN s_a = 0.0 THEN 1 ELSE 0 END),
        goal_diff = goal_diff + (NEW.goals_a - NEW.goals_b),
        trend = LEFT(TRIM(LEADING ' ' FROM (CASE WHEN s_a = 1.0 THEN 'W ' ELSE 'L ' END) || COALESCE(trend, '')), 9)
    WHERE id IN (NEW.a1_id, NEW.a2_id);

    -- 5. Update Players (Team B)
    UPDATE players SET 
        rating = rating - delta_a,
        games = games + 1,
        wins = wins + (CASE WHEN s_a = 0.0 THEN 1 ELSE 0 END),
        losses = losses + (CASE WHEN s_a = 1.0 THEN 1 ELSE 0 END),
        goal_diff = goal_diff - (NEW.goals_a - NEW.goals_b),
        trend = LEFT(TRIM(LEADING ' ' FROM (CASE WHEN s_a = 0.0 THEN 'W ' ELSE 'L ' END) || COALESCE(trend, '')), 9)
    WHERE id IN (NEW.b1_id, NEW.b2_id);

    -- 6. Insert History (Example for one player)
    INSERT INTO player_ratings_history (player_id, match_id, rating)
    SELECT id, NEW.id, rating FROM players WHERE id IN (NEW.a1_id, NEW.a2_id, NEW.b1_id, NEW.b2_id);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

#### B. Trigger Creation
```sql
CREATE TRIGGER trigger_update_stats
AFTER INSERT ON matches
FOR EACH ROW
EXECUTE FUNCTION update_players_stats_after_match();
```

## 3. Benefits for the New Leaderboard
If you add a second leaderboard (e.g., Monthly Leaderboard or 1vs1):
- You can add a second trigger or expand the existing one.
- The Streamlit app will remain lightweight: it only needs to read data, while the DB handles consistency across various leaderboards in real-time.
- **Data Integrity**: There will never be a risk that a match is saved without updating the rating (atomic operation on the DB).
