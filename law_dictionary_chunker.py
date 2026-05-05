"""
Legal Dictionary PDF Parser
----------------------------
Extracts legal terms and definitions from a text-based PDF
and saves them as a JSON file with 2 fields per term:
  - part_of_speech
  - definition

Requirements:
    pip install pypdf

Usage:
    python parse_legal_pdf.py
"""

import re
import json
from pypdf import PdfReader

# ─── CONFIG ───────────────────────────────────────────────────────────────────
PDF_PATH    = "Legal-Dictionery.pdf"   # path to your PDF
OUTPUT_PATH = "legal_dictionary.json"  # output JSON file
# ──────────────────────────────────────────────────────────────────────────────

# Step 1: Extract text from all pages using pypdf
print("Reading PDF...")
reader = PdfReader(PDF_PATH)
raw = ""
for page in reader.pages:
    text = page.extract_text()
    if text:
        raw += text + "\n"

print(f"Extracted text from {len(reader.pages)} pages.")

# Step 2: Remove page headers/footers
# Lines like: "Essential Legal Dictionary:Layout 1   4/21/08   5:23 PM   Page 7"
raw = re.sub(
    r'Essential Legal Dictionary:Layout 1\s+\d+/\d+/\d+\s+\d+:\d+\s+[AP]M\s+Page\s+\w+',
    '', raw
)

# Step 3: Remove form feed characters between pages
raw = raw.replace('\f', '\n')

# Step 4: Collapse multiple blank lines into one
raw = re.sub(r'\n{3,}', '\n\n', raw)

# Step 5: Split text into blocks separated by blank lines
blocks = re.split(r'\n\n+', raw)

# Step 6: Define pattern to detect a dictionary entry
# Each entry starts with: term. POS_ABBREVIATION. Definition
# e.g. "abandon. V. To intentionally give up..."
pos_pattern = re.compile(
    r'^(.+?)\.\s+(N\.|V\.|ADJ\.|ADV\.|ABBRV\.|CONJ\.|PREP\.|PHRASE\.|INTERJ\.)',
    re.DOTALL
)

entries = []
seen_terms = set()

for block in blocks:
    block = block.strip()
    if not block:
        continue

    # Collapse internal whitespace/newlines into single spaces
    block = re.sub(r'[ \t]+', ' ', block)
    block = block.replace('\n', ' ').strip()

    m = pos_pattern.match(block)
    if not m:
        continue

    term = m.group(1).strip()

    # Skip malformed keys (too long, or contain junk from page layout)
    if len(term) > 80:
        continue

    # Skip publisher/copyright noise that slipped through
    if any(x in term for x in ['Layout', 'Copyright', 'Sourcebooks', 'www.', 'ISBN', 'Naperville']):
        continue

    pos_raw     = m.group(2).rstrip('.')          # e.g. "N", "V", "ADJ"
    definition  = block[m.end():].strip().lstrip('. ').strip()

    key = term.lower()

    if key in seen_terms:
        # Append alternate sense to existing entry instead of duplicating
        for e in reversed(entries):
            if e['term'].lower() == key:
                e['definition'] += ' | ' + definition
                break
        continue

    seen_terms.add(key)
    entries.append({
        'term':       term,
        'definition': definition,
        'part_of_speech': pos_raw
    })

# Step 7: Build final dict keyed by term
legal_dict = {}
for e in entries:
    legal_dict[e['term']] = {
        'part_of_speech': e['part_of_speech'],
        'definition':     e['definition']
    }

# Step 8: Save to JSON
with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(legal_dict, f, indent=2, ensure_ascii=False)

print(f"Done. {len(legal_dict)} terms saved to {OUTPUT_PATH}")