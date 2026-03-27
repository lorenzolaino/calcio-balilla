# ⚽ Table Football - Elo Ranking

A Streamlit application to manage an Elo-based ranking system for table football (2vs2).

## 🚀 How to Run Locally

### 1. Prerequisites
- Python 3.8+
- PostgreSQL (local or remote)

### 2. Installation
Clone the repository and install the dependencies:
```bash
pip install -r requirements.txt
```

### 3. Database Configuration
The application uses the `DATABASE_URL` environment variable to connect to PostgreSQL.

#### Option A: Local Database (Docker)
The fastest way to start a local database:
```bash
docker run --name pg-calcio -e POSTGRES_PASSWORD=password -e POSTGRES_DB=calcio -p 5432:5432 -d postgres
export DATABASE_URL=postgresql://postgres:password@localhost:5432/calcio
```

#### Option B: Local Database (Native Installation)
Create a database in Postgres and set the variable:
```bash
export DATABASE_URL=postgresql://<username>:<password>@localhost:5432/<db_name>
```

#### Option C: External Database (e.g., Supabase, Render, Neon)
Copy the connection string provided by your provider:
```bash
export DATABASE_URL=postgresql://user:pass@host:port/dbname?sslmode=require
```

### 4. Start the Application
Once the `DATABASE_URL` variable is set, run Streamlit:
```bash
streamlit run app.py
```

The application will automatically initialize the necessary tables on the first run.

## 🛠️ Database Optimizations
The code has been optimized to minimize database calls through:
- **Streamlit Caching**: Read-heavy operations (ranking, match history) are cached using `@st.cache_data`.
- **Batch Processing**: Player updates and history inserts during match registration are executed in batches.
- **Efficient Querying**: Use of `RETURNING` clauses and `IN` filters to reduce network round-trips.
