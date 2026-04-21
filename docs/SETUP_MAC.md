# Running Pirkei Avot Finder on macOS

## Prerequisites

- Python 3.10+ installed (`python3 --version` to check)
- PostgreSQL with the `pgvector` extension
- A Supabase project (for authentication)
- AWS API Gateway endpoint (for semantic search)

## 1. Clone & set up virtual environment

```bash
git clone <your-repo-url>
cd <project-folder>

python3 -m venv venv
source venv/bin/activate
```

## 2. Install dependencies

```bash
pip install -r requirements.txt
```

## 3. Create the `.env` file

Create a `.env` file in the project root with these variables:

```env
# PostgreSQL connection string
DATABASE_URL=postgresql://username:password@localhost:5432/pirkei_avot

# Flask secret key (generate one with: python3 -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY=your_secret_key_here

# Supabase credentials
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key

# AWS Semantic Search
AWS_SEARCH_AI_KEY=your_aws_api_key
AWS_SEARCH_API_URL=https://your-api-gateway-url.amazonaws.com/prod/search
```

## 4. Set up PostgreSQL

Make sure PostgreSQL is running, then:

```bash
# Install PostgreSQL if needed
brew install postgresql@15
brew services start postgresql@15

# Create the database
createdb pirkei_avot

# Enable pgvector extension (connect to the DB first)
psql pirkei_avot -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Initialize tables
python scripts/create_db.py
```

## 5. Run the app

```bash
# Development
python app.py

# Or with Flask directly
flask run
```

The app will be available at `http://localhost:5000`.

## 6. Production (optional)

```bash
gunicorn --config gunicorn.conf.py app:app
```

## Notes

- If you're connecting to a remote PostgreSQL (like Render or Supabase), just use that connection string in `DATABASE_URL` — no need to install PostgreSQL locally.
- The `sslmode=require` is enforced in the config, so remote databases need SSL support.
- Rate limiting is set to 20 requests/minute per IP.
