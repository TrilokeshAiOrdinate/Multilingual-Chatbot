import re

# ============================================================
# Jurisdiction Mapping (MUST MATCH INDEX VALUES EXACTLY)
# ============================================================

STATE_KEYWORDS = {

    # -------- STATES --------
    "andhra pradesh": "Andhra Pradesh",
    "arunachal pradesh": "Arunachal Pradesh",
    "assam": "Assam",
    "bihar": "Bihar",
    "chhattisgarh": "Chhattisgarh",
    "goa": "Goa",
    "gujarat": "Gujurat",
    "haryana": "Haryana",
    "himachal pradesh": "Himachal Pradesh",
    "jharkhand": "Jharkhand",
    "karnataka": "Karnataka",
    "kerala": "Kerala",
    "madhya pradesh": "Madhya Pradesh",
    "maharashtra": "Maharashtra",
    "manipur": "Manipur",
    "meghalaya": "Meghalaya",
    "mizoram": "Mizoram",
    "nagaland": "Nagaland",
    "odisha": "Odisha",
    "orissa": "Odisha",
    "punjab": "Punjab",
    "rajasthan": "Rajasthan",
    "sikkim": "Sikkim",
    "tamil nadu": "Tamil Nadu",
    "telangana": "Telangana",
    "tripura": "Tripura",
    "uttar pradesh": "Uttar Pradesh",
    "uttarakhand": "Uttarakhand",
    "west bengal": "West Bengal",

    # -------- UNION TERRITORIES --------
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "jammu and kashmir": "Jammu and Kashmir",
    "ladakh": "Ladakh",
    "puducherry": "Puducherry",
    "pondicherry": "Puducherry",
    "chandigarh": "Chandigarh",

    "andaman and nicobar": "Andaman and Nicobar Islands",
    "andaman & nicobar": "Andaman and Nicobar Islands",

    "dadra and nagar haveli": "Dadra and Nagar Haveli and Daman and Diu",
    "daman and diu": "Dadra and Nagar Haveli and Daman and Diu",
    "dadra & nagar haveli": "Dadra and Nagar Haveli and Daman and Diu",

    "lakshadweep": "Lakshadweep",

    # -------- CENTRAL --------
    "india": "India",
    "central": "India",
    "union of india": "India",
    "central government": "India",
}

# ============================================================
# Normalize Query
# ============================================================

def normalize(text: str):
    text = text.lower()
    text = re.sub(r"[_\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ============================================================
# Extract Filters
# ============================================================

def extract_filters(query: str):

    q = normalize(query)
    filters = {}

    # --------------------------------------------------------
    # Jurisdiction Detection
    # --------------------------------------------------------
    detected_state = None

    for state in sorted(STATE_KEYWORDS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(state)}\b", q):
            detected_state = STATE_KEYWORDS[state]
            q = re.sub(rf"\b{re.escape(state)}\b", "", q)
            break

    filters["jurisdiction"] = detected_state if detected_state else "India"

    # --------------------------------------------------------
    # YEAR Detection + Intent
    # --------------------------------------------------------
    year_match = re.search(r"\b(19|20)\d{2}\b", q)

    if year_match:
        year = year_match.group()

        # STRICT AFTER
        if re.search(r"\b(after|post|later than|beyond|newer than)\b", q):
            filters["date_op"] = "gt"
            filters["date"] = year

        # SINCE / FROM
        elif re.search(r"\b(since|from)\b", q):
            filters["date_op"] = "ge"
            filters["date"] = year

        # STRICT BEFORE
        elif re.search(r"\b(before|earlier than|older than|pre)\b", q):
            filters["date_op"] = "lt"
            filters["date"] = year

        # UPTO / TILL
        elif re.search(r"\b(till|upto|up to)\b", q):
            filters["date_op"] = "le"
            filters["date"] = year

        # EXACT YEAR
        else:
            filters["date_from"] = year
            filters["date_to"] = year

        q = re.sub(rf"\b{year}\b", "", q)

    # --------------------------------------------------------
    # Clean Remaining Query
    # --------------------------------------------------------
    q = re.sub(r"\s+", " ", q).strip()

    return filters, q


# ============================================================
# Azure Filter Builder
# ============================================================

def build_azure_filter(filters):

    parts = []

    # Jurisdiction
    if filters.get("jurisdiction"):
        parts.append(
            f"jurisdiction eq '{filters['jurisdiction']}'"
        )

    # Operator-based date filtering
    if filters.get("date_op") and filters.get("date"):
        parts.append(
            f"(date {filters['date_op']} '{filters['date']}')"
        )

    # Exact year range
    elif filters.get("date_from") and filters.get("date_to"):
        parts.append(
            f"(date ge '{filters['date_from']}' and date le '{filters['date_to']}')"
        )

    return " and ".join(parts) if parts else None