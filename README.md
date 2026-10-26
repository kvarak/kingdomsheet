# Kingdom Sheet

A small Django app for tracking kingdoms in a Kingmaker-style campaign. Players create a kingdom, share its access code, and edit a plain character sheet of numeric statistics. Every change is recorded in a history log.

## How access works

- There are no accounts or passwords for logins. A kingdom is opened with its **access code** (64 hex characters).
- Creating a kingdom gives you its code. The sheet shows the full sharing link. Share it or the code itself with your group.
- Opening the link only shows a confirmation page. Joining needs an explicit POST, so following a link never adds membership by accident.
- Membership is stored in your browser session. Clearing cookies or using another browser means joining again.
- Anyone with the code can edit the kingdom. Treat the code like a password.

### Player names

Before you can change anything, pick a display name on the names page.

- An unprotected name is free to use, but anyone can pick it. Its history entries show as `unverified`.
- You can protect a name with a password (at least 8 characters). Selecting a protected name requires its password. History entries from that name show as `password-verified`.
- Names are matched ignoring case and extra spaces.
- Requests to the names page are rate limited to 5 per 10 minutes per name. The limit is keyed by name, not IP address, because a reverse proxy hides client IPs.

## Local development

1. Copy the example config and edit it:

   ```sh
   cp .env.example .env
   ```

   Set `DJANGO_SECRET_KEY` to a long random value, for example:

   ```sh
   python -c "import secrets; print(secrets.token_urlsafe(50))"
   ```

   Set `POSTGRES_PASSWORD` to a database password. `.env` is ignored by git and must not be committed.

2. Start everything. Migrations run automatically on container start:

   ```sh
   make serve
   ```

3. Open http://127.0.0.1:8000/

Other targets:

| Command | What it does |
| --- | --- |
| `make serve` | Build and start the web and database services |
| `make stop` | Stop the services (data is kept) |
| `make check` | Run ruff lint and format checks and the test suite inside Docker |
| `make migrate` | Apply database migrations |
| `make logs` | Follow service logs |

PostgreSQL is not published to the host. Only the web app listens, on `127.0.0.1:8000`. Database data lives in the `db-data` volume.

## Deploying the published image

CI builds the web image on every push to `main` that passes `make check`, and pushes it to GitHub Container Registry as:

- `ghcr.io/<owner>/kingdomsheet-web:latest`
- `ghcr.io/<owner>/kingdomsheet-web:<commit SHA>`

The image is multi-architecture (`linux/amd64` and `linux/arm64`). Docker picks the right one automatically, so the same tag runs on a normal server or a Raspberry Pi with a 64-bit OS (Pi 3, 4, 5 or Zero 2 W with 64-bit Raspberry Pi OS). 32-bit Raspberry Pi OS is not supported, because the PostgreSQL driver has no 32-bit ARM build. Check with `uname -m`: it must print `aarch64`. On a Pi with little memory, set `GUNICORN_WORKERS=2` in `.env`.

To run it instead of building locally, set `WEB_IMAGE` in `.env` and start without building. New GHCR packages are private, so either make the package public in its GitHub package settings or log in first with `docker login ghcr.io` using a personal access token with `read:packages`.

```sh
# In .env:
# WEB_IMAGE=ghcr.io/<owner>/kingdomsheet-web:latest

docker compose pull web
docker compose up -d --no-build
```

Migrations run on every container start, before gunicorn starts. To run them by hand:

```sh
docker compose run --rm web python manage.py migrate
```

Production settings to check in `.env`:

- `DJANGO_SECRET_KEY`: a unique random value. Never reuse the example.
- `DJANGO_ALLOWED_HOSTS`: your public hostname.
- `DJANGO_CSRF_TRUSTED_ORIGINS`: the full origin, for example `https://kingdoms.example.com`.
- `DJANGO_HTTPS=1`: enables secure cookies. Put the app behind an HTTPS reverse proxy that sets `X-Forwarded-Proto` and passes the original `Host` header, so sharing links use your public address.
- `DJANGO_DEBUG` stays `0`.

Access codes in request paths are redacted from the gunicorn logs.

## Layout

- `config/`: Django settings and URLs.
- `kingdoms/`: models, forms, views, and tests.
- `templates/kingdoms/`, `static/kingdoms/`: plain HTML and CSS.
- `Dockerfile`, `docker-compose.yml`, `Makefile`: container and task setup.
- `requirements.in` and `requirements-dev.in`: dependency sources. The `.txt` files are pinned locks.

To change dependencies, edit the `.in` file and recompile the lock inside a Python 3.13 container.

## Limits

- The access code is the only secret. There is no per-user audit beyond the display name.
- History entries are never edited or deleted by the app.
- Membership is per browser session. It is not tied to a user account.
