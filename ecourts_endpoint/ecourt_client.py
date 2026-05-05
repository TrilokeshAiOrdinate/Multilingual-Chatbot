"""
Async HTTP client for the LegTech eCourt API.

Base URL: https://legtech-backend.azurewebsites.net

Endpoints supported:
  POST /ecourt/fetch-by-cnr          â†’ fetch case by CNR number
  GET  /ecourt/cases/{id}/ecourt-data â†’ full case details
  GET  /ecourt/cases/{id}/orders      â†’ list of orders
  GET  /ecourt/cases/{id}/history     â†’ hearing history
  POST /ecourt/cases/{id}/sync        â†’ sync case from eCourts portal
  POST /ecourt/download-order         â†’ download a specific order
"""
import logging
from typing import Any

import httpx

from .settings import settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_MAX_RETRIES = 2

# In-memory token cache (refreshed on 401)
_token: str | None = None


async def _login() -> str:
    """Obtain a Bearer token via OAuth2 password flow and cache it."""
    global _token
    url = f"{settings.ECOURT_BASE_URL}/auth/login"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            url,
            data={
                "username": settings.ECOURT_USERNAME,
                "password": settings.ECOURT_PASSWORD,
                "grant_type": "password",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if resp.status_code != 200:
        raise RuntimeError(
            f"eCourt login failed ({resp.status_code}): {resp.text[:300]}"
        )
    _token = resp.json()["access_token"]
    logger.info("eCourt: token obtained successfully")
    return _token


async def _auth_headers() -> dict[str, str]:
    global _token
    if not _token:
        await _login()
    return {"Content-Type": "application/json", "Authorization": f"Bearer {_token}"}


async def _get(path: str) -> dict[str, Any]:
    global _token
    url = f"{settings.ECOURT_BASE_URL}{path}"
    for attempt in range(1, _MAX_RETRIES + 2):
        try:
            headers = await _auth_headers()
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url, headers=headers)
            if resp.status_code == 401:
                logger.warning("eCourt: token expired, re-authenticatingâ€¦")
                _token = None
                headers = await _auth_headers()
                async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                    resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException:
            if attempt > _MAX_RETRIES:
                raise
            logger.warning("GET %s timed out (attempt %d), retryingâ€¦", path, attempt)
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"eCourt API error {e.response.status_code}: {e.response.text[:300]}"
            ) from e


async def _post(path: str, body: dict | None = None) -> dict[str, Any]:
    global _token
    url = f"{settings.ECOURT_BASE_URL}{path}"
    for attempt in range(1, _MAX_RETRIES + 2):
        try:
            headers = await _auth_headers()
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(url, headers=headers, json=body or {})
            if resp.status_code == 401:
                logger.warning("eCourt: token expired, re-authenticatingâ€¦")
                _token = None
                headers = await _auth_headers()
                async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                    resp = await client.post(url, headers=headers, json=body or {})
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException:
            if attempt > _MAX_RETRIES:
                raise
            logger.warning("POST %s timed out (attempt %d), retryingâ€¦", path, attempt)
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"eCourt API error {e.response.status_code}: {e.response.text[:300]}"
            ) from e


# â”€â”€ Public helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def fetch_by_cnr(cnr_number: str) -> dict[str, Any]:
    """Fetch case data by CNR number (creates or updates the case record)."""
    return await _post("/ecourt/fetch-by-cnr", {"cnr": cnr_number.strip().upper()})


async def get_case_details(case_id: int | str) -> dict[str, Any]:
    """Retrieve full eCourt data for a stored case."""
    return await _get(f"/ecourt/cases/{case_id}/ecourt-data")


async def get_case_orders(case_id: int | str) -> dict[str, Any]:
    """Retrieve the list of orders for a case."""
    return await _get(f"/ecourt/cases/{case_id}/orders")


async def get_case_history(case_id: int | str) -> dict[str, Any]:
    """Retrieve the hearing / cause-list history for a case."""
    return await _get(f"/ecourt/cases/{case_id}/history")


async def sync_case(case_id: int | str) -> dict[str, Any]:
    """Trigger a fresh sync of a case from the eCourts portal."""
    return await _post(f"/ecourt/cases/{case_id}/sync")


async def download_order(payload: dict) -> dict[str, Any]:
    """Download a specific order document."""
    return await _post("/ecourt/download-order", payload)


# â”€â”€ Formatting helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _fmt_case_summary(raw: dict) -> str:
    """
    Convert raw API response into a readable case summary.

    The LegTech API returns:
      { success, cnr_number, case_status, next_hearing_date,
        data: { court_name, case_details: {...}, status: {...},
                acts: [...], parties: {...}, history: [...], orders: [...] } }
    """
    lines: list[str] = []

    # Unwrap top-level envelope
    inner: dict = raw.get("data") or raw

    # â”€â”€ Basic identifiers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    cnr = raw.get("cnr_number") or inner.get("cnr_number") or "N/A"
    court = inner.get("court_name") or "N/A"

    case_details: dict = inner.get("case_details") or {}
    case_type = case_details.get("Case Type") or "N/A"
    filing_num = case_details.get("Filing Number") or "N/A"
    filing_date = case_details.get("Filing Date") or "N/A"
    reg_num = case_details.get("Registration Number") or "N/A"

    lines.append(f"**CNR:** {cnr}")
    lines.append(f"**Court:** {court}")
    lines.append(f"**Case Type:** {case_type}")
    lines.append(f"**Filing Number:** {filing_num}  |  **Registration:** {reg_num}")
    lines.append(f"**Filed:** {filing_date}")

    # â”€â”€ Status block â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    status_block: dict = inner.get("status") or {}
    if status_block:
        case_status = status_block.get("Case Status") or raw.get("case_status") or "N/A"
        next_date = status_block.get("Next Hearing Date") or raw.get("next_hearing_date") or "N/A"
        disposal = status_block.get("Nature of Disposal") or ""
        first_hearing = status_block.get("First Hearing Date") or ""
        decision_date = status_block.get("Decision Date") or ""

        lines.append(f"**Status:** {case_status}")
        if first_hearing:
            lines.append(f"**First Hearing:** {first_hearing}")
        if decision_date:
            lines.append(f"**Decision Date:** {decision_date}")
        if disposal:
            lines.append(f"**Disposal:** {disposal}")
        lines.append(f"**Next Hearing:** {next_date}")
    else:
        lines.append(f"**Status:** {raw.get('case_status') or 'N/A'}")
        lines.append(f"**Next Hearing:** {raw.get('next_hearing_date') or 'N/A'}")

    # â”€â”€ Parties â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    parties: dict = inner.get("parties") or {}
    petitioners = parties.get("petitioner") or []
    respondents = parties.get("respondent") or []
    if petitioners:
        names = ", ".join(p.get("party_name", "") for p in petitioners if p.get("party_name"))
        lines.append(f"**Petitioner(s):** {names}")
    if respondents:
        names = ", ".join(r.get("party_name", "") for r in respondents if r.get("party_name"))
        lines.append(f"**Respondent(s):** {names}")

    # â”€â”€ Acts / Sections â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    acts = inner.get("acts") or []
    if acts:
        act_strs = [f"{a.get('act', '')} Â§ {a.get('sections', '')}".strip(" Â§") for a in acts]
        lines.append(f"**Acts/Sections:** {' | '.join(act_strs)}")

    # â”€â”€ Hearing history â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    history = inner.get("history") or []
    if history:
        lines.append(f"\n**Hearing History ({len(history)} entries):**")
        for h in history[-5:]:
            h_date = h.get("judge") or h.get("hearing_date") or "?"
            h_business = h.get("business_on_date") or h.get("purpose_of_hearing") or ""
            lines.append(f"  â€¢ [{h_date}] {h_business}")

    # â”€â”€ Orders â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    orders = inner.get("orders") or []
    if orders:
        lines.append(f"\n**Orders ({len(orders)}):**")
        for o in orders[:5]:
            o_date = o.get("order_date") or o.get("date") or "?"
            o_text = (o.get("order_text") or o.get("text") or "")[:200]
            lines.append(f"  â€¢ [{o_date}] {o_text}")
    else:
        lines.append("\n**Orders:** None on record")

    return "\n".join(lines)


def format_case_response(data: dict, context: str = "details") -> str:
    """
    Public formatter called by the tool executor.

    Args:
        data:    Raw dict from any eCourt API endpoint.
        context: One of 'details', 'orders', 'history', 'cnr', 'sync'.
    """
    if not data:
        return "No data returned from eCourt API."

    if context in ("cnr", "details", "sync"):
        return _fmt_case_summary(data)

    inner = data.get("data") or data

    if context == "orders":
        orders = inner.get("orders") or (data if isinstance(data, list) else [])
        if not orders:
            return "No orders found for this case."
        lines = [f"**Orders ({len(orders)}):**"]
        for o in orders:
            o_date = o.get("order_date") or o.get("date") or "?"
            o_text = (o.get("order_text") or o.get("text") or "")[:300]
            lines.append(f"\n[{o_date}]\n{o_text}")
        return "\n".join(lines)

    if context == "history":
        history = inner.get("history") or (data if isinstance(data, list) else [])
        if not history:
            return "No hearing history found for this case."
        lines = [f"**Hearing History ({len(history)} entries):**"]
        for h in history:
            h_date = h.get("judge") or h.get("hearing_date") or h.get("date") or "?"
            h_purpose = h.get("business_on_date") or h.get("purpose_of_hearing") or "N/A"
            lines.append(f"  [{h_date}] {h_purpose}")
        return "\n".join(lines)

    return str(inner)

