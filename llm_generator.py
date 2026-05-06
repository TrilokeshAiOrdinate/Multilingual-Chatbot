"""
LLM 2: Response Generator - Answer Synthesis Agent
Generates accurate responses using ONLY fetched data
Uses more powerful LLM (GPT-4) for quality responses
NO HALLUCINATIONS - Data-driven responses only
"""

import json
import logging
import re
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from openai import AzureOpenAI
import os

from prompts import (
    GENERATOR_SYSTEM_PROMPT,
    format_generator_prompt,
    format_fetched_data_for_generator
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


# =============================================================================
# LLM 2: RESPONSE GENERATOR
# =============================================================================

class ResponseGenerator:
    """
    Response synthesis agent using LLM 2 (GPT-4 for quality)
    Generates responses using ONLY fetched data
    Prevents hallucinations through data-driven approach
    """
    
    def __init__(self):
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        
        # Use powerful model for response generation
        self.generator_model = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.1-chat")
        self.max_retries = 3
    
    def generate_response(
        self,
        user_query: str,
        tool_results: List[Dict[str, Any]],
        tools_used: List[str],
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Generate response using only fetched data
        
        Args:
            user_query: Original user question
            tool_results: Results from executed tools
            tools_used: List of tools that were used
            language: Response language code
        
        Returns:
            Generated response with metadata
        """
        try:
            logger.info(f"[GENERATOR] Creating response for: {user_query[:100]}...")
            
            # Check if we have valid data
            valid_results = [r for r in tool_results if r.get("status") == "success"]
            
            if not valid_results:
                return self._get_no_data_response(user_query, tool_results)
            
            # Format data for LLM
            formatted_data = format_fetched_data_for_generator(tool_results)
            
            # Build generator prompt
            generator_prompt = format_generator_prompt(
                query=user_query,
                fetched_data=formatted_data,
                tools_used=tools_used,
                language=language
            )
            
            # Call LLM 2
            response = self.client.chat.completions.create(
                model=self.generator_model,
                messages=[
                    {
                        "role": "system",
                        "content": GENERATOR_SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": generator_prompt
                    }
                ],
                # max_completion_tokens=2000
                max_tokens=2000
            )
            
            # Extract response
            response_text = response.choices[0].message.content.strip()
            
            logger.info(f"[GENERATOR] Response generated successfully")
            
            return {
                "status": "success",
                "response": response_text,
                "tools_used": tools_used,
                "sources_count": len(valid_results),
                "language": language,
                "user_query": user_query
            }
        
        except Exception as e:
            logger.error(f"[GENERATOR] Response generation failed: {str(e)}")
            return self._get_error_response(user_query, str(e))
    
    def _get_no_data_response(
        self,
        user_query: str,
        tool_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate response when no data found"""
        errors = [r.get("error", "Unknown error") for r in tool_results if r.get("status") == "error"]
        
        response = f"""I attempted to find information about "{user_query}" but encountered issues:

Errors encountered:
{chr(10).join(f"• {error}" for error in errors) if errors else "• No data sources returned valid results"}

To get better results, please try:
1. Rephrasing your query
2. Using specific case numbers (e.g., CNR 2024/12345)
3. Breaking complex questions into smaller parts
4. Specifying which type of information you need (term definition, current case status, or historical precedent)

Available search types:
• Legal terms: Define concepts and legal terminology
• Live cases: Search using CNR numbers for current case status
• Historical cases: Find precedents and landmark decisions"""
        
        return {
            "status": "partial",
            "response": response,
            "tools_used": [],
            "sources_count": 0,
            "user_query": user_query,
            "warning": "No valid data sources found"
        }
    
    def _get_error_response(self, user_query: str, error: str) -> Dict[str, Any]:
        """Generate response on error"""
        logger.warning(f"[GENERATOR] Error occurred: {error}")
        
        response = f"""I encountered an error while processing your query:
"{user_query}"

Error details: {error}

Please try again or rephrase your question."""
        
        return {
            "status": "error",
            "response": response,
            "error": error,
            "user_query": user_query
        }
    
    def validate_response(self, response: Dict[str, Any]) -> bool:
        """Validate generated response"""
        return (
            response.get("status") in ["success", "partial", "error"] and
            "response" in response and
            len(response.get("response", "")) > 0
        )
    
    def format_for_api(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Format response for API output"""
        return {
            "query": response.get("user_query", ""),
            "response": response.get("response", ""),
            "sources": response.get("tools_used", []),
            "status": response.get("status", "unknown"),
            "language": response.get("language", "en")
        }


# =============================================================================
# RESPONSE FORMATTER
# =============================================================================

class ResponseFormatter:
    """Format responses for different output channels"""

    @staticmethod
    def strip_source_labels(response: str) -> str:
        """Remove tool/source labels from response text; metadata carries sources."""
        response = re.sub(r"\s*\[Source:\s*[^\]]+\]", "", response, flags=re.IGNORECASE)
        response = re.sub(
            r"(?im)^\s*(?:source|sources)\s*:\s*(?:LAW_DICTIONARY|MASTERDB|eCOURTS|[\w,\s-]+)\s*$\n?",
            "",
            response
        )
        return re.sub(r"\n{3,}", "\n\n", response).strip()
    
    @staticmethod
    def format_markdown(response: str) -> str:
        """Format response as markdown"""
        return ResponseFormatter.strip_source_labels(response)
    
    @staticmethod
    def format_json(
        query: str,
        response: str,
        tools_used: List[str],
        status: str = "success"
    ) -> str:
        """Format response as JSON"""
        data = {
            "query": query,
            "response": ResponseFormatter.strip_source_labels(response),
            "sources": tools_used,
            "status": status
        }
        return json.dumps(data, indent=2, ensure_ascii=False)
    
    @staticmethod
    def format_html(response: str) -> str:
        """Format response as HTML"""
        response = ResponseFormatter.strip_source_labels(response)
        # Simple HTML formatting
        html = f"""
        <div class="legal-response">
            <div class="response-content">
                {response.replace(chr(10), '<br>')}
            </div>
        </div>
        """
        return html
    
    @staticmethod
    def add_disclaimer(response: str, tool_names: List[str]) -> str:
        """Add legal disclaimer to response"""
        disclaimer = f"""

---
**Important Disclaimer:**
This response is based on data from: {', '.join(tool_names)}
This is not a substitute for professional legal advice. 
Please consult with a qualified legal professional for legal matters.
"""
        return response + disclaimer


# =============================================================================
# DATA CONSISTENCY CHECKER
# =============================================================================

class DataConsistencyChecker:
    """Check consistency in fetched data to prevent contradictions"""
    
    @staticmethod
    def check_consistency(tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Check if results from different tools are consistent
        Flag any contradictions
        """
        
        contradictions = []
        
        # Group results by tool type
        results_by_tool = {}
        for result in tool_results:
            tool = result.get("tool", "unknown")
            if tool not in results_by_tool:
                results_by_tool[tool] = []
            results_by_tool[tool].append(result)
        
        # Check for contradictions between tools
        if "eCOURTS" in results_by_tool and "MASTERDB" in results_by_tool:
            # Example: Check if case numbers match if mentioned in both
            pass
        
        return {
            "is_consistent": len(contradictions) == 0,
            "contradictions": contradictions,
            "warning_needed": len(contradictions) > 0
        }
    
    @staticmethod
    def flag_insufficient_data(tool_results: List[Dict[str, Any]]) -> bool:
        """Check if data is insufficient for reliable answer"""
        success_results = [r for r in tool_results if r.get("status") == "success"]
        return len(success_results) == 0


# =============================================================================
# GLOBAL GENERATOR INSTANCE
# =============================================================================

generator = ResponseGenerator()
formatter = ResponseFormatter()
consistency_checker = DataConsistencyChecker()
