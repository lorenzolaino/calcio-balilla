# Project Patterns & Architectural Mandates

This document outlines the core engineering standards and optimization patterns established for the Calcio Balilla project. Adherence to these patterns ensures data integrity, high performance, and long-term maintainability.

## 1. Database Optimization Patterns

### A. Server-Side Filtering
**Mandate**: Always filter data in the database (SQL) rather than in application code (Python).
*   **Why**: Minimizes memory usage and reduces network bandwidth.
*   **Example**: `WHERE is_active = TRUE` or `WHERE m.a1_id = :pid`.

### B. Batch Updates & Transaction Integrity
**Mandate**: Wrap all multi-step write operations in a single transaction and use batch updates.
*   **Pattern**: Use `with engine.begin() as conn:` for atomic transactions.
*   **Pattern**: When updating multiple rows (e.g., player stats), prepare a list of dictionaries and execute a single `UPDATE` statement.
*   **Example**: 
    ```python
    conn.execute(update_stmt, [{"id": 1, "r": 1050}, {"id": 2, "r": 1020}])
    ```

### C. N+1 Query Prevention
**Mandate**: Use SQL `JOIN`s to fetch all related metadata in a single round-trip.
*   **Why**: Prevents performance degradation as the database grows.
*   **Example**: Joining `matches` with `players` four times to get all participant names in one `SELECT`.

## 2. Data Integrity Patterns

### A. Soft Delete (Player Deactivation)
**Mandate**: Never hard-delete players with match history.
*   **Implementation**: Use the `is_active` flag.
*   **Behavior**: Inactive players are hidden from selection and current leaderboards but are preserved in historical records and trends to maintain Elo mathematical accuracy.

### B. Transactional Restoration (Match Deletion)
**Mandate**: Deleting a match must surgically revert all affected statistics.
*   **Reversion Flow**:
    1. Fetch specific deltas from the match record.
    2. Subtract deltas from player ratings.
    3. Revert wins/losses and goal differences.
    4. Recalculate trends from the remaining history.

## 3. Streamlit & UX Patterns

### A. Strategic Caching
**Mandate**: Use `@st.cache_data` for all read-only database lookups.
*   **Pattern**: Explicitly call `st.cache_data.clear()` after any write operation to ensure UI consistency.

### B. Versioning & Release Notes
**Mandate**: Use `CURRENT_VERSION` and `localStorage` (via `streamlit_js_eval`) to show users a "What's New" dialog only once per update.

## 4. Testing Patterns

### A. Isolated Logic Testing
**Mandate**: Core business logic (Elo, stat restoration) must be testable without a live database.
*   **Pattern**: Use `unittest.mock` to intercept database calls and verify SQL logic and parameter passing.
