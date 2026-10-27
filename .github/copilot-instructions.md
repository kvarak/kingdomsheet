# GitHub Copilot Instructions for Kingdom Sheet

Kingdom Sheet is a small Django web app for running the kingdom side of a Kingmaker campaign played with the Varlyn 5e rules: kingdom sheets, settlements on the urban grid, armies and characters. It is used at the table by a small group and hosted on a Raspberry Pi.

## Writing style

These apply to everything: UI text, error messages, README, docstrings, comments and commit messages.

- **No Oxford commas.** Never place a comma before the final "and" or "or" in a list.
- **No em dashes (—) or other non-standard dashes**, including en dashes (–) and Unicode minus signs (−). Use a regular spaced dash ( - ) in prose and a plain hyphen-minus for negative numbers (-4).
- Prefer **plain language** over rules jargon in the UI. Keep help text short and usable at the table.

## Kingmaker alignment

The app supports the campaign's pillars:

- exploring the Stolen Lands
- founding and growing a kingdom and its settlements
- the politics of who rules the region

- Prefer features that help run the kingdom turn, settlements, armies and leadership.
- Warn briefly when a requested feature drifts away from kingdom management, and suggest a version that fits.

## Game rules

The campaign is played in **Varlyn**, a D&D 5e setting with its own rule twists. The Varlyn rules at [dnd.rigo.nu](https://dnd.rigo.nu) are authoritative, including the campaign's [Kingmaker special rules](https://dnd.rigo.nu/CampaignRules/12_kingmaker_rules.html).

- **Varlyn 5e first.** Anything about characters, checks, combat, conditions, spells or items uses Varlyn 5e rules. Never fall back to plain 5e, Pathfinder 1e or Pathfinder 2e where Varlyn has a rule.
- **Armies** are manual rosters for battles played by hand on Roll20. Strongholds & Followers is the intended reference for units, but do not claim compatibility or implement any of its mechanics (derived statistics, category lists, casualty rules, costs, upkeep or recovery) until the user has checked the actual rules and agreed the Varlyn connection. Never mix in Kingdoms & Warfare. Do not build a battlefield, combat engine, Roll20 sheet, API script or synchronisation.
- **Kingdom subsystem.** Varlyn has no kingdom rules yet, so kingdom sheets, the urban grid and settlement growth follow the structure of the official **Pathfinder 2e** Kingmaker sheets and the rules the user has given, with the numbers converted to the Varlyn 5e scale: a proficiency bonus by level, Expertise as advantage, Improved Proficiency as +1 steps, Control DC = 12 + proficiency + size and disadvantage instead of large flat penalties. When Varlyn or the campaign rules cover any of it, they win: point out the conflict and propose the Varlyn version.
- **Converting Pathfinder material.** First say whether the source is Pathfinder 1e or 2e. Keep its story role and kingdom relevance, then convert the mechanics to fit Varlyn 5e. In the Kingmaker vault, use the `pathfinder-to-5e-conversion` skill.
- **Do not invent mechanics.** Only automate rules the user has stated, that are printed on the official sheets or that Varlyn defines. Everything else stays a field the players type in.
- When a rule is ambiguous or Varlyn and Pathfinder disagree, ask instead of guessing. The Foundry VTT PF2e system is a useful reference for how a Pathfinder kingdom rule is usually implemented; say so when following it.
- Rule data and arithmetic live in plain functions (`kingdoms/rules.py`, `kingdoms/growth.py`) so they are easy to read, test and swap for Varlyn versions.

## Code conventions

- **Minimal and readable.** One Django app (`kingdoms`), server-rendered templates, plain CSS. No SPA, frontend build or JavaScript framework; a few lines of plain JavaScript are fine where the page cannot work without them.
- **Look and layout** follow kvarak/fh-items: fieldsets with legends, a 33/67 column split, small grey hints and one blue button style for every button.
- **Everything runs in Docker.** Use the Make targets: `make serve`, `make stop`, `make check` (ruff lint and format, then the tests), `make migrate`, `make logs`. Do not install Python packages on the host.
- Run `make check` after every change and keep it passing. Add tests for new rules and views.
- Business logic goes in `services.py` and the rule modules, not in views or templates. Every change a player makes is recorded in the kingdom's history.
- **Migrations:** keep data migrations and table changes in separate migrations (PostgreSQL refuses to alter a table in the same transaction that just updated its rows). Freeze any rule logic a data migration needs inside the migration file. Check new migrations against the local database, not only the empty test database.

## Access and safety

- Kingdoms are opened with a secret access code; membership lives in the browser session. Only members may see or change a kingdom, its settlements, armies, characters and pictures.
- Only password-protected names may edit. Kingdoms, settlements and armies each have their own one-editor-at-a-time lock with a 15-minute idle timeout.
- Use Django's CSRF protection and check permissions on the server for every write.
- Never commit secrets. Read settings from environment variables.

## Raspberry Pi hosting

- The published image is multi-architecture (`linux/amd64` and `linux/arm64`). New dependencies must have arm64 wheels.
- Keep memory, disk and bandwidth low. Uploaded pictures are downscaled to WebP before they are stored.
