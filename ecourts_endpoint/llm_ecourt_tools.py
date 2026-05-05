"""
Tool schemas exposed to the LLM during the agentic loop.

Four tools cover the full surface of this legal assistant:
  1. search_judgments    — semantic + keyword search across the judgment corpus
  2. lookup_statute      — retrieve judgments that cite a specific Act / section
  3. fetch_live_case     — live eCourts scrape for procedural / status data
  4. get_related_cases   — find cases semantically similar to a known case ID
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_judgments",
            "description": (
                "Search historical court judgments and legal precedents from the master database "
                "using a hybrid of semantic (vector) and full-text search. "
                "Use this for queries about legal principles, constitutional provisions, "
                "landmark rulings, or any fact-based legal question that does not require live data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A focused legal search query. Be specific — e.g. 'anticipatory bail under Section 438 CrPC' rather than 'bail'."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of judgments to return (default 5, max 10).",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_statute",
            "description": (
                "Find judgments that specifically reference a named Indian Act and/or section number. "
                "Use this when the user asks about a particular statute, e.g. "
                "'Section 138 Negotiable Instruments Act' or 'Article 21 Constitution of India'. "
                "More targeted than search_judgments for statute-specific queries."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "act_name": {
                        "type": "string",
                        "description": "Name of the Act or constitutional provision, e.g. 'Indian Penal Code', 'Constitution of India', 'Consumer Protection Act'."
                    },
                    "section": {
                        "type": "string",
                        "description": "Section or article number as a string, e.g. '302', '21', '138'. Omit if searching the whole Act."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (default 5).",
                        "default": 5
                    }
                },
                "required": ["act_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_live_case",
            "description": (
                "Fetch live, real-time case data from the Indian eCourts system via the LegTech API. "
                "Use this for queries about: current case status, upcoming hearing dates, recent orders, "
                "pending matters, case transfer, or any procedural update that requires today's data. "
                "Supports lookup by CNR number (16-char code like MHAU010012342023) or numeric case ID. "
                "Do NOT use this for historical legal analysis — use search_judgments instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "CNR number (e.g. MHAU010012342023) OR a numeric case ID (e.g. 4521). "
                            "Use CNR when the user provides it directly; use a case ID for follow-up lookups."
                        )
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_case_orders",
            "description": (
                "Retrieve the list of orders passed in a specific eCourt case. "
                "Use this when the user asks about orders, judgments, or directives issued in a case "
                "identified by a numeric case ID."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "case_id": {
                        "type": "integer",
                        "description": "Numeric case ID returned by fetch_live_case."
                    }
                },
                "required": ["case_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_case_history",
            "description": (
                "Retrieve the full hearing / cause-list history for an eCourt case. "
                "Use this when the user wants to see past hearing dates, adjournments, or the procedural timeline."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "case_id": {
                        "type": "integer",
                        "description": "Numeric case ID returned by fetch_live_case."
                    }
                },
                "required": ["case_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sync_case",
            "description": (
                "Trigger a fresh sync of an eCourt case from the live eCourts portal. "
                "Use this when the user explicitly asks to refresh or update case data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "case_id": {
                        "type": "integer",
                        "description": "Numeric case ID to sync."
                    }
                },
                "required": ["case_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_related_cases",
            "description": (
                "Given a specific case ID already retrieved, find other judgments in the database "
                "that are semantically related (similar facts, legal issues, or doctrine). "
                "Use this as a follow-up after search_judgments to broaden the precedent landscape."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "case_id": {
                        "type": "integer",
                        "description": "The integer ID of a judgment already retrieved in this session."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of related cases to fetch (default 4).",
                        "default": 4
                    }
                },
                "required": ["case_id"]
            }
        }
    }
]
