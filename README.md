# Multilingual Legal Chatbot Pipeline - LexAIO

## 📋 Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Pipeline Flow](#pipeline-flow)
4. [Components](#components)
5. [Tools & Data Sources](#tools--data-sources)
6. [API Endpoints](#api-endpoints)
7. [Configuration](#configuration)
8. [Examples](#examples)
9. [Supported Languages](#supported-languages)

---

## Overview

LexAIO is a sophisticated multilingual legal chatbot system designed for the Indian legal system. It provides intelligent retrieval and synthesis of legal information through a dual-LLM orchestrated pipeline that ensures:

- **Accuracy**: Data-driven responses without hallucinations
- **Speed**: Lightweight router for quick tool selection
- **Multilingual Support**: Handles queries in multiple Indian languages
- **Multi-Source Integration**: Combines Law Dictionary, eCourts, and Legal Document Search
- **Case Tracking**: Real-time case status via eCourts integration (using CNR numbers)

---

## Architecture

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     FastAPI REST API Layer                          │
│                    (app.py / masterdb_aisearch)                     │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Orchestrator Agent                               │
│         (orchestrator.py - Central Processing Hub)                 │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ Query Classifier │  │  LLM 1: Router   │  │ Tool Executor    │  │
│  │ (CNR Extraction) │  │  (GPT-4o-mini)   │  │                  │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │        LLM 2: Response Generator (GPT-4)                    │  │
│  │        (Synthesizes response from tool data only)           │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────┬──────────────────────────────────────────────────────┘
             │
             ├─────────────────┬─────────────────┬──────────────────┐
             ▼                 ▼                 ▼                  ▼
        ┌─────────┐      ┌──────────┐     ┌──────────────┐   ┌──────────┐
        │ LAW     │      │ eCourts  │     │ MasterDB     │   │ Tools    │
        │DICTIONARY       │ Client   │     │ AI Search    │   │Registry  │
        │ Tool    │      │ (CNR)    │     │ (Legal Docs) │   │          │
        └─────────┘      └──────────┘     └──────────────┘   └──────────┘
             │                 │                  │                │
             ▼                 ▼                  ▼                ▼
        ┌─────────────────────────────────────────────────────────────┐
        │          Local Data Sources & External APIs                │
        │                                                            │
        │  • Local JSON Law Dictionary        • eCourts Portal API  │
        │  • Vector Embeddings (cached)       • Azure Search Index   │
        │  • Hybrid Search Index              • Legal Documents DB  │
        └─────────────────────────────────────────────────────────────┘
```

---

## Pipeline Flow

### Complete Query Processing Pipeline

```
User Input (Legal Question)
         │
         ▼
    ┌─────────────────────────────┐
    │  STEP 1: Query Analysis     │
    │  - Detect Language          │
    │  - Extract CNR (if present) │
    │  - Classify Query Type      │
    └────────────┬────────────────┘
                 │
                 ▼
    ┌─────────────────────────────┐
    │  STEP 2: Tool Selection     │
    │  LLM 1 (GPT-4o-mini)        │
    │  - Analyze query            │
    │  - Decide which tools       │
    │  - Check if clarification   │
    │    is needed                │
    └────────────┬────────────────┘
                 │
                 ▼
    ┌─────────────────────────────────────────┐
    │  STEP 3: Execute Tools (Parallel)       │
    │  - Law Dictionary Search                │
    │  - eCourts API Lookup                   │
    │  - MasterDB Search                      │
    └────────────┬────────────────────────────┘
                 │
                 ▼
    ┌─────────────────────────────┐
    │  STEP 4: Response Synthesis │
    │  LLM 2 (GPT-4)              │
    │  - Format data              │
    │  - Generate response        │
    │  - Add citations            │
    │  - Apply consistency checks │
    └────────────┬────────────────┘
                 │
                 ▼
    ┌─────────────────────────────┐
    │  STEP 5: Format Output      │
    │  - Markdown/JSON/HTML       │
    │  - Add metadata             │
    │  - Include sources          │
    └────────────┬────────────────┘
                 │
                 ▼
         User Receives Response
```

---

## Components

### 1. **Orchestrator Agent** (`orchestrator.py`)
Central controller that coordinates the entire pipeline.

**Responsibilities:**
- Query classification and preprocessing
- Tool selection via LLM Router
- Tool execution coordination (up to 3 tools max)
- Response generation via LLM Generator
- Output formatting and consistency checking

**Key Methods:**
```python
process_query(user_query, language="en", return_format="markdown")
  └─ Returns: {"status", "response", "tools_used", "sources", "timestamp"}
```

---

### 2. **LLM 1: Router** (`llm_router.py`)
Fast, cost-efficient tool selector using GPT-4o-mini.

**Responsibilities:**
- Analyze user queries
- Determine which tools are needed (Law Dictionary, eCourts, MasterDB, etc.)
- Detect clarification needs
- Route queries to appropriate data sources

**Tool Selection Logic:**
- **LAW_DICTIONARY**: Legal definitions, terminology
- **ECOURTS**: Case status, CNR lookups, hearing dates
- **MASTERDB**: Acts, legislation, legal documents
- **COMBINED**: Multiple sources for comprehensive answers

**Key Methods:**
```python
analyze_query(user_query, language="en")
  └─ Returns: {"tools": [...], "reasoning", "clarification_needed"}
```

---

### 3. **LLM 2: Response Generator** (`llm_generator.py`)
Powerful synthesizer using GPT-4 for high-quality responses.

**Responsibilities:**
- Generate accurate responses from tool data
- Format responses in requested format (markdown, JSON, HTML)
- Add citations and sources
- Perform consistency checks
- Prevent hallucinations (data-driven only)

**Key Methods:**
```python
generate_response(user_query, tool_results, tools_used, language="en")
  └─ Returns: {"response", "sources_cited", "confidence"}
```

---

### 4. **Query Classifier** (`llm_router.py`)
Preprocesses queries before routing.

**Features:**
- Extract CNR (Case Number) from queries
- Classify query type (case_lookup, legal_definition, document_search, etc.)
- Detect language automatically
- Extract entities for targeted searches

---

## Tools & Data Sources

### 1. **Law Dictionary Tool** (`hybrid_search.py`)
Local legal dictionary with intelligent search.

**Data Source:** `legal_dictionary_with_embeddings.json`

**Search Mechanism:**
- **Vector Search**: Semantic similarity using SentenceTransformers
- **Keyword Search**: BM25 text matching via Azure Cognitive Search
- **Cross-Encoder Reranking**: MS-MARCO model for relevance scoring
- **Term Boosting**: Exact match and partial match scoring

**Response Format:**
```json
{
  "term": "Negligence",
  "part_of_speech": "noun",
  "definition": "...",
  "confidence_score": 0.95,
  "source": "LAW_DICTIONARY"
}
```

**Top K Results:** Default 5, configurable

---

### 2. **eCourts Tool** (`ecourts_endpoint/`)
Integration with Indian eCourts system for live case data.

**Features:**
- Fetch case details by CNR (Case Number Reference)
- Get case status and hearing history
- Download court orders
- Real-time sync with eCourts portal

**Supported Operations:**
```
POST   /ecourt/fetch-by-cnr          → Fetch case by CNR number
GET    /ecourt/cases/{id}/ecourt-data → Full case details
GET    /ecourt/cases/{id}/orders      → List of orders
GET    /ecourt/cases/{id}/history     → Hearing history
POST   /ecourt/cases/{id}/sync        → Sync case from portal
POST   /ecourt/download-order         → Download specific order
```

**Response Format:**
```json
{
  "case_number": "CNR...",
  "status": "Active",
  "next_hearing": "2026-06-15",
  "orders": [],
  "source": "eCOURTS"
}
```

---

### 3. **MasterDB Search Tool** (`masterdb_aisearch/`)
Azure Cognitive Search integration for legal documents (Acts, Legislation).

**Features:**
- Hybrid search (vector + semantic)
- Full-text search over Indian legal documents
- Embeddings-based similarity
- State and central acts indexed

**Endpoint:** Separate FastAPI instance on port 8001

**Search Mechanism:**
```
1. Generate embedding for query
2. Vector search (k=30) in Azure Search Index
3. Cross-encoder reranking
4. Return top_k results with scores
```

**Response Format:**
```json
{
  "document": "The Indian Penal Code, Section 304",
  "relevant_excerpt": "...",
  "relevance_score": 0.92,
  "source": "MASTERDB"
}
```

---

## API Endpoints

### Main API (`app.py` - Port 8000)

#### 1. **Health Check**
```
GET /
Response: {"status": "running", "service": "Legal Orchestrator API", "version": "1.0.0"}
```

#### 2. **Process Legal Query** (Main Endpoint)
```
POST /query
Content-Type: application/json

Request Body:
{
  "query": "What is negligence under Indian law?",
  "language": "en",
  "return_format": "markdown"
}

Response:
{
  "status": "success",
  "query": "What is negligence under Indian law?",
  "response": "Negligence is a legal concept...",
  "tools_used": ["LAW_DICTIONARY"],
  "format": "markdown",
  "sources_count": 1,
  "timestamp": "2026-05-04T10:30:00Z"
}
```

#### 3. **Available Tools**
```
GET /tools
Response: [{"name": "LAW_DICTIONARY", "description": "..."}, ...]
```

---

### Secondary API (`masterdb_aisearch/api.py` - Port 8001)

#### **Legal Document Search**
```
GET /search?query=section%20304&top_k=5

Response:
{
  "query": "section 304",
  "num_results": 5,
  "search_time_sec": 0.234,
  "results": [
    {
      "document": "...",
      "relevance_score": 0.92,
      "source": "MASTERDB"
    }
  ]
}
```

---

## Configuration

### Environment Variables (`.env`)

```bash
# Azure OpenAI Configuration
AZURE_OPENAI_KEY=your_api_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_DEPLOYMENT=gpt-5.1-chat          # LLM 2 (Generator)
AZURE_OPENAI_DEPLOYMENT_ROUTER=gpt-4o-mini   # LLM 1 (Router)

# Azure Cognitive Search (for MasterDB)
SEARCH_ENDPOINT=https://your-search.search.windows.net
SEARCH_KEY=your_search_key
INDEX_NAME=legal-documents

# eCourts Integration
ECOURT_BASE_URL=https://legtech-backend.azurewebsites.net
ECOURT_USERNAME=your_username
ECOURT_PASSWORD=your_password

# Server Configuration
HOST=127.0.0.1
PORT=8000
RELOAD=true
```

### Models Used

| Component | Model | Purpose | Speed | Cost |
|-----------|-------|---------|-------|------|
| **Router (LLM 1)** | GPT-4o-mini | Tool selection | ⚡ Fast | 💰 Low |
| **Generator (LLM 2)** | GPT-4 | Response synthesis | ⏱️ Medium | 💸 High |
| **Embeddings** | SentenceTransformers (all-MiniLM-L6-v2) | Vector search | ⚡ Fast | 🆓 Free |
| **Reranking** | Cross-Encoder (ms-marco) | Result ranking | ⏱️ Medium | 🆓 Free |

---

## Supported Languages

The system supports queries in multiple Indian and international languages:

| Language | Code | Support | Tool Access |
|----------|------|---------|-------------|
| **English** | `en` | ✅ Full | All tools |
| **Hindi** | `hi` | ✅ Full | All tools |
| **Tamil** | `ta` | ✅ Full | All tools |
| **Telugu** | `te` | ✅ Partial | Dictionary only |
| **Bengali** | `bn` | ✅ Partial | Dictionary only |
| **Marathi** | `mr` | ✅ Partial | Dictionary only |

---

## Examples

### Example 1: Legal Definition Query

**Request:**
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is a tort?",
    "language": "en",
    "return_format": "markdown"
  }'
```

**Processing Flow:**
1. ✅ Classification: Legal definition query
2. ✅ LLM 1 Router: Select LAW_DICTIONARY tool
3. ✅ Tool Execution: Search for "tort" definition
4. ✅ LLM 2 Generator: Synthesize comprehensive response
5. ✅ Output: Formatted definition with examples

**Response:**
```json
{
  "status": "success",
  "query": "What is a tort?",
  "response": "# Tort\n\nA tort is a civil wrongdoing...",
  "tools_used": ["LAW_DICTIONARY"],
  "format": "markdown",
  "sources_count": 1,
  "timestamp": "2026-05-04T10:30:00Z"
}
```

---

### Example 2: Case Status Query (with CNR)

**Request:**
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the status of case CNR: ABCD1234567890?",
    "language": "en",
    "return_format": "markdown"
  }'
```

**Processing Flow:**
1. ✅ Classification: Case lookup query (CNR detected)
2. ✅ LLM 1 Router: Select eCOURTS tool
3. ✅ Tool Execution: Fetch case from eCourts API
4. ✅ LLM 2 Generator: Format case details
5. ✅ Output: Case status with next hearing date

**Response:**
```json
{
  "status": "success",
  "query": "What is the status of case CNR: ABCD1234567890?",
  "response": "## Case Status\n\n**Case Number:** ABCD1234567890\n**Status:** Active\n...",
  "tools_used": ["ECOURTS"],
  "format": "markdown",
  "sources_count": 1,
  "timestamp": "2026-05-04T10:30:00Z"
}
```

---

### Example 3: Comprehensive Legal Document Query

**Request:**
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the provisions for compensation under Section 304 of IPC?",
    "language": "en",
    "return_format": "markdown"
  }'
```

**Processing Flow:**
1. ✅ Classification: Legal document query
2. ✅ LLM 1 Router: Select MASTERDB + LAW_DICTIONARY
3. ✅ Tool Execution: 
   - Query MasterDB for Section 304
   - Search dictionary for "compensation" definition
4. ✅ LLM 2 Generator: Combine and synthesize response
5. ✅ Output: Comprehensive answer with citations

**Response:**
```json
{
  "status": "success",
  "query": "What are the provisions for compensation under Section 304 of IPC?",
  "response": "## Section 304 - Compensation Provisions\n\n...",
  "tools_used": ["MASTERDB", "LAW_DICTIONARY"],
  "format": "markdown",
  "sources_count": 2,
  "timestamp": "2026-05-04T10:30:00Z"
}
```

---

### Example 4: Hindi Language Query

**Request:**
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "भारतीय कानून में क्षति क्या है?",
    "language": "hi",
    "return_format": "markdown"
  }'
```

**Processing Flow:**
1. ✅ Classification: Language detected as Hindi
2. ✅ LLM 1 Router: Translate and select appropriate tools
3. ✅ Tool Execution: Search across tools
4. ✅ LLM 2 Generator: Generate response in Hindi
5. ✅ Output: Hindi formatted response

---

### Example 5: Complex Multi-Tool Query

**Request:**
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "I have a negligence case (CNR: ABCD1234567890). What constitutes negligence, what is the legal status of my case, and what does Section 304 say?",
    "language": "en",
    "return_format": "json"
  }'
```

**Processing Flow:**
1. ✅ Classification: Mixed query (definition + case + document)
2. ✅ LLM 1 Router: Select ALL tools (LAW_DICTIONARY, ECOURTS, MASTERDB)
3. ✅ Tool Execution (Parallel):
   - Dictionary: Definition of negligence
   - eCourts: Case status for ABCD1234567890
   - MasterDB: Section 304 information
4. ✅ LLM 2 Generator: Synthesize comprehensive response
5. ✅ Output: Structured JSON with all information

---

## Advanced Features

### 1. **Dual LLM Strategy**
- **Router (Cheap)**: GPT-4o-mini for quick, cost-efficient routing
- **Generator (Powerful)**: GPT-4 for accurate, nuanced responses
- **Result**: High quality at optimized cost

### 2. **Hybrid Search Technology**
- Combines vector semantics with keyword matching
- Cross-encoder reranking for relevance
- Term boosting for exact matches
- Better recall and precision

### 3. **Consistency Checking**
- Validates response quality before returning
- Checks for hallucinations
- Ensures data-driven accuracy
- Flags low-confidence responses

### 4. **Multi-Tool Orchestration**
- Parallel execution of up to 3 tools
- Intelligent tool selection
- Result aggregation and deduplication
- Smart response synthesis

### 5. **CNR Case Tracking**
- Automatic CNR detection in queries
- Real-time case status from eCourts
- Historical hearing information
- Order document tracking

---

## Troubleshooting

### Issue: No results from Law Dictionary
**Solutions:**
- Check if the index is properly initialized
- Verify embeddings are generated (`create_upload_index.py`)
- Try rephrasing the query with more legal terminology

### Issue: eCourts API connection fails
**Solutions:**
- Verify `ECOURT_USERNAME` and `ECOURT_PASSWORD` in `.env`
- Check network connectivity to `ECOURT_BASE_URL`
- Ensure CNR format is correct (typically 13 digits)

### Issue: Slow response times
**Solutions:**
- Check if Azure OpenAI API is responsive
- Monitor parallel tool execution
- Consider increasing timeout thresholds

### Issue: Low confidence responses
**Solutions:**
- Provide more detailed queries
- Use specific legal terminology
- Specify which tool should be used if known

---

## Performance Metrics

| Metric | Target | Status |
|--------|--------|--------|
| **Average Response Time** | < 5s | - |
| **Tool Selection Accuracy** | > 90% | - |
| **Response Quality (BLEU)** | > 0.75 | - |
| **Hallucination Rate** | < 2% | - |
| **Languages Supported** | 3+ | 6 |

---

## Future Enhancements

- [ ] Support for document uploads
- [ ] Fine-tuned Indian legal LLMs
- [ ] Real-time legal news integration
- [ ] Lawyer recommendation system
- [ ] Legal document generation (drafts)
- [ ] Audio input/output support
- [ ] Mobile app integration

---

## Support & Documentation

For issues or questions:
- Check the codebase docstrings in `orchestrator.py`
- Review test cases in `test_orchestrator.py`
- Consult Azure OpenAI documentation
- Check Azure Cognitive Search setup

---

**Last Updated:** May 2026  
**Version:** 2.0  
**Status:** ✅ Production Ready
