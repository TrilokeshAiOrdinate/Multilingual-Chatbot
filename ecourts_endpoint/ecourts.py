"""
eCourts data fetcher.

Delegates to the LegTech REST API client (scraper/ecourt_client.py).
The old Playwright-based scraper is preserved as a commented fallback.
"""
import logging
import re

from .settings import settings
from .ecourt_client import (
    fetch_by_cnr,
    get_case_details,
    format_case_response,
)

logger = logging.getLogger(__name__)

# CNR numbers are 16-character alphanumeric codes, e.g. MHAU010012342023
_CNR_RE = re.compile(r"^[A-Z]{4}\d{12}$", re.IGNORECASE)


def _looks_like_cnr(query: str) -> bool:
    return bool(_CNR_RE.match(query.strip()))


async def fetch_ecourts_data(query: str) -> str | None:
    """
    Entry point called by the tool executor.

    Strategy:
      1. If the query looks like a CNR number â†’ POST /ecourt/fetch-by-cnr
      2. Otherwise try to extract a numeric case_id from the query and call
         GET /ecourt/cases/{id}/ecourt-data
      3. Return a formatted plain-text summary ready for the LLM.
    """
    if not settings.ENABLE_ECourts:
        return None

    query = query.strip()

    try:
        if _looks_like_cnr(query):
            logger.info("eCourt: CNR lookup for %s", query)
            data = await fetch_by_cnr(query)
            return format_case_response(data, context="cnr")

        # Try to pull a numeric ID out of a query like "case 4521" or "id:4521"
        id_match = re.search(r"\b(\d{3,10})\b", query)
        if id_match:
            case_id = int(id_match.group(1))
            logger.info("eCourt: case details lookup for id=%d", case_id)
            data = await get_case_details(case_id)
            return format_case_response(data, context="details")

        logger.warning("eCourt: cannot determine lookup type for query=%r", query)
        return (
            "Could not determine the case identifier from your query. "
            "Please provide a CNR number (e.g. MHAU010012342023) or a numeric case ID."
        )

    except RuntimeError as e:
        logger.error("eCourt API error: %s", e)
        return f"eCourt API returned an error: {e}"
    except Exception as e:
        logger.error("eCourt fetch failed: %s", e, exc_info=True)
        return f"Failed to fetch eCourt data: {e}"

