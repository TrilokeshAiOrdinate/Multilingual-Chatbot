"""
Tool executor â€” bridges LLM tool_call objects to actual async implementations.

Every tool returns a plain string so the LLM can consume it as a tool message.
Errors are caught here and returned as descriptive strings; the agent decides
whether to retry with a different approach.
"""
import json
import logging
from retrieval.hybrid_search import hybrid_search, search_by_statute, get_related_cases as db_related
from .ecourts import fetch_ecourts_data
from .ecourt_client import (
    get_case_orders,
    get_case_history,
    sync_case,
    format_case_response,
)
from llm.client import get_embedding

logger = logging.getLogger(__name__)


async def _search_judgments(query: str, limit: int = 5) -> str:
    limit = min(int(limit), 10)
    try:
        embedding = await get_embedding(query)
        results = await hybrid_search(query, embedding, limit=limit)
        if not results:
            return "No judgments found for this query."
        parts = []
        for r in results:
            parts.append(
                f"[ID:{r['id']} | {r['court']} | {r['judgment_date']}]\n"
                f"Title: {r['title']}\n"
                f"{r['content'][:700]}"
            )
        return "\n\n---\n\n".join(parts)
    except Exception as e:
        logger.error(f"search_judgments failed: {e}", exc_info=True)
        return f"Error searching judgments: {e}"


async def _lookup_statute(act_name: str, section: str = "", limit: int = 5) -> str:
    limit = min(int(limit), 10)
    try:
        results = await search_by_statute(act_name, section, limit=limit)
        if not results:
            return f"No judgments found citing '{act_name}'" + (f" Section {section}" if section else "") + "."
        parts = []
        for r in results:
            parts.append(
                f"[ID:{r['id']} | {r['court']} | {r['judgment_date']}]\n"
                f"Title: {r['title']}\n"
                f"{r['content'][:700]}"
            )
        return "\n\n---\n\n".join(parts)
    except Exception as e:
        logger.error(f"lookup_statute failed: {e}", exc_info=True)
        return f"Error looking up statute: {e}"


async def _fetch_live_case(query: str) -> str:
    try:
        result = await fetch_ecourts_data(query)
        if not result:
            return "No live case data found on eCourts for this query."
        return (
            "AUTHENTICATION SUCCEEDED. LIVE CASE DATA RETRIEVED SUCCESSFULLY.\n"
            "Base your entire answer on the following verified data from the eCourts system:\n\n"
            + result
        )
    except Exception as e:
        logger.error(f"fetch_live_case failed: {e}", exc_info=True)
        return f"Error fetching live case data: {e}"


async def _get_case_orders(case_id: int) -> str:
    try:
        data = await get_case_orders(int(case_id))
        result = format_case_response(data, context="orders")
        return f"[eCourt API SUCCESS]\n\n{result}"
    except Exception as e:
        logger.error(f"get_case_orders failed: {e}", exc_info=True)
        return f"Error fetching case orders: {e}"


async def _get_case_history(case_id: int) -> str:
    try:
        data = await get_case_history(int(case_id))
        result = format_case_response(data, context="history")
        return f"[eCourt API SUCCESS]\n\n{result}"
    except Exception as e:
        logger.error(f"get_case_history failed: {e}", exc_info=True)
        return f"Error fetching case history: {e}"


async def _sync_case(case_id: int) -> str:
    try:
        data = await sync_case(int(case_id))
        result = format_case_response(data, context="sync")
        return f"[eCourt API SUCCESS]\n\n{result}"
    except Exception as e:
        logger.error(f"sync_case failed: {e}", exc_info=True)
        return f"Error syncing case: {e}"


async def _get_related_cases(case_id: int, limit: int = 4) -> str:
    limit = min(int(limit), 8)
    try:
        results = await db_related(int(case_id), limit=limit)
        if not results:
            return f"No related cases found for case ID {case_id}."
        parts = []
        for r in results:
            parts.append(
                f"[ID:{r['id']} | {r['court']} | {r['judgment_date']}]\n"
                f"Title: {r['title']}\n"
                f"{r['content'][:500]}"
            )
        return "\n\n---\n\n".join(parts)
    except Exception as e:
        logger.error(f"get_related_cases failed: {e}", exc_info=True)
        return f"Error fetching related cases: {e}"


_REGISTRY = {
    "search_judgments": _search_judgments,
    "lookup_statute": _lookup_statute,
    "fetch_live_case": _fetch_live_case,
    "get_case_orders": _get_case_orders,
    "get_case_history": _get_case_history,
    "sync_case": _sync_case,
    "get_related_cases": _get_related_cases,
}


async def execute_tool(name: str, arguments_json: str) -> str:
    """Parse the LLM's JSON arguments and dispatch to the correct tool."""
    if name not in _REGISTRY:
        return f"Unknown tool '{name}'. Available tools: {list(_REGISTRY.keys())}"
    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError as e:
        return f"Invalid tool arguments JSON: {e}"
    return await _REGISTRY[name](**args)

