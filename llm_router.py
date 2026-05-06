"""
LLM 1: Router - Tool Selection Agent
Analyzes user queries and selects appropriate tools
Uses faster, cheaper LLM (GPT-4o-mini) for routing
"""

import json
import logging
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from openai import AzureOpenAI
import os

from prompts import (
    ROUTER_SYSTEM_PROMPT,
    format_router_prompt
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


# =============================================================================
# LLM 1: ROUTER
# =============================================================================

class LLMRouter:
    """
    Tool selection agent using LLM 1 (GPT-4o-mini for speed/cost)
    Routes queries to appropriate legal data sources
    """
    
    def __init__(self):
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        
        # Use cheaper model for routing
        self.router_model = os.getenv(
            "AZURE_OPENAI_DEPLOYMENT_ROUTER",
            os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.1-chat")
        )
        self.max_retries = 3
    
    def analyze_query(self, user_query: str, language: str = "en") -> Dict[str, Any]:
        """
        Analyze user query and determine which tools to use
        
        Args:
            user_query: The user's question
            language: Language code (en, hi, etc.)
        
        Returns:
            Dictionary with tool routing decision
        """
        try:
            logger.info(f"[ROUTER] Analyzing query: {user_query[:100]}...")
            
            # Build the prompt
            user_prompt = format_router_prompt(user_query, language)
            
            # Call LLM 1
            response = self.client.chat.completions.create(
                model=self.router_model,
                messages=[
                    {
                        "role": "system",
                        "content": ROUTER_SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                # max_completion_tokens=500
                max_tokens=500
            )
            
            # Extract response
            response_text = response.choices[0].message.content.strip()
            logger.debug(f"[ROUTER] Raw response: {response_text}")
            
            # Parse JSON response
            routing_decision = self._parse_router_response(response_text)
            
            logger.info(f"[ROUTER] Decision: Tools={routing_decision.get('tools')}, "
                       f"Type={routing_decision.get('query_type')}, "
                       f"Confidence={routing_decision.get('confidence')}")
            
            return routing_decision
        
        except Exception as e:
            logger.error(f"[ROUTER] Analysis failed: {str(e)}")
            return self._get_error_decision(str(e))
    
    def _parse_router_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse LLM response into structured decision
        Handles both JSON and fallback formats
        """
        try:
            # Try to extract JSON from response
            json_str = response_text.strip()
            
            # If response contains markdown code blocks, extract JSON
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            
            decision = json.loads(json_str)
            
            # Validate required fields
            if "tools" not in decision:
                decision["tools"] = ["law_dictionary"]
            if "confidence" not in decision:
                decision["confidence"] = 0.5
            
            return decision
        
        except json.JSONDecodeError as e:
            logger.warning(f"[ROUTER] Failed to parse JSON: {str(e)}")
            return self._get_fallback_decision(response_text)
    
    def _get_fallback_decision(self, response_text: str) -> Dict[str, Any]:
        """Fallback decision if JSON parsing fails"""
        # Simple heuristic-based routing as fallback
        response_lower = response_text.lower()
        
        tools = []
        query_type = "UNCLEAR"
        
        if any(word in response_lower for word in ["cnr", "case number", "live", "current"]):
            tools.append("ecourts")
            query_type = "LIVE_CASE"
        
        if any(word in response_lower for word in ["define", "term", "meaning", "what is"]):
            tools.append("law_dictionary")
            query_type = "LEGAL_TERM"
        
        if any(word in response_lower for word in ["precedent", "landmark", "historical", "history"]):
            tools.append("masterdb")
            query_type = "HISTORICAL_CASE"
        
        # Default to dictionary if no tools selected
        if not tools:
            tools = ["law_dictionary"]
        
        return {
            "tools": tools,
            "query_type": query_type,
            "confidence": 0.6,
            "reasoning": "Fallback heuristic routing (JSON parsing failed)",
            "clarification_needed": False,
            "warning": "LLM response was not properly formatted"
        }
    
    def _get_error_decision(self, error: str) -> Dict[str, Any]:
        """Default decision on error"""
        logger.warning(f"[ROUTER] Using default routing due to error: {error}")
        return {
            "tools": ["law_dictionary"],
            "query_type": "UNCLEAR",
            "confidence": 0.3,
            "reasoning": "Error in LLM routing, defaulting to law_dictionary",
            "clarification_needed": False,
            "error": error
        }
    
    def validate_routing_decision(self, decision: Dict[str, Any]) -> bool:
        """Validate routing decision has required fields"""
        required_fields = ["tools", "query_type", "confidence"]
        return all(field in decision for field in required_fields)
    
    def should_clarify_query(self, decision: Dict[str, Any]) -> bool:
        """Check if user clarification is needed"""
        return decision.get("clarification_needed", False) and \
               decision.get("confidence", 0) < 0.7
    
    def get_clarification_message(self, decision: Dict[str, Any]) -> str:
        """Get clarification message if needed"""
        return decision.get("clarification_message", 
                          "Please clarify your query for better results.")


# =============================================================================
# QUERY CLASSIFICATION
# =============================================================================

class QueryClassifier:
    """Helper class for query classification and preprocessing"""
    
    QUERY_PATTERNS = {
        "live_case": [
            r"\b[A-Z]{4}\d{12}\b",
            r"case\s+number",
            r"live\s+case",
            r"current\s+status",
            r"next\s+hearing",
            r"pending\s+case"
        ],
        "legal_term": [
            r"what\s+is",
            r"define",
            r"meaning\s+of",
            r"explain",
            r"term\s+",
            r"concept\s+of"
        ],
        "historical": [
            r"precedent",
            r"landmark",
            r"historical",
            r"past\s+case",
            r"case\s+law",
            r"earlier\s+ruling"
        ]
    }
    
    @staticmethod
    def extract_cnr(query: str) -> Optional[str]:
        """Extract CNR number from query if present"""
        import re
        match = re.search(r"cnr\s+(\d+/\d+)", query, re.IGNORECASE)
        return match.group(1) if match else None
    
    @staticmethod
    def classify_query_type(query: str) -> str:
        """Classify query into types using regex patterns"""
        import re
        query_lower = query.lower()
        
        for query_type, patterns in QueryClassifier.QUERY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return query_type
        
        return "unknown"
    
    @staticmethod
    def detect_language(query: str) -> str:
        """Simple language detection (basic implementation)"""
        # This is a placeholder - integrate proper language detection
        # For now, assume English or other languages
        try:
            query.encode('ascii')
            return "en"
        except UnicodeEncodeError:
            # Contains non-ASCII characters
            return "multi"


# =============================================================================
# GLOBAL ROUTER INSTANCE
# =============================================================================

router = LLMRouter()


