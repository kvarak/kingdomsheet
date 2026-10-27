# Kingdom Sheet

A small Django app for tracking kingdoms in a Kingmaker campaign played with the Varlyn 5e rules (dnd.rigo.nu). Players create a kingdom, share its access code and edit its kingdom sheet. Every change is recorded in a history log.

## The sheet

The sheet follows the layout of the official Kingmaker kingdom sheet: kingdom details, ability scores, ruin, unrest, leaders, all 16 kingdom skills, feats, abilities, commodities, work sites, settlements, relations and ongoing events. Free-form custom statistics sit below it. The numbers are the Pathfinder 2e kingdom rules adapted to the Varlyn 5e scale.

Only these values are calculated, and they update after saving:

- Ability modifier = (score - 10) / 2, rounded down.
- Proficiency bonus by kingdom level, as for characters: +2 at levels 1-4, rising by 1 every 4 levels to +6.
- Skill ranks: Untrained (no proficiency), Proficient (+ proficiency), Expertise (+ proficiency, roll with advantage), Expertise +1 and Expertise +2 (each step adds +1, like Varlyn's Improved Proficiency).
- Skill total = ability modifier + proficiency + bonus + VP. Bonus holds every other bonus or penalty, such as structures and invested leaders.
- Control DC = 12 + proficiency bonus + size modifier (+0 under 10 hexes, then +1 at 10, +2 at 25, +3 at 50 and +4 at 100), plus 2 while the ruler role is vacant.
- Other kingdom check DCs = 12 + the proficiency bonus for the content's level, +2 when hard and +5 when very hard. The sheet shows them next to the Control DC.
- VP (vacancy penalty) per skill, from leadership roles no character fills: a vacant ruler gives -1 to every skill, which stacks; a vacant counselor, emissary, treasurer or viceroy gives -1 to Culture, Loyalty, Economy or Stability skills; a vacant general or magister gives disadvantage on Warfare. Apart from the ruler's, vacancy penalties do not stack, so a skill takes the worst one, and disadvantage counts as worse than -1. Advantage and disadvantage cancel out.
- Vacancy effects the skill table cannot show (the ruler's 1d4 Unrest, disadvantage on Warfare activities for a vacant general or magister and disadvantage on Region activities for a vacant warden) are listed under Leaders. Warfare activities can use other skills than Warfare, so that penalty is listed too. In edit mode, the ⓘ next to each role shows its key ability and vacancy penalty.

Everything else, such as ruin and unrest penalties, storage limits and resource dice, is typed in by hand.

## How access works

- There are no accounts or passwords for logins. A kingdom is opened with its **access code** (64 hex characters).
- Creating a kingdom gives you its code. The sheet shows the full sharing link. Share it or the code itself with your group.
- Opening the link only shows a confirmation page. Joining needs an explicit POST, so following a link never adds membership by accident.
- Membership is stored in your browser session. Clearing cookies or using another browser means joining again.
- Anyone with the code can edit the kingdom. Treat the code like a password.

### Player names

Before you can change anything, pick a display name on the names page.

- Only password-protected names (password at least 8 characters) can create or edit kingdoms. Selecting a protected name requires its password.
- An unprotected name can still be selected, but it must be protected before it can edit. Older history entries made by unprotected names are marked `(not protected)`.
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
| `make serve` | Build and start the web and database services, then follow their logs (Ctrl+C detaches, services keep running) |
| `make stop` | Stop the services (data is kept) |
| `make check` | Run ruff lint and format checks and the test suite inside Docker |
| `make migrate` | Apply database migrations |
| `make logs` | Follow service logs |
| `make reset-password NAME="Alice"` | Set a new password for a player who lost theirs (prompts for it) |

PostgreSQL is not published to the host. Only the web app listens, on `127.0.0.1:8000`. Database data lives in the `db-data` volume and uploaded character pictures in the `media-data` volume. Back up both.

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

## Settlements

Each settlement has its own page with the PF2e urban grid: 3 x 3 blocks of 2 x 2 lots, border features on each side, type, level, consumption, overcrowding, max item bonus, influence, infrastructure and ongoing events. These values are typed in by hand.

- Each side can have water, a bridge and one wall (wooden or stone). A bridge needs water on the same side. Water, bridges and walls are drawn around the grid, also in the thumbnails on the kingdom page.
- Growth rules decide where buildings may go and set the settlement type automatically. Free lots where nothing may be built are greyed out, and a line above the grid says what is allowed next.
  - A settlement's level is the number of blocks with at least one building, at most 20. It updates on its own and cannot be edited.
  - A village builds in one block only. When all 4 lots there are filled, a building in an adjacent block (sharing a side) makes it a town.
  - A town has 2 to 4 connected blocks, in any shape. When each of its 4 blocks has at least 2 lots built, the next building may go anywhere and makes it a city.
  - A city builds anywhere. Metropolis is chosen by hand once the kingdom is level 15, every block has at least 2 lots built and the settlement is not overcrowded. Extra urban grids are not supported yet.
  - Removing a building recalculates the type from the remaining buildings, except for a metropolis. Editors can still change the type by hand.
- Add or delete settlements from the kingdom sheet in edit mode. A settlement that someone else is editing cannot be deleted.
- Editing a settlement uses its own cogwheel and lock, separate from the kingdom's, so one player can edit the kingdom while another edits a settlement.
- In settlement edit mode, click a + on the grid, pick a building and a rotation, then place it. Overlapping buildings are refused.
- Building images live in `static/img/<lots>/<name>.png`, where `<lots>` is how many lots the building covers (1, 2 or 4). Add a PNG there and it appears in the picker after a rebuild. `static/img/settlement-base.png` is the empty block.

## Armies

Armies are rosters of units belonging to the kingdom, each optionally garrisoned in one of its settlements. Battles are played by hand on Roll20 with unit tokens, Strength bars and chat rolls, using the campaign's [Kingmaker Warfare](https://dnd.rigo.nu/CampaignRules/12_kingmaker_war.html) house rules (inspired by Strongholds & Followers); the app only records units and outcomes. There is no battlefield, combat engine, Roll20 sheet, API script or synchronisation.

- An army has a name, a garrison settlement (optional), a commander (one of the kingdom's characters), a location and notes. Add or delete armies in the Armies box in kingdom edit mode. An army that someone else is editing cannot be deleted. Deleting a settlement keeps its armies, without a garrison.
- Editing an army and its units uses the army's own cogwheel and lock, separate from the kingdom's and the settlements'.
- A unit has a name; a quality chosen from militia, trained, veteran or elite (or none, for units such as irregular raiders); ancestry, equipment and unit type as free text; Attack, Defense, Power, Toughness and Morale as whole numbers; a size as free text (such as "about 50 soldiers"); current and maximum Strength; status, traits and notes; and a display order. Every value is typed in; the rules page has the basic unit profiles. Strength cannot be negative, and current Strength cannot be more than maximum.
- A unit can have one **hero**, one of the kingdom's characters, who gives it +2 Morale. The table and the Roll20 summary show Morale with the hero's +2 included; the unit's own Morale is stored without it. A character can be the army's commander or one unit's hero, not both, and the hero of only one unit in the army. The commander's once-per-round advantage is tracked on Roll20, not in the app.
- A unit is marked **diminished** while its current Strength is above 0 but no more than half its maximum, rounding down. Diminished and the hero's Morale are the only values the app works out; no other statistic is derived and no category list is enforced.
- The army page shows a plain-text summary of each unit with a "Copy unit summary" button, for pasting into Roll20 chat. The text is also in a read-only box for copying by hand.
- The battle log (linked from the Kingdom box) records each battle's name, location, in-game date, opponents, outcome (victory, defeat, draw or withdrawal) and notes. Recording a battle never changes a unit: update current strength and status on the army page afterwards.
- Every change to armies, units and battles is recorded in the kingdom history.
- Recruitment, upkeep, recovery, commander bonuses and how armies connect to kingdom skills are not decided yet, so none of them are implemented.
- The fields of the older Kingmaker army sheet (level, AC, saves, HP, tactics, gear and so on) were removed in migration 0019, deleting any values they held.

## Characters

Each kingdom has its own list of characters, both player characters (PCs) and NPCs, linked as "Characters" in the Kingdom box. A character has a name, a kind (PC or NPC) and an optional picture. Leader roles on the kingdom sheet are filled by picking a character, or left vacant. Up to four filled roles can be marked invested (the Inv column); saving the sheet clears it on vacant roles. Being invested grants nothing automatically.

- Each character card lists every role the character holds: leader roles, army commands and unit heroes, each linked to its page. Nothing stops a character holding several roles, because different pages can be edited at the same time; the list makes overlaps easy to spot.
- Any protected name in the kingdom can add, rename, change, replace the picture of or delete a character. Deleting a character leaves its leader roles vacant and uninvested and removes it as army commander or unit hero.
- Uploads (JPEG, PNG, GIF or WebP, up to 10 MB) are shrunk to at most 512 pixels on the longest side and stored as WebP, which keeps them small on a Raspberry Pi and strips metadata such as GPS positions.
- Pictures are served by the app to the kingdom's members only. A reverse proxy in front of the app must accept request bodies of at least 10 MB (nginx defaults to 1 MB: set `client_max_body_size 10m;`).

## Viewing and editing

A kingdom opens read-only. The cogwheel in the top right starts editing, which locks the sheet so only one player edits at a time. Others see who is editing and how long the lock lasts.

- The lock ends when the editor presses Done, or after 15 minutes without a save. Saving or pressing Keep editing resets the timer.
- The editor sees a countdown in the top right. Typing alone does not reset it, so save regularly.
- If the timer runs out and nobody else has started editing, the editor can still save.
- Creating a kingdom opens it in edit mode.

## Lost passwords

Passwords cannot be recovered, only replaced by the host. Set a new one, then give it to the player:

```sh
make reset-password NAME="Alice"
# Without the Makefile, for example on a server:
docker compose exec web python manage.py reset_name_password "Alice"
```

The command prompts for the password twice without echoing it.

## Layout

- `config/`: Django settings and URLs.
- `kingdoms/`: models, forms, views and tests. `rules.py` holds the kingdom rules and arithmetic (Pathfinder 2e structure on the Varlyn 5e scale); `sheet.py` maps the sheet onto models and form fields.
- `templates/kingdoms/`, `static/kingdoms/`: plain HTML and CSS.
- `Dockerfile`, `docker-compose.yml`, `Makefile`: container and task setup.
- `requirements.in` and `requirements-dev.in`: dependency sources. The `.txt` files are pinned locks.

To change dependencies, edit the `.in` file and recompile the lock inside a Python 3.13 container.

## Limits

- The access code is the only secret. There is no per-user audit beyond the display name.
- History entries are never edited or deleted by the app.
- Membership is per browser session. It is not tied to a user account.
