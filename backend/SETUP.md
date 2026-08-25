# Backend Setup — Phase 1 (Foundation: DB, Models, Auth)

## What's in this batch
```
backend/
  .env                    <- DB connection + secret key (already filled in for you)
  main.py                 <- FastAPI entrypoint
  app/
    __init__.py
    config.py              <- loads .env
    database.py             <- SQLAlchemy engine/session
    models.py                <- all 9 tables
    security.py               <- password hashing + JWT
    schemas.py                 <- request/response validation
    deps.py                     <- get_current_user, require_role
    routers/
      __init__.py
      auth.py                    <- /auth/register, /auth/login, /auth/me
```

## Steps (Windows 10, cmd or PowerShell)

1. Copy all the files above into your existing `backend/` folder,
   preserving the folder structure (don't flatten `app/routers/` into `app/`).

2. Activate your venv:
   ```
   cd backend
   venv\Scripts\activate
   ```
   (PowerShell: `.\venv\Scripts\Activate.ps1` — if you get an execution
   policy error, run `Set-ExecutionPolicy -Scope Process RemoteSigned` first)

3. Confirm `.env` matches your actual Postgres setup. It's currently set to:
   ```
   DATABASE_URL=postgresql://equityuser:equity2025@localhost:5432/equityengine
   ```
   which matches the user/db you created earlier — should be correct as-is.

4. Run the server:
   ```
   uvicorn main:app --reload
   ```

5. If it starts without errors, you'll see something like:
   ```
   INFO:     Uvicorn running on http://127.0.0.1:8000
   ```
   On startup, `Base.metadata.create_all()` creates all 9 tables in your
   `equityengine` database automatically — you don't need to run any SQL
   by hand.

6. Verify the tables were created:
   ```
   psql -U equityuser -d equityengine -h localhost
   \dt
   ```
   You should see all 9 tables listed.

7. Test the API in your browser at **http://127.0.0.1:8000/docs** —
   FastAPI auto-generates interactive API docs. Try:
   - `POST /auth/register` with a body like:
     ```json
     {
       "email": "test@example.com",
       "full_name": "Test Candidate",
       "password": "password123",
       "role": "candidate",
       "consent_given": true
     }
     ```
   - You should get back a 201 response with an access_token and user object.
   - Copy the access_token, click "Authorize" at the top of the docs page,
     paste it in as `Bearer <token>` (or just the raw token, FastAPI's
     docs UI handles the prefix), and try `GET /auth/me` — it should
     return the same user.

## If something breaks

Common issues and what they usually mean:

- **`ModuleNotFoundError: No module named 'X'`** — that package isn't
  actually in your venv despite being in your original list. Run
  `pip list` inside the activated venv to check, and tell me which one
  is missing so I can either adjust the code or you can install it.

- **`sqlalchemy.exc.OperationalError: could not connect to server`** —
  Postgres isn't running, or the connection details in `.env` don't
  match. Check the Postgres service is started (Services app on
  Windows, look for "postgresql-x64-..." ).

- **`psycopg2.errors.InsufficientPrivilege`** — the schema grants from
  your DROP/CREATE script didn't take effect. Re-run the `GRANT ALL ON
  SCHEMA public` line from psql.

- **bcrypt-related error mentioning `__about__`** — a passlib/bcrypt
  version mismatch. Tell me the exact error text and I'll fix it (this
  is a known compatibility issue between passlib and newer bcrypt
  releases, which is why bcrypt==4.0.1 was pinned in your original list).

Paste me the exact error text if anything fails — don't paraphrase it,
the exact wording usually tells me exactly what's wrong.
