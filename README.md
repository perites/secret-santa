# Secret Santa

A small Flask app for a fixed group of people. Each participant gets a personal
link, fills in a wishlist of up to 3 items, and picks who they will give a gift
to. Nobody, including the admin, can see who picked whom.

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows; use `source .venv/bin/activate` elsewhere
pip install -r requirements.txt
cp .env.example .env          # then set ADMIN_PIN in .env
python app.py                 # http://127.0.0.1:5003
```

The database (`instance/santa.db`) and tables are created on first start.

## Configuration

Settings live in `config.py`; any of them can be overridden in `.env`:

| Variable | Default | Meaning |
| --- | --- | --- |
| `ADMIN_PIN` | empty (admin disabled) | PIN for `/admin` |
| `DEADLINE` | `2026-12-15T23:59:59` | Last moment to pick, change a pick or edit a wishlist (server local time) |
| `GIFT_BUDGET` | `25-30 euro` | Price range shown next to the deadline; empty hides it |
| `PUBLIC_URL` | empty | Address used in invite links, e.g. `https://santa.example.com` |
| `SECRET_KEY` | generated into `instance/secret_key` | Signs session cookies |
| `SESSION_COOKIE_SECURE` | off | Set to `1` when serving over HTTPS |
| `HOST` / `PORT` / `FLASK_DEBUG` | `127.0.0.1` / `5003` / off | Used by `python app.py` |

## Running the exchange

1. Open `/admin`, enter the PIN and add every participant (name, optional
   photo, optional wishes).
2. Copy each person's link and send it to them **privately**. Opening the link
   signs that browser in as that person for a year; whoever has the link can
   act as that person.
3. Participants edit their wishlist and pick someone until the deadline. After
   the deadline everything is locked for participants; the admin can still edit.
4. If a link leaks or someone switches devices and lost it, use **New link** in
   the admin panel. The old link stops working and signs out every browser that
   used it. Their pick and wishlist are kept.

The admin panel shows whether each person has opened their link, and how many
people have picked in total, but not who has picked, so pairs can't be deduced.
Anyone with direct access to `santa.db` can still see the pairs.

## Tests

```bash
python verify.py
```

Uses an in-memory database, so it doesn't touch `santa.db` and needs no running server.
