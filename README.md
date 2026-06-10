# Food Order — 13 June 2026

A tiny order-taking web page. No database, no dependencies — orders are
saved to `orders.txt` in this repo.

## Menu

| Item            | Price |
|-----------------|-------|
| Chicken Biryani | 11 €  |
| Veg Biryani     | 10 €  |
| Samosa          | 2 €   |
| Bread Pakoda    | 2 €   |

## Run it

```bash
python3 app.py
```

Then open http://localhost:8000. Anyone on your network can reach it at
`http://<your-ip>:8000`.

## Deploy on Render

Create a **Web Service** from this repo with:

| Setting       | Value                                       |
|---------------|---------------------------------------------|
| Runtime       | Python 3                                    |
| Build command | `pip install -r requirements.txt` (default) |
| Start command | `python3 app.py`                            |

`requirements.txt` is empty — the app uses only the standard library —
but Render requires a build command, so the default pip install is a
harmless no-op. The app binds to `0.0.0.0` and reads the port from
Render's `PORT` env var automatically.

**⚠️ Ephemeral filesystem:** on Render's free tier the disk resets on
every deploy *and* every time the idle service spins down and wakes up,
so `orders.txt` is wiped. As a safety net the app also prints every
order to stdout (lines starting with `ORDER`), so you can recover all
orders from the **Logs** tab in the Render dashboard even after a
restart. To keep the service from spinning down during the ordering
window, just open the page every ~10 minutes, or use a free uptime
pinger. (A paid persistent disk would solve it properly, but for a
one-day order the log backup is plenty.)

- The **summary at the top** shows total quantity per item, subtotals, and
  the grand total in euros.
- Each person enters their name, picks quantities, and submits.
- Every order is appended as one tab-separated line to `orders.txt`
  (timestamp, name, then a quantity per menu item), so you can read or
  edit it by hand and commit it to the repo if you want a record.

## Can I just use a WhatsApp poll instead?

Yes — and for a small group it's honestly the simplest option, with two caveats.

**The simple way (no code at all):** create a poll in the WhatsApp group
with the four items as options and enable *"Allow multiple answers"*:

> 🍽️ Food order for 13 June — vote for what you want!
> - Chicken Biryani (11 €)
> - Veg Biryani (10 €)
> - Samosa (2 €)
> - Bread Pakoda (2 €)

WhatsApp shows you the vote counts and who voted for what, which is your
summary. Caveats:

1. **No quantities.** Each person can vote for an item only once, so
   "2 samosas" isn't expressible. Workaround: post two polls (e.g. a
   second "extra portion?" poll), or have people comment quantities —
   at which point you're tallying by hand again.
2. **No automation.** The official WhatsApp Business / Cloud API does not
   support creating polls or reading poll results, so you can't pull the
   votes into a script or into `orders.txt` automatically. Unofficial
   libraries (whatsapp-web.js, Baileys) can do it, but they violate
   WhatsApp's terms of service and risk getting the number banned — not
   worth it for a lunch order.

**Rule of thumb:** if everyone orders at most one of each item, use a
WhatsApp poll and skip the web page entirely. If people order multiple
portions or you want the euro totals computed for you, run `app.py` and
share the link in the group.
