"""
FastAPI Integration with Orchestrator Agent
Exposes the legal orchestrator through REST API endpoints
"""

from fastapi import FastAPI, Query, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import logging
import json
from datetime import datetime

from orchestrator import orchestrator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# FASTAPI APP SETUP
# =============================================================================

app = FastAPI(
    title="Legal Orchestrator API",
    description="Multilingual Legal Chatbot with Tool Orchestration",
    version="1.0.0"
)

# Add CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class QueryRequest(BaseModel):
    """Request model for legal query"""
    query: str
    language: Optional[str] = "en"
    return_format: Optional[str] = "markdown"
    
    class Config:
        example = {
            "query": "What is negligence?",
            "language": "en",
            "return_format": "markdown"
        }


class QueryResponse(BaseModel):
    """Response model for legal query"""
    status: str
    query: str
    response: str
    tools_used: List[str]
    format: str
    sources_count: int
    timestamp: str
    
    class Config:
        example = {
            "status": "success",
            "query": "What is negligence?",
            "response": "Negligence is...",
            "tools_used": ["law_dictionary"],
            "format": "markdown",
            "sources_count": 1,
            "timestamp": "2026-04-30T10:30:00Z"
        }


class ToolInfo(BaseModel):
    """Tool information model"""
    name: str
    description: str


# =============================================================================
# HEALTH CHECK ENDPOINT
# =============================================================================

@app.get("/", tags=["Health"])
def home():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "Legal Orchestrator API",
        "version": "1.0.0",
        "message": "API is operational 🚀"
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "service": "Legal Orchestrator API",
        "timestamp": datetime.now().isoformat(),
        "available_tools": len(orchestrator.get_available_tools())
    }


# =============================================================================
# QUERY ENDPOINT
# =============================================================================

@app.post("/query", response_model=QueryResponse, tags=["Legal Queries"])
def process_legal_query(request: QueryRequest):
    """
    Process a legal query through the orchestrator pipeline
    
    - **query**: The legal question (required)
    - **language**: Query language code - en, hi, ta, te, kn, ml (default: en)
    - **return_format**: Response format - markdown, json, html (default: markdown)
    
    Returns:
        - Complete response with sources and metadata
    """
    try:
        logger.info(f"[API] Received query: {request.query[:100]}...")
        
        # Validate input
        if not request.query or len(request.query.strip()) < 3:
            raise HTTPException(
                status_code=400,
                detail="Query must be at least 3 characters long"
            )
        
        # Process through orchestrator
        result = orchestrator.process_query(
            user_query=request.query,
            language=request.language,
            return_format=request.return_format
        )
        
        # Check for errors
        if result.get("status") == "error":
            logger.error(f"[API] Query processing failed: {result.get('error')}")
            raise HTTPException(
                status_code=500,
                detail=f"Query processing failed: {result.get('error')}"
            )
        
        # Add timestamp
        result["timestamp"] = datetime.now().isoformat()
        
        logger.info(f"[API] Query processed successfully")
        return QueryResponse(**result)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/query", tags=["Legal Queries"])
def query_get(
    q: str = Query(..., description="Legal query"),
    language: str = Query("en", description="Language code"),
    format: str = Query("markdown", description="Response format")
):
    """
    Alternative GET endpoint for legal queries
    
    Query parameters:
    - q: Legal question
    - language: Language code (default: en)
    - format: Response format (default: markdown)
    """
    request = QueryRequest(query=q, language=language, return_format=format)
    return process_legal_query(request)


# =============================================================================
# TOOLS ENDPOINT
# =============================================================================

@app.get("/tools", response_model=List[ToolInfo], tags=["Tools"])
def get_available_tools():
    """
    Get list of available tools in the orchestrator
    
    Returns:
        - List of tools with descriptions
    """
    try:
        tools_dict = orchestrator.get_available_tools()
        tools = [
            ToolInfo(name=name, description=description)
            for name, description in tools_dict.items()
        ]
        return tools
    except Exception as e:
        logger.error(f"[API] Failed to retrieve tools: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve available tools"
        )


# =============================================================================
# BATCH QUERY ENDPOINT
# =============================================================================

@app.post("/batch-query", tags=["Legal Queries"])
def batch_process_queries(queries: List[QueryRequest]):
    """
    Process multiple queries in batch
    
    - **queries**: List of query requests
    
    Returns:
        - List of responses for each query
    """
    try:
        if len(queries) > 10:
            raise HTTPException(
                status_code=400,
                detail="Maximum 10 queries per batch"
            )
        
        results = []
        for request in queries:
            result = orchestrator.process_query(
                user_query=request.query,
                language=request.language,
                return_format=request.return_format
            )
            result["timestamp"] = datetime.now().isoformat()
            results.append(result)
        
        logger.info(f"[API] Batch processed {len(queries)} queries")
        return {"status": "success", "count": len(results), "results": results}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] Batch processing failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Batch processing failed: {str(e)}"
        )


# =============================================================================
# STATISTICS/MONITORING ENDPOINT
# =============================================================================

@app.get("/stats", tags=["Monitoring"])
def get_statistics():
    """
    Get API usage statistics
    """
    return {
        "status": "ok",
        "available_tools": len(orchestrator.get_available_tools()),
        "tools": list(orchestrator.get_available_tools().keys()),
        "timestamp": datetime.now().isoformat()
    }


# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"[API] Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error": "Internal server error",
            "status_code": 500
        }
    )


# =============================================================================
# STARTUP/SHUTDOWN EVENTS
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    logger.info("="*80)
    logger.info("🚀 Legal Orchestrator API Starting Up")
    logger.info("="*80)
    logger.info(f"Available Tools: {list(orchestrator.get_available_tools().keys())}")
    logger.info("="*80)


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    logger.info("="*80)
    logger.info("🛑 Legal Orchestrator API Shutting Down")
    logger.info("="*80)


# =============================================================================
# DOCUMENTATION ENDPOINT
# =============================================================================

@app.get("/docs/usage", tags=["Documentation"])
def get_usage_documentation():
    """Get API usage documentation"""
    return {
        "api": "Legal Orchestrator API",
        "version": "1.0.0",
        "endpoints": {
            "POST /query": "Process a single legal query",
            "GET /query": "Process query via GET parameters",
            "POST /batch-query": "Process multiple queries in batch",
            "GET /tools": "List available tools",
            "GET /stats": "API statistics",
            "GET /health": "Health check"
        },
        "supported_languages": ["en", "hi", "ta", "te", "kn", "ml"],
        "return_formats": ["markdown", "json", "html"],
        "example_queries": [
            "What is negligence?",
            "Show me case CNR 2024/12345",
            "Tell me about landmark negligence cases",
            "Recent updates on CNR 2024/12345 similar to 2015 precedent"
        ]
    }


# =============================================================================
# RUN SERVER
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
