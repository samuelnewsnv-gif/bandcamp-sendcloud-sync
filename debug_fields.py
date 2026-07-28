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

    # Use any band_id you know has at least one unshipped order.
    # Eskimo (575689618) had orders in your earlier tests.
    band_id = 575689618

    response = requests.post(
        "https://bandcamp.com/api/merchorders/4/get_orders",
        headers={"Authorization": f"Bearer {token}"},
        json={"band_id": band_id, "unshipped_only": True, "format": "json"},
    )
    response.raise_for_status()
    items = response.json().get("items", [])

    if not items:
        print(f"No unshipped items found for band_id {band_id}.")
        print("Edit this script and try a different band_id from your earlier list.")
    else:
        first_item = items[0]
        print("Field names found on this order (values hidden for privacy):\n")
        for key in sorted(first_item.keys()):
            value = first_item[key]
            value_type = type(value).__name__
            is_empty = value in (None, "", [])
            print(f"  {key}  (type: {value_type}, empty: {is_empty})")
