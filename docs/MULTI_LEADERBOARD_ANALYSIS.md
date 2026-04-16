# Multi-Leaderboard System Analysis

This document analyzes the technical implications, costs, and scalability of implementing a private/group-based leaderboard system where users see only their own rankings, while administrators have global access.

## 1. Architectural Impact

### Data Model Changes
To support multiple independent leaderboards, the schema must evolve:
1.  **`groups` table**: To define different competitive circles (e.g., "Office A", "Friends", "Tournament 2024").
2.  **`group_members` table**: A many-to-many relationship between `players` and `groups`.
3.  **`matches` table update**: Add a `group_id` column to attribute matches to a specific context.
4.  **`players` table update**: Ratings must become group-specific. Instead of a single rating in the `players` table, we move it to a `group_stats` table (`player_id`, `group_id`, `rating`, `wins`, `losses`, `trend`).

### Access Control
- **Regular Users**: Can only query data where `group_id` matches their assigned group(s).
- **Admin Users**: Can query all `group_id`s or a summary view.

## 2. Database Call Analysis (Impact on Free Tier)

### Reading (Standings)
- **Current**: 1 `SELECT` from `players`.
- **New**: 1 `SELECT` from `group_stats` WHERE `group_id = :my_group`.
- **Impact**: **Zero increase in call count**. With a proper index on `group_id`, the database performance remains nearly identical.

### Writing (Recording a Match)
- **Current**: 1 `INSERT` (match) + multiple `UPDATE`s (players).
- **New**: 1 `INSERT` (match) + multiple `UPDATE`s (group_stats).
- **Impact**: **Zero increase in call count**. The logic simply targets a filtered row instead of a global one.

### Overhead
The only increase in "calls" occurs during the initial setup (creating a group, joining a group). These are infrequent "admin" actions.

## 3. Storage & Row Count (The Real Limit)
Most free-tier databases (like Supabase, Neon, or Railway) limit **row count** or **active storage**.
- **Standings**: Instead of `N` players, you will have `N * G` rows (where `G` is the number of groups). This grows faster than before.
- **Matches**: The number of matches is the main driver of storage. Whether they are in one leaderboard or ten, 1000 matches = 1000 rows.

## 4. Implementation Recommendations

### Phase 1: Filtered View (Low Effort)
If players are the same but want different "views" of the data (e.g., a "Pro" vs "Amateur" ranking), you can just add a `category` tag to matches and filter the query.

### Phase 2: Isolated Groups (High Effort / High Privacy)
If you want completely separate Elo ratings per group:
1.  **Use the Trigger Strategy**: (See `DATABASE_OPTIMIZATION.md`). Moving logic to the DB is mandatory here to prevent Python code from becoming a "spaghetti" of group-filtering logic.
2.  **Indexing**: Ensure `group_id` is an index on every table. This keeps the "cost" of the query low even as the database grows.
3.  **RLS (Row Level Security)**: If using PostgreSQL, you can enable RLS. This way, the database itself blocks a user from seeing a group they don't belong to, even if the Python code makes a mistake. This is the gold standard for security.

## 5. Conclusion
Adding multiple leaderboards is **not expensive in terms of call count**, but it increases **logical complexity**. By using the **Trigger Strategy** and **Row Level Security**, you can scale to hundreds of leaderboards while keeping the Python application simple and the database calls minimal.
