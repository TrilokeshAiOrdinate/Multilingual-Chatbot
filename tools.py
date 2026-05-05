"""
Tool Wrapper Classes for Legal Data Sources
Handles all external API calls (eCourts, MasterDB, Law Dictionary)
"""

import os
import json
import logging
import requests
import re
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


# =============================================================================
# BASE TOOL CLASS
# =============================================================================

class BaseTool(ABC):
    """Abstract base class for all legal data tools"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    @abstractmethod
    def search(self, query: str, **kwargs) -> Dict[str, Any]:
        """Execute search operation"""
        pass
    
    def format_results(self, results: Any) -> Dict[str, Any]:
        """Format results with metadata"""
        return {
            "tool": self.name,
            "status": "success",
            "data": results,
            "source": self.name
        }
    
    def format_error(self, error: str) -> Dict[str, Any]:
        """Format error response"""
        logger.error(f"[{self.name}] {error}")
        return {
            "tool": self.name,
            "status": "error",
            "error": error,
            "source": self.name
        }


# =============================================================================
# LAW DICTIONARY TOOL
# =============================================================================

class LawDictionaryTool(BaseTool):
    """
    Tool for searching legal terms and definitions
    Uses local law dictionary with hybrid search (vector + semantic)
    """
    
    def __init__(self):
        super().__init__(
            name="LAW_DICTIONARY",
            description="Search legal terms, definitions, and meanings"
        )
    
    def search(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Search law dictionary for terms and definitions
        
        Args:
            query: Search query for legal terms
            top_k: Number of top results to return
        
        Returns:
            Dictionary with formatted results
        """
        try:
            logger.info(f"[{self.name}] Searching for: {query}")
            from hybrid_search import hybrid_search as dictionary_hybrid_search

            results = dictionary_hybrid_search(query, top_k=top_k)
            
            if not results:
                return self.format_error("No terms found in dictionary")
            
            formatted_results = [
                {
                    "term": result.get("term", ""),
                    "definition": result.get("definition", ""),
                    "part_of_speech": result.get("part_of_speech", ""),
                    "confidence_score": result.get("confidence_score", 0)
                }
                for result in results
            ]
            
            return {
                "tool": self.name,
                "status": "success",
                "query": query,
                "count": len(formatted_results),
                "data": formatted_results,
                "source": "Local Law Dictionary"
            }
        
        except Exception as e:
            return self.format_error(f"Dictionary search failed: {str(e)}")


# =============================================================================
# eCOURTS TOOL (LIVE LEGTECH API)
# =============================================================================

class eCourtsToolBase(BaseTool):
    """Tool for fetching live case data from the LegTech eCourt API."""

    def __init__(self):
        super().__init__(
            name="eCOURTS",
            description="Fetch live case status by CNR number or numeric case ID"
        )
        self.ecourt_base_url = os.getenv("ECOURT_BASE_URL", "https://legtech-backend.azurewebsites.net").rstrip("/")
        self.ecourt_username = os.getenv("ECOURT_USERNAME", "")
        self.ecourt_password = os.getenv("ECOURT_PASSWORD", "")
        self._token = None

    def search(self, query: str, cnr_number: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Fetch live case data using a CNR number or numeric case ID from the query."""
        try:
            if not self.ecourt_username or not self.ecourt_password:
                return self.format_error("Missing ECOURT_USERNAME or ECOURT_PASSWORD in .env")

            lookup = (cnr_number or self._extract_cnr(query) or "").strip()
            if lookup:
                logger.info(f"[{self.name}] Fetching live case by CNR: {lookup}")
                data = self._post("/ecourt/fetch-by-cnr", {"cnr": lookup.upper()})
                return self._format_case_result(query, data, lookup_type="cnr", lookup_value=lookup)

            case_id = self._extract_case_id(query)
            if case_id:
                logger.info(f"[{self.name}] Fetching live case by case ID: {case_id}")
                data = self._get(f"/ecourt/cases/{case_id}/ecourt-data")
                return self._format_case_result(query, data, lookup_type="case_id", lookup_value=case_id)

            return self.format_error(
                "Provide a 16-character CNR number like MHAU010012342023 or a numeric case ID."
            )

        except requests.exceptions.RequestException as e:
            return self.format_error(f"eCourt API request failed: {str(e)}")
        except Exception as e:
            return self.format_error(f"eCourts search failed: {str(e)}")

    def _authenticate(self) -> str:
        if self._token:
            return self._token

        response = requests.post(
            f"{self.ecourt_base_url}/auth/login",
            data={
                "username": self.ecourt_username,
                "password": self.ecourt_password,
                "grant_type": "password",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        response.raise_for_status()
        self._token = response.json()["access_token"]
        return self._token

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._authenticate()}",
        }

    def _get(self, path: str) -> Dict[str, Any]:
        response = requests.get(f"{self.ecourt_base_url}{path}", headers=self._headers(), timeout=30)
        if response.status_code == 401:
            self._token = None
            response = requests.get(f"{self.ecourt_base_url}{path}", headers=self._headers(), timeout=30)
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(f"{self.ecourt_base_url}{path}", headers=self._headers(), json=payload, timeout=30)
        if response.status_code == 401:
            self._token = None
            response = requests.post(f"{self.ecourt_base_url}{path}", headers=self._headers(), json=payload, timeout=30)
        response.raise_for_status()
        return response.json()

    def _extract_cnr(self, query: str) -> Optional[str]:
        match = re.search(r"\b[A-Z]{4}\d{12}\b", query, re.IGNORECASE)
        return match.group(0).upper() if match else None

    def _extract_case_id(self, query: str) -> Optional[str]:
        match = re.search(r"\b(?:case\s*id|id|case)\s*[:#-]?\s*(\d{3,10})\b", query, re.IGNORECASE)
        if match:
            return match.group(1)
        fallback = re.search(r"\b(\d{3,10})\b", query)
        return fallback.group(1) if fallback else None

    def _format_case_result(self, query: str, data: Dict[str, Any], lookup_type: str, lookup_value: str) -> Dict[str, Any]:
        return {
            "tool": self.name,
            "status": "success",
            "query": query,
            "lookup_type": lookup_type,
            "lookup_value": lookup_value,
            "data": data,
            "source": "LegTech eCourt API",
            "endpoint": self.ecourt_base_url,
        }

# =============================================================================
# MASTERDB TOOL (Knowledge Base for Historical Cases)
# =============================================================================

class MasterDBTool(BaseTool):
    """
    Tool for searching historical cases, precedents, and case law
    Searches the MasterDB via API endpoint using hybrid search.
    
    NOTE: This tool calls the MasterDB API endpoint directly
    instead of importing functions. This ensures separation of concerns
    and allows MasterDB to run as an independent microservice.
    """
    
    def __init__(self):
        super().__init__(
            name="MASTERDB",
            description="Search Indian central/state acts and legal knowledge base"
        )
        # MasterDB API URL - defaults to localhost if not configured
        self.masterdb_api_url = os.getenv("MASTERDB_API_URL", "http://localhost:8001")
        logger.info(f"[MASTERDB] Configured API URL: {self.masterdb_api_url}")
    
    def search(self, query: str, top_k: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        """
        Search MasterDB via API endpoint for Indian legal documents using hybrid search.
        
        Args:
            query: Search query for legal documents
            top_k: Optional number of results to return
        
        Returns:
            Legal documents from the MasterDB search
        """
        try:
            logger.info(f"[{self.name}] Searching via API for: {query}")
            logger.info(f"[{self.name}] API Endpoint: {self.masterdb_api_url}/search")
            
            # Build the API request
            params = {"query": query}
            if top_k is None:
                top_k = self._default_top_k(query)
            if top_k is not None:
                params["top_k"] = top_k
            
            # Call the MasterDB API endpoint
            response = requests.get(
                f"{self.masterdb_api_url}/search",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            api_response = response.json()
            
            # Extract results from API response
            results = api_response.get("results", [])
            
            logger.info(f"[{self.name}] API returned {len(results)} results")
            
            # Format results
            formatted_results = [
                {
                    "id": result.get("id", ""),
                    "act": result.get("act", ""),
                    "jurisdiction": result.get("jurisdiction", ""),
                    "doc_id": result.get("doc_id", ""),
                    "date": result.get("date", ""),
                    "translated": result.get("translated"),
                    "score": result.get("score", 0),
                    "text": result.get("text", "")
                }
                for result in results
            ]
            
            return {
                "tool": self.name,
                "status": "success",
                "query": query,
                "count": len(formatted_results),
                "data": formatted_results,
                "source": "MasterDB API",
                "search_method": "Hybrid keyword + vector search with metadata filters",
                "api_response_time": api_response.get("search_time_sec", "N/A")
            }
        
        except requests.exceptions.ConnectionError as e:
            logger.error(f"[{self.name}] Connection error - API unreachable at {self.masterdb_api_url}")
            logger.error(f"[{self.name}] Error: {str(e)}")
            return self.format_error(f"MasterDB API unreachable at {self.masterdb_api_url}. Make sure it's running.")
        
        except requests.exceptions.Timeout as e:
            logger.error(f"[{self.name}] Request timeout after 30 seconds")
            return self.format_error("MasterDB API request timed out")
        
        except requests.exceptions.HTTPError as e:
            logger.error(f"[{self.name}] HTTP error from API: {str(e)}")
            return self.format_error(f"MasterDB API error: {response.text}")
        
        except Exception as e:
            logger.error(f"[{self.name}] Search failed: {str(e)}")
            return self.format_error(f"MasterDB search failed: {str(e)}")

    def _default_top_k(self, query: str) -> Optional[int]:
        """Use broader retrieval for statute/Act explanations."""
        query_lower = query.lower()
        statute_query = re.search(
            r"\b(?:act|acts|section|sections|provision|provisions|statute|legislation|"
            r"bare act|rule|rules|code|ipc|crpc|cpc|constitution|article)\b",
            query_lower
        )
        explanation_query = re.search(
            r"\b(?:explain|what\s+is|summary|summarize|overview|provisions|rights|remedies)\b",
            query_lower
        )

        if statute_query and explanation_query:
            return 15

        if statute_query:
            return 10

        return None


# =============================================================================
# TOOL REGISTRY
# =============================================================================

class ToolRegistry:
    """Registry and manager for all available tools"""
    
    def __init__(self):
        self.tools = {
            "law_dictionary": LawDictionaryTool(),
            "ecourts": eCourtsToolBase(),
            "masterdb": MasterDBTool()
        }
        self.tool_descriptions = {
            key: tool.description
            for key, tool in self.tools.items()
        }
    
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """Get a tool by name"""
        return self.tools.get(tool_name.lower())
    
    def get_available_tools(self) -> Dict[str, str]:
        """Get all available tools and their descriptions"""
        return self.tool_descriptions
    
    def execute_tool(self, tool_name: str, query: str, **kwargs) -> Dict[str, Any]:
        """Execute a specific tool"""
        tool = self.get_tool(tool_name)
        if not tool:
            return {
                "status": "error",
                "error": f"Tool '{tool_name}' not found"
            }
        return tool.search(query, **kwargs)


# =============================================================================
# GLOBAL TOOL REGISTRY INSTANCE
# =============================================================================

tool_registry = ToolRegistry()

