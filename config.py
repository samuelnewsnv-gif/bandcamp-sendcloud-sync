# ---------------------------------------------------
# This is the GitHub Actions version of config.py.
# Instead of hardcoded secrets, it reads them from
# environment variables, which GitHub fills in from
# the encrypted Secrets you set up in the repo settings.
#
# This file is safe to upload to GitHub -- it contains
# no actual secret values.
#
# IMPORTANT: when you upload this to GitHub, rename it
# to "config.py" (removing "_github") so sync.py can
# find it.
# ---------------------------------------------------

import os

BANDCAMP_CLIENT_ID = os.environ["BANDCAMP_CLIENT_ID"]
BANDCAMP_CLIENT_SECRET = os.environ["BANDCAMP_CLIENT_SECRET"]

SENDCLOUD_PUBLIC_KEY = os.environ["SENDCLOUD_PUBLIC_KEY"]
SENDCLOUD_SECRET_KEY = os.environ["SENDCLOUD_SECRET_KEY"]
SENDCLOUD_INTEGRATION_ID = os.environ["SENDCLOUD_INTEGRATION_ID"]
