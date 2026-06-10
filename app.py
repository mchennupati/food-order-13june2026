#!/usr/bin/env python3
"""Simple order taker for the 13 June 2026 food order.

Run with:  python3 app.py
Then open: http://localhost:8000

Orders are appended to orders.txt (tab-separated: timestamp, name,
then one quantity column per menu item). No database needed.
"""

import html
import os
import threading
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

# Render (and most PaaS hosts) tell us which port to bind via $PORT
PORT = int(os.environ.get("PORT", 8000))
ORDERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orders.txt")

# (key, label, price in euros)
MENU = [
    ("chicken_biryani", "Chicken Biryani", 11),
    ("veg_biryani", "Veg Biryani", 10),
    ("samosa", "Samosa", 2),
    ("bread_pakoda", "Bread Pakoda", 2),
]


# Serializes file writes; the server is threaded so two requests can
# touch orders.txt at the same time otherwise.
FILE_LOCK = threading.Lock()


def read_orders():
    """Return a list of orders: {time, name, items: {key: qty}}."""
    orders = []
    if not os.path.exists(ORDERS_FILE):
        return orders
    with open(ORDERS_FILE, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 2 + len(MENU):
                continue  # skip malformed/comment lines
            time_str, name = parts[0], parts[1]
            items = {}
            for (key, _, _), qty_str in zip(MENU, parts[2:]):
                try:
                    qty = int(qty_str)
                except ValueError:
                    qty = 0
                if qty > 0:
                    items[key] = qty
            if items:
                orders.append({"time": time_str, "name": name, "items": items})
    return orders


def append_order(name, items):
    quantities = [str(items.get(key, 0)) for key, _, _ in MENU]
    line = "\t".join([datetime.now().strftime("%Y-%m-%d %H:%M"), name] + quantities)
    with FILE_LOCK:
        with open(ORDERS_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    # Also log to stdout: on hosts with an ephemeral filesystem (e.g. Render
    # free tier) orders.txt is wiped on restart, but the host's log page
    # keeps these lines so orders can be recovered.
    print(f"ORDER\t{line}", flush=True)


def delete_order(idx, name):
    """Delete order number idx (0-based, as displayed) if the name matches.

    The name check guards against deleting the wrong row when someone
    else's add/delete shifted the indices between page load and click.
    """
    with FILE_LOCK:
        orders = read_orders()
        if not (0 <= idx < len(orders)) or orders[idx]["name"] != name:
            return False
        deleted = orders.pop(idx)
        with open(ORDERS_FILE, "w", encoding="utf-8") as f:
            for order in orders:
                quantities = [str(order["items"].get(key, 0)) for key, _, _ in MENU]
                f.write("\t".join([order["time"], order["name"]] + quantities) + "\n")
    print(f"DELETE\t{deleted['time']}\t{deleted['name']}", flush=True)
    return True


def order_total(items):
    return sum(qty * price for key, _, price in MENU for k, qty in items.items() if k == key)


def render_page():
    orders = read_orders()

    # Summary: total quantity per item and grand total
    totals = {key: 0 for key, _, _ in MENU}
    for order in orders:
        for key, qty in order["items"].items():
            totals[key] += qty
    grand_total = sum(totals[key] * price for key, _, price in MENU)

    summary_rows = ""
    for key, label, price in MENU:
        if totals[key]:
            summary_rows += (
                f"<tr><td>{label}</td><td>{totals[key]}</td>"
                f"<td>{totals[key] * price} &euro;</td></tr>"
            )
    if not summary_rows:
        summary_rows = '<tr><td colspan="3">No orders yet</td></tr>'

    order_rows = ""
    for idx, order in enumerate(orders):
        item_list = ", ".join(
            f"{order['items'][key]}&times; {label}"
            for key, label, _ in MENU if key in order["items"]
        )
        safe_name = html.escape(order["name"], quote=True)
        # Escape for the JS string first (backslashes and quotes), then for
        # HTML — the browser decodes entities in the attribute before the
        # JS engine sees the string.
        msg = (
            f"You are deleting {order['name']}'s order "
            f"({order_total(order['items'])} euros). Continue?"
        )
        confirm_msg = html.escape(
            msg.replace("\\", "\\\\").replace("'", "\\'"), quote=True
        )
        order_rows += (
            f"<tr><td>{html.escape(order['name'])}</td><td>{item_list}</td>"
            f"<td>{order_total(order['items'])} &euro;</td>"
            f"<td>{html.escape(order['time'])}</td>"
            f'<td><form method="post" action="/delete" '
            f"onsubmit=\"return confirm('{confirm_msg}')\">"
            f'<input type="hidden" name="idx" value="{idx}">'
            f'<input type="hidden" name="name" value="{safe_name}">'
            f'<button type="submit" class="delete">Delete</button>'
            f"</form></td></tr>"
        )

    menu_inputs = ""
    for key, label, price in MENU:
        menu_inputs += f"""
        <div class="item">
          <span class="item-label">{label} ({price} &euro;)</span>
          <span class="stepper">
            <button type="button" aria-label="one less {label}" onclick="step('{key}', -1)">&minus;</button>
            <input type="number" id="{key}" name="{key}" min="0" max="20" value="0" inputmode="numeric" readonly>
            <button type="button" aria-label="one more {label}" onclick="step('{key}', 1)">+</button>
          </span>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Food Order &ndash; 13 June 2026</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 700px; margin: 2rem auto; padding: 0 1rem; color: #222; }}
  h1 {{ font-size: 1.5rem; }}
  h2 {{ font-size: 1.15rem; margin-top: 2rem; }}
  table {{ border-collapse: collapse; width: 100%; margin: 0.5rem 0 1rem; }}
  th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; }}
  th {{ background: #f3f3f3; }}
  .summary {{ background: #f0f7f0; border: 1px solid #b8d8b8; border-radius: 8px; padding: 1rem; }}
  .summary .grand {{ font-size: 1.2rem; font-weight: bold; }}
  .item {{ display: flex; justify-content: space-between; align-items: center; margin: 0.6rem 0; gap: 0.5rem; }}
  .item-label {{ flex: 1; }}
  .stepper {{ display: flex; align-items: center; gap: 0.3rem; }}
  .stepper button {{ width: 2.8rem; height: 2.8rem; font-size: 1.5rem; line-height: 1;
                     background: #eee; color: #222; border: 1px solid #bbb; border-radius: 8px;
                     padding: 0; touch-action: manipulation; }}
  .stepper button:hover {{ background: #ddd; }}
  .stepper input {{ width: 2.5rem; height: 2.6rem; text-align: center; font-size: 1.2rem;
                    border: 1px solid #ccc; border-radius: 6px; background: #fff;
                    -moz-appearance: textfield; appearance: textfield; }}
  .stepper input::-webkit-outer-spin-button,
  .stepper input::-webkit-inner-spin-button {{ -webkit-appearance: none; margin: 0; }}
  form {{ border: 1px solid #ddd; border-radius: 8px; padding: 1rem; }}
  input[type=text] {{ width: 100%; padding: 0.4rem; box-sizing: border-box; margin: 0.3rem 0 0.8rem; }}
  button {{ background: #2d7a2d; color: white; border: none; padding: 0.6rem 1.4rem; border-radius: 6px; font-size: 1rem; cursor: pointer; }}
  button:hover {{ background: #246324; }}
  button.delete {{ background: #b33; padding: 0.25rem 0.7rem; font-size: 0.85rem; }}
  button.delete:hover {{ background: #922; }}
  td form {{ border: none; padding: 0; margin: 0; }}
</style>
</head>
<body>
<h1>Food Order &ndash; 13 June 2026</h1>

<h2>Add your order</h2>
<form method="post" action="/">
  <label for="name">Your name</label>
  <input type="text" id="name" name="name" required maxlength="60" placeholder="e.g. Murali">
  {menu_inputs}
  <button type="submit">Add order</button>
</form>

<h2>Orders so far</h2>
<table>
  <tr><th>Name</th><th>Items</th><th>Total</th><th>Time</th><th></th></tr>
  {order_rows or '<tr><td colspan="5">No orders yet</td></tr>'}
</table>

<div class="summary">
  <h2 style="margin-top:0">Summary</h2>
  <table>
    <tr><th>Item</th><th>Qty</th><th>Subtotal</th></tr>
    {summary_rows}
  </table>
  <div class="grand">Total: {grand_total} &euro; &middot; {len(orders)} order(s)</div>
</div>

<script>
function step(id, delta) {{
  var input = document.getElementById(id);
  var value = parseInt(input.value, 10) || 0;
  input.value = Math.min(20, Math.max(0, value + delta));
}}
</script>
</body>
</html>"""


class OrderHandler(BaseHTTPRequestHandler):
    def _send_html(self, content, status=200):
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send_html(render_page())
        else:
            self._send_html("<h1>404 Not Found</h1>", status=404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        name = form.get("name", [""])[0].strip().replace("\t", " ")

        if self.path == "/delete":
            try:
                idx = int(form.get("idx", ["-1"])[0])
            except ValueError:
                idx = -1
            delete_order(idx, name)
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return

        items = {}
        for key, _, _ in MENU:
            try:
                qty = int(form.get(key, ["0"])[0])
            except ValueError:
                qty = 0
            if qty > 0:
                items[key] = min(qty, 20)
        if name and items:
            append_order(name, items)
        # Redirect back so refreshing doesn't resubmit the order
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def log_message(self, fmt, *args):
        pass  # keep the console quiet


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), OrderHandler)
    print(f"Order taker running on port {PORT}", flush=True)
    print(f"Orders are saved to {ORDERS_FILE}", flush=True)
    server.serve_forever()
