"""
Main Orchestrator Agent
Coordinates tool selection, execution, and response generation
This is the main pipeline that brings together:
- LLM 1 (Router) for tool selection
- Tool Execution
- LLM 2 (Generator) for response synthesis
"""

import logging
import json
import re
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

from tools import tool_registry
from llm_router import router, QueryClassifier
from llm_generator import generator, formatter, consistency_checker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s - %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()


# =============================================================================
# ORCHESTRATOR AGENT
# =============================================================================

class LegalOrchestratorAgent:
    """
    Main orchestrator for legal query processing
    Coordinates multi-tool, dual-LLM pipeline
    """
    
    def __init__(self):
        self.router = router
        self.generator = generator
        self.tool_registry = tool_registry
        self.formatter = formatter
        self.consistency_checker = consistency_checker
        self.max_tools = 3
    
    def process_query(
        self,
        user_query: str,
        language: str = "en",
        return_format: str = "markdown"
    ) -> Dict[str, Any]:
        """
        Process user query through complete pipeline
        
        Args:
            user_query: User's question
            language: Query language code (en, hi, ta, etc.)
            return_format: Response format (markdown, json, html)
        
        Returns:
            Complete response with metadata
        """
        
        logger.info(f"\n{'='*80}")
        logger.info(f"[ORCHESTRATOR] Processing Query: {user_query[:100]}...")
        logger.info(f"Language: {language} | Format: {return_format}")
        logger.info(f"{'='*80}\n")
        
        try:
            # ====================================================================
            # STEP 1: CLASSIFY QUERY
            # ====================================================================
            logger.info("[STEP 1] Query Classification & Preprocessing")
            
            # Extract CNR if present
            cnr_number = QueryClassifier.extract_cnr(user_query)
            query_type = QueryClassifier.classify_query_type(user_query)
            
            logger.info(f"  - Query type: {query_type}")
            if cnr_number:
                logger.info(f"  - CNR detected: {cnr_number}")
            
            # ====================================================================
            # STEP 2: LLM 1 - ROUTE QUERY TO TOOLS
            # ====================================================================
            logger.info("\n[STEP 2] Tool Selection (LLM 1 - Router)")
            
            routing_decision = self.router.analyze_query(user_query, language)
            
            # Check if clarification needed
            if routing_decision.get("clarification_needed"):
                logger.warning(f"[ORCHESTRATOR] Clarification needed!")
                return {
                    "status": "clarification_needed",
                    "message": routing_decision.get("clarification_message"),
                    "query": user_query
                }
            
            selected_tools = routing_decision.get("tools", ["law_dictionary"])
            selected_tools = self._apply_tool_routing_overrides(selected_tools, user_query)
            confidence = routing_decision.get("confidence", 0.5)
            
            logger.info(f"  - Selected tools: {selected_tools}")
            logger.info(f"  - Confidence: {confidence:.2%}")
            logger.info(f"  - Query type detected: {routing_decision.get('query_type')}")
            
            # ====================================================================
            # STEP 3: EXECUTE SELECTED TOOLS
            # ====================================================================
            logger.info("\n[STEP 3] Tool Execution")
            
            tool_results = self._execute_tools(selected_tools, user_query, cnr_number)
            
            for result in tool_results:
                tool_name = result.get("tool", "Unknown")
                status = result.get("status", "unknown")
                logger.info(f"  - {tool_name}: {status}")
            
            # ====================================================================
            # STEP 4: DATA CONSISTENCY CHECK
            # ====================================================================
            logger.info("\n[STEP 4] Data Consistency Check")
            
            consistency_result = self.consistency_checker.check_consistency(tool_results)
            
            if consistency_result.get("warning_needed"):
                logger.warning(f"⚠️  Contradictions detected!")
                logger.warning(f"  Contradictions: {consistency_result.get('contradictions')}")
            else:
                logger.info("  ✓ Data is consistent")
            
            # ====================================================================
            # STEP 5: LLM 2 - GENERATE RESPONSE
            # ====================================================================
            logger.info("\n[STEP 5] Response Generation (LLM 2 - Generator)")
            
            response_result = self.generator.generate_response(
                user_query=user_query,
                tool_results=tool_results,
                tools_used=selected_tools,
                language=language
            )
            
            logger.info(f"  - Status: {response_result.get('status')}")
            logger.info(f"  - Response length: {len(response_result.get('response', ''))} chars")
            
            # ====================================================================
            # STEP 6: FORMAT RESPONSE
            # ====================================================================
            logger.info("\n[STEP 6] Response Formatting")
            
            formatted_response = self._format_final_response(
                response_result,
                return_format,
                tool_results
            )
            
            logger.info(f"  - Format: {return_format}")
            logger.info(f"{'='*80}\n")
            
            return formatted_response
        
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Pipeline failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "query": user_query
            }

    def _apply_tool_routing_overrides(
        self,
        tool_names: List[str],
        query: str
    ) -> List[str]:
        """
        Apply deterministic routing corrections for strong statutory signals.
        This catches common queries like "what is domestic violence act?" even
        when the LLM router treats them as dictionary-only definition requests.
        """
        normalized_tools = []
        for tool_name in tool_names:
            tool_key = tool_name.lower()
            if tool_key not in normalized_tools:
                normalized_tools.append(tool_key)

        query_lower = query.lower()
        statutory_patterns = [
            r"\b(?:section|sections|provision|provisions|statute|legislation|bare act)\b",
            r"\b(?:rule|rules|code|codes|ipc|crpc|cpc|constitution|article)\b",
            r"\b[a-z][a-z\s]{2,}\s+act\b",
            r"\bact\s+(?:of\s+)?\d{4}\b",
        ]
        dictionary_act_phrases = [
            r"\bwrongful act\b",
            r"\bact of\b",
            r"\ban act that\b",
            r"\bmeaning of act\b",
        ]

        has_statutory_signal = any(
            re.search(pattern, query_lower)
            for pattern in statutory_patterns
        )
        dictionary_only_act = any(
            re.search(pattern, query_lower)
            for pattern in dictionary_act_phrases
        )

        if has_statutory_signal and not dictionary_only_act:
            explicitly_needs_dictionary = re.search(
                r"\b(?:dictionary|meaning\s+of\s+the\s+term|define\s+the\s+term|"
                r"word\s+meaning|terminology)\b",
                query_lower
            )

            if explicitly_needs_dictionary:
                statutory_tools = ["masterdb"]
                statutory_tools.append("law_dictionary")
                statutory_tools.extend(
                    tool_name
                    for tool_name in normalized_tools
                    if tool_name not in {"masterdb", "law_dictionary"}
                )
                return statutory_tools

            statutory_tools = []
            for tool_name in ["masterdb", *normalized_tools]:
                if tool_name != "law_dictionary" and tool_name not in statutory_tools:
                    statutory_tools.append(tool_name)

            return statutory_tools[:self.max_tools]

        return normalized_tools
    
    def _execute_tools(
        self,
        tool_names: List[str],
        query: str,
        cnr_number: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute selected tools and collect results
        
        Args:
            tool_names: List of tools to execute
            query: The user query
            cnr_number: Optional CNR number for eCourts
        
        Returns:
            List of tool results
        """
        results = []
        
        # Limit number of tools
        tool_names = tool_names[:self.max_tools]
        
        for tool_name in tool_names:
            logger.info(f"  - Executing: {tool_name}")
            
            try:
                # Execute tool with specific parameters
                if tool_name.lower() == "ecourts" and cnr_number:
                    result = self.tool_registry.execute_tool(
                        tool_name,
                        query,
                        cnr_number=cnr_number
                    )
                else:
                    result = self.tool_registry.execute_tool(tool_name, query)
                
                results.append(result)
            
            except Exception as e:
                logger.error(f"  - {tool_name} failed: {str(e)}")
                results.append({
                    "tool": tool_name,
                    "status": "error",
                    "error": str(e)
                })
        
        return results
    
    def _format_final_response(
        self,
        response_result: Dict[str, Any],
        format_type: str,
        tool_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Format final response for output
        
        Args:
            response_result: Generator output
            format_type: Output format (markdown, json, html)
            tool_results: Original tool results
        
        Returns:
            Formatted response
        """
        response_text = response_result.get("response", "")
        tools_used = response_result.get("tools_used", [])
        
        # Format based on type
        if format_type == "json":
            formatted = formatter.format_json(
                query=response_result.get("user_query", ""),
                response=response_text,
                tools_used=tools_used,
                status=response_result.get("status", "success")
            )
        elif format_type == "html":
            formatted = formatter.format_html(response_text)
        else:  # markdown
            formatted = formatter.format_markdown(response_text)
        
        return {
            "status": response_result.get("status", "success"),
            "query": response_result.get("user_query", ""),
            "response": formatted,
            "tools_used": tools_used,
            "format": format_type,
            "sources_count": response_result.get("sources_count", 0)
        }
    
    def get_available_tools(self) -> Dict[str, str]:
        """Get list of available tools"""
        return self.tool_registry.get_available_tools()


# =============================================================================
# GLOBAL ORCHESTRATOR INSTANCE
# =============================================================================

orchestrator = LegalOrchestratorAgent()


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Test queries
    test_queries = [
        {
            "query": "What is negligence in Indian law?",
            "language": "en",
            "description": "Legal term definition"
        },
        {
            "query": "Show me case CNR 2024/12345",
            "language": "en",
            "description": "Live case lookup"
        },
        {
            "query": "Tell me about landmark negligence cases",
            "language": "en",
            "description": "Historical cases"
        },
        {
            "query": "Recent updates on CNR 2024/12345 similar to 2015 negligence precedent",
            "language": "en",
            "description": "Mixed query"
        }
    ]
    
    print("\n" + "="*80)
    print("LEGAL ORCHESTRATOR AGENT - TEST SUITE")
    print("="*80)
    
    for i, test in enumerate(test_queries, 1):
        print(f"\n\n### Test {i}: {test['description']}")
        print(f"Query: {test['query']}\n")
        
        result = orchestrator.process_query(
            user_query=test['query'],
            language=test['language'],
            return_format="markdown"
        )
        
        print("\nFinal Result:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("\n" + "="*80)
