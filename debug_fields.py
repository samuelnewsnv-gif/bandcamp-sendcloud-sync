# ---------------------------------------------------
# One-time diagnostic: prints the FIELD NAMES Bandcamp
# returns for a real order -- not the actual values,
# so nothing private gets shown. This helps us find
# the exact name of the "shipping address phone" field.
# ---------------------------------------------------

import requests
import config

def get_bandcamp_access_token():
    response = requests.post(
        "https://bandcamp.com/oauth_token",
        data={
            "client_id": config.BANDCAMP_CLIENT_ID,
            "client_secret": config.BANDCAMP_CLIENT_SECRET,
            "grant_type": "client_credentials",
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]


if __name__ == "__main__":
    token = get_bandcamp_access_token()

    band_ids_response = requests.post(
        "https://bandcamp.com/api/account/1/my_bands",
        headers={"Authorization": f"Bearer {token}"},
    )
    band_ids_response.raise_for_status()
    band_ids = [b["band_id"] for b in band_ids_response.json()["bands"]]

    for band_id in band_ids:
        response = requests.post(
            "https://bandcamp.com/api/merchorders/4/get_orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"band_id": band_id, "unshipped_only": True, "format": "json"},
        )
        response.raise_for_status()
        items = response.json().get("items", [])

        for item in items:
            sub_total = item.get("sub_total")
            if sub_total in (None, 0, "0", ""):
                print(f"--- band_id {band_id}, sale_item_id {item.get('sale_item_id')} ---")
                print(f"  item_name: {item.get('item_name')!r}")
                print(f"  sub_total: {sub_total!r}")
                print(f"  order_total: {item.get('order_total')!r}")
                print(f"  discount_code: {item.get('discount_code')!r}")
                print(f"  quantity: {item.get('quantity')!r}")
                print(f"  currency: {item.get('currency')!r}")
                print()

    print("Done. Anything printed above is an item with a missing/zero sub_total.")
