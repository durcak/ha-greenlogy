"""Konštanty pre integráciu Greenlogy."""

from datetime import timedelta

DOMAIN = "greenlogy"

API_URL = "https://api.greenlogy.com/api/v1"
API_VERSION = "v1.1.0"
CLIENT_ID = "zmluvyWebApp"
ORGANIZATION_ID = "00000000-0000-0000-0000-000000000001"

UPDATE_INTERVAL = timedelta(hours=3)

# Od kedy sa pri prvom spustení sťahuje hodinová história z elektromera.
HISTORY_START = "2024-11-01"

STAT_IMPORT = "grid_import"
STAT_EXPORT = "grid_export"
