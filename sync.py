# ---------------------------------------------------
# Bandcamp -> Sendcloud order sync
#
# What this script does, step by step:
#   1. Logs into Bandcamp
#   2. Finds every label/band you have access to
#   3. Asks Bandcamp for all UNSHIPPED orders across all of them
#   4. Groups items back into "one order = one package"
#   5. Sends those orders to Sendcloud, so they're ready to ship
# ---------------------------------------------------
 
import requests
import config
from datetime import datetime, timezone, timedelta
 
BANDCAMP_ORDERS_URL = "https://bandcamp.com/api/merchorders/4/get_orders"
BANDCAMP_TOKEN_URL = "https://bandcamp.com/oauth_token"
BANDCAMP_ACCOUNT_URL = "https://bandcamp.com/api/account/1/my_bands"
 
SENDCLOUD_ORDERS_URL = "https://panel.sendcloud.sc/api/v3/orders"
 
# Skip orders older than this many days (roughly 5 months).
MAX_ORDER_AGE_DAYS = 150
 
# Maps each Bandcamp label/band_id to the prefix used in Sendcloud order numbers.
# Format produced: "[prefix]-[original order number]"
BAND_ID_PREFIXES = {
    792406079: "bsp",
    2897554137: "1",
    341764360: "border",
    575689618: "2",
    1870854692: "exhale",
    200023910: "involve",
    1449402291: "jizn",
    176704495: "katabasis",
    3068916041: "lenske",
    1421908456: "feed",
    3433669029: "mf",
    143765293: "mote",
    3414803877: "muscut",
    2684250839: "2",
    1367429057: "noannaos",
    1557450113: "non",
    3586623086: "os",
    3753991259: "2",
    3556950288: "phaaar",
    189594798: "1",
    1432725081: "2",
    33107976: "srn",
    776531251: "shukai",
    2977408721: "smt",
    1948782826: "mf",
    2703262393: "tlt",
    498386230: "2",
    2550321443: "2",
    4058517213: "1",
}
 
 
# ---------- Step 1: Bandcamp login ----------
 
def get_bandcamp_access_token():
    response = requests.post(
        BANDCAMP_TOKEN_URL,
        data={
            "client_id": config.BANDCAMP_CLIENT_ID,
            "client_secret": config.BANDCAMP_CLIENT_SECRET,
            "grant_type": "client_credentials",
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]
 
 
# ---------- Step 2: find all labels ----------
 
def get_label_band_ids(token):
    """
    Returns the band_id of every top-level label/band you manage.
    (These are the IDs we query orders against.)
    """
    response = requests.post(
        BANDCAMP_ACCOUNT_URL,
        headers={"Authorization": f"Bearer {token}"},
    )
    response.raise_for_status()
    bands = response.json()["bands"]
    return [band["band_id"] for band in bands]
 
 
# ---------- Step 3: fetch unshipped orders ----------
 
def get_unshipped_orders(token, band_id):
    """
    Returns a list of unshipped sale ITEMS (not grouped yet) for one label.
    """
    response = requests.post(
        BANDCAMP_ORDERS_URL,
        headers={"Authorization": f"Bearer {token}"},
        json={
            "band_id": band_id,
            "unshipped_only": True,
            "format": "json",
        },
    )
    if response.status_code != 200:
        print(f"  Warning: couldn't fetch orders for band_id {band_id}")
        print("  Bandcamp said:", response.text)
        return []
 
    data = response.json()
    items = data.get("items", [])
    for item in items:
        item["source_band_id"] = band_id
    return items
 
 
# ---------- Step 4: group items into packages ----------
 
def group_items_into_orders(items):
    """
    Bandcamp lists one row per purchased item. If someone bought a
    t-shirt AND a CD in one purchase, that's two rows sharing the
    same payment_id. We group those back into a single order.
 
    We also only keep items that are actually PAID -- Bandcamp's
    "unshipped" filter includes pending/refunded/failed payments too,
    which we don't want to send to Sendcloud for fulfillment.
    """
    orders = {}
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_ORDER_AGE_DAYS)
    skipped_old = 0
 
    for item in items:
        if item.get("payment_state") != "paid":
            continue
 
        order_date = parse_bandcamp_date(item.get("order_date"))
        if order_date and order_date < cutoff:
            skipped_old += 1
            continue
 
        payment_id = item["payment_id"]
        if payment_id not in orders:
            orders[payment_id] = {
                "payment_id": payment_id,
                "source_band_id": item.get("source_band_id"),
                "buyer_name": item.get("buyer_name"),
                "buyer_email": item.get("buyer_email"),
                "ship_to_name": item.get("ship_to_name"),
                "ship_to_street": item.get("ship_to_street"),
                "ship_to_street_2": item.get("ship_to_street_2"),
                "ship_to_city": item.get("ship_to_city"),
                "ship_to_state": item.get("ship_to_state"),
                "ship_to_zip": item.get("ship_to_zip"),
                "ship_to_country_code": item.get("ship_to_country_code"),
                "currency": item.get("currency"),
                "order_date": item.get("order_date"),
                "payment_state": item.get("payment_state"),
                "order_total": 0,
                "sale_item_ids": [],
                "line_items": [],
                "is_likely_preorder": False,
            }
 
        order = orders[payment_id]
        order["sale_item_ids"].append(item["sale_item_id"])
        order["order_total"] = round(order["order_total"] + (item.get("order_total") or 0), 2)
 
        item_name = item.get("item_name") or "Merch item"
        is_preorder_item = "pre-order" in item_name.lower() or "preorder" in item_name.lower()
        if is_preorder_item:
            order["is_likely_preorder"] = True
 
        order["line_items"].append({
            "name": item_name,
            "quantity": item.get("quantity") or 1,
            "sub_total": round(item.get("sub_total") or 0, 2),
        })
 
    if skipped_old:
        print(f"  Skipped {skipped_old} item(s) older than {MAX_ORDER_AGE_DAYS} days.")
 
    return list(orders.values())
 
 
def parse_bandcamp_date(date_str):
    """
    Bandcamp gives dates like '14 Dec 2014 23:01:10 GMT'.
    Returns a proper Python datetime, or None if there's no date.
    """
    if not date_str:
        return None
    parsed = datetime.strptime(date_str, "%d %b %Y %H:%M:%S %Z")
    return parsed.replace(tzinfo=timezone.utc)
 
 
def convert_bandcamp_date(date_str):
    """
    Sendcloud wants ISO format like '2014-12-14T23:01:10Z'.
    """
    parsed = parse_bandcamp_date(date_str)
    if not parsed:
        return datetime.now(timezone.utc).isoformat()
    return parsed.isoformat()
 
 
# ---------- Step 5: push into Sendcloud ----------
 
def build_sendcloud_order(order):
    prefix = BAND_ID_PREFIXES.get(order["source_band_id"], "unk")
    prefixed_number = f"{prefix}-{order['payment_id']}"
 
    shipping_address = {
        "name": order["ship_to_name"] or order["buyer_name"] or "Unknown",
        "address_line_1": order["ship_to_street"] or "",
        "address_line_2": order["ship_to_street_2"] or "",
        "city": order["ship_to_city"] or "",
        "postal_code": order["ship_to_zip"] or "",
        "country_code": order["ship_to_country_code"] or "",
    }
    if order["ship_to_state"] and order["ship_to_country_code"]:
        shipping_address["state_province_code"] = (
            f"{order['ship_to_country_code']}-{order['ship_to_state']}"
        )
 
    return {
        "order_id": prefixed_number,
        "order_number": prefixed_number,
        "order_details": {
            "integration": {"id": int(config.SENDCLOUD_INTEGRATION_ID)},
            "status": {
                "code": "unfulfilled",
                "message": "Awaiting fulfillment",
            },
            "order_created_at": convert_bandcamp_date(order["order_date"]),
            "tags": ["preorder"] if order["is_likely_preorder"] else [],
            "order_items": [
                {
                    "name": line["name"],
                    "quantity": line["quantity"],
                    "total_price": {
                        "value": line["sub_total"],
                        "currency": order["currency"] or "USD",
                    },
                }
                for line in order["line_items"]
            ],
        },
        "payment_details": {
            "total_price": {
                "value": order["order_total"],
                "currency": order["currency"] or "USD",
            },
            "status": {
                "code": "paid" if order["payment_state"] == "paid" else "pending",
                "message": order["payment_state"] or "pending",
            },
        },
        "shipping_address": shipping_address,
    }
 
 
def send_orders_to_sendcloud(orders):
    if not orders:
        return
 
    payload = [build_sendcloud_order(order) for order in orders]
 
    response = requests.post(
        SENDCLOUD_ORDERS_URL,
        auth=(config.SENDCLOUD_PUBLIC_KEY, config.SENDCLOUD_SECRET_KEY),
        json=payload,
    )
 
    if response.status_code not in (200, 201):
        print("  Sendcloud rejected this batch.")
        print("  Status code:", response.status_code)
        print("  Sendcloud said:", response.text)
        return
 
    print(f"  Sent {len(payload)} order(s) to Sendcloud successfully.")
 
 
# ---------- Main ----------
 
def main():
    print("Logging into Bandcamp...")
    token = get_bandcamp_access_token()
 
    print("Finding your labels/bands...")
    band_ids = get_label_band_ids(token)
    print(f"Found {len(band_ids)} labels/bands.\n")
 
    all_items = []
    for band_id in band_ids:
        items = get_unshipped_orders(token, band_id)
        if items:
            print(f"  band_id {band_id}: {len(items)} unshipped item(s)")
        all_items.extend(items)
 
    if not all_items:
        print("\nNo unshipped orders found. Nothing to sync.")
        return
 
    print(f"\nTotal unshipped items across all labels: {len(all_items)}")
 
    orders = group_items_into_orders(all_items)
    print(f"Grouped into {len(orders)} order(s) (packages).\n")
 
    print("Sending to Sendcloud...")
    # Sendcloud accepts up to 100 orders per request, so we send in batches.
    batch_size = 100
    for i in range(0, len(orders), batch_size):
        batch = orders[i:i + batch_size]
        send_orders_to_sendcloud(batch)
 
    print("\nDone!")
 
 
if __name__ == "__main__":
    main()