import os
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, send_file, render_template, request
from google import genai
from google.genai import types
import re
import wave
import uuid
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Load your Gemini API key from environment
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GOOGLE_API_KEY not found in environment variables")
    raise ValueError("GOOGLE_API_KEY environment variable is required")

client = genai.Client(api_key=GEMINI_API_KEY)

headers = {"User-Agent": "Matthew matthew@example.com"}

def get_cik(ticker):
    """Resolve ticker to CIK using SEC API."""
    try:
        url = f"https://www.sec.gov/files/company_tickers.json"
        data = requests.get(url, headers=headers, timeout=10).json()
        for entry in data.values():
            if entry["ticker"].lower() == ticker.lower():
                logger.info(f"Found CIK for {ticker}")
                return str(entry["cik_str"]).zfill(10)
        logger.warning(f"CIK not found for ticker: {ticker}")
        return None
    except Exception as e:
        logger.error(f"Error getting CIK for {ticker}: {e}")
        return None

def get_latest_10k_url(cik):
    """Fetch latest 10-K filing URL for a company."""
    try:
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        data = requests.get(url, headers=headers, timeout=10).json()
        forms = data["filings"]["recent"]["form"]
        for i, form in enumerate(forms):
            if form == "10-K":
                accession = data["filings"]["recent"]["accessionNumber"][i]
                primary_doc = data["filings"]["recent"]["primaryDocument"][i]
                archive_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{primary_doc}"
                logger.info(f"Found 10-K URL for CIK {cik}")
                return archive_url
        logger.warning(f"No 10-K found for CIK: {cik}")
        return None
    except Exception as e:
        logger.error(f"Error getting 10-K URL for CIK {cik}: {e}")
        return None

def fetch_10k_text(url):
    """Fetch raw text from EDGAR 10-K filing URL."""
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        logger.info(f"Successfully fetched 10-K content")
        return soup.get_text(separator="\n")
    except Exception as e:
        logger.error(f"Error fetching 10-K: {e}")
        return None

def extract_sections(text):
    """
    Extract major narrative sections from a 10-K filing using regex.
    Returns a dictionary with section names and full text.
    """
    sections = {}
    
    patterns = [
        (r"item\s+1[.\s]+business", "Business", r"item\s+1a"),
        (r"item\s+1a[.\s]+risk\s+factors", "Risk Factors", r"item\s+1b"),
        (r"item\s+7[.\s]+management|item\s+7[.\s]+md&a", "Management's Discussion and Analysis", r"item\s+7a|item\s+8"),
        (r"item\s+7a[.\s]+quantitative", "Quantitative and Qualitative Disclosures", r"item\s+8"),
        (r"item\s+8[.\s]+financial", "Financial Statements", r"item\s+9"),
    ]
    
    for start_pattern, name, end_pattern in patterns:
        # Find all matches of the start pattern
        matches = list(re.finditer(start_pattern, text, re.IGNORECASE))
        if not matches:
            print(f"⚠ Section not found: {name}")
            continue
        
        # Use the *last* match (skips TOC, grabs real section body)
        start = matches[-1].start()
        
        end_match = re.search(end_pattern, text[start:], re.IGNORECASE)
        end = start + end_match.start() if end_match else len(text)
        
        section_text = text[start:end].strip()
        sections[name] = section_text
    
    return sections

def analyze_with_gemini(section_name, section_text):
    """Send section text to Gemini for summarization."""
    # Truncate to avoid huge API payloads and timeouts
    MAX_TEXT_LENGTH = 100000
    truncated_text = section_text[:MAX_TEXT_LENGTH]
    if len(section_text) > MAX_TEXT_LENGTH:
        truncated_text += f"\n\n[Text truncated - original length: {len(section_text)} characters]"

    # Per-section prompt templates and (optional) model choices
    section_key = (section_name or "").lower()

    prompt_templates = {
        "business": (
            "You are an equity analyst focusing on business model, market position, "
            "and competitive advantages.\n\nSection: {section_name}\n\n{section_text}\n\n"
            "Tasks:\n"
            "- Explain the business model and primary revenue drivers.\n"
            "- Identify signs of durable competitive advantage (moat).\n"
            "- Note material data gaps and where to look next.\n"
            "Deliverable: Concise memo (bulleted, 6-10 bullets)."
        ),
        "risk factors": (
            "You are a risk analyst.\n\nSection: {section_name}\n\n{section_text}\n\n"
            "Tasks:\n"
            "- Extract and summarize top 5 material risks with likelihood/impact.\n"
            "- Flag any qualitative language that obscures magnitude.\n"
            "Deliverable: Ranked risk list with short rationale."
        ),
        "management's discussion and analysis": (
            "You are a financial analyst focused on management commentary.\n\nSection: {section_name}\n\n{section_text}\n\n"
            "Tasks:\n"
            "- Pull out key operating metrics, trends, and management tone.\n"
            "- Assess disclosures for transparency and conservative accounting.\n"
            "Deliverable: MD&A summary with citations to named disclosures."
        ),
        "quantitative and qualitative disclosures": (
            "You are a numbers-focused analyst.\n\nSection: {section_name}\n\n{section_text}\n\n"
            "Tasks:\n"
            "- Identify material quantitative disclosures and reconcile to narrative.\n"
            "- Call out rounding, restatements, or discrepancies.\n"
            "Deliverable: Short reconciled data checklist."
        ),
        "financial statements": (
            "You are an accounting and valuation analyst.\n\nSection: {section_name}\n\n{section_text}\n\n"
            "Tasks:\n"
            "- Summarize income statement, balance sheet, cash flow highlights.\n"
            "- Extract free cash flow and perform a quick sanity DCF.\n"
            "Deliverable: Key financials + headline valuation range."
        ),
        "combined": (
            "You are a senior investor synthesizing Business, Risks, and MD&A.\n\nSection: {section_name}\n\n{section_text}\n\n"
            "Tasks:\n"
            "- Produce an integrated moat & durability memo in Buffett style.\n"
            "- Provide one suggested follow-up question and critical citations.\n"
            "Deliverable: 1-page investor memo."
        ),
    }

    # Lightweight model selection per section (defaults to the flash model)
    model_map = {
        "financial statements": "gemini-2.5-flash",
        "combined": "gemini-2.5-flash",
        "management's discussion and analysis": "gemini-2.5-flash",
        "risk factors": "gemini-2.5-flash",
        "business": "gemini-2.5-flash",
        "quantitative and qualitative disclosures": "gemini-2.5-flash",
    }

    template = prompt_templates.get(section_key, None)
    if template:
        prompt = template.format(section_name=section_name, section_text=truncated_text)
    else:
        # Fallback to a general Buffett-style analytic prompt
        prompt = (
            f"You are a Berkshire-style analyst.\nSection: {section_name}\n\n{truncated_text}\n\n"
            "Tasks: Identify moat, management quality, cashflow durability, and valuation.\n"
            "Deliverable: Bulleted memo."
        )

    model = model_map.get(section_key, "gemini-2.5-flash")

    try:
        response = client.models.generate_content(
            model=model,
            config=types.GenerateContentConfig(system_instruction="You are an expert investment analyst."),
            contents=prompt
        )
        # `response.text` is used elsewhere in the file; preserve that interface
        return getattr(response, "text", None) or str(response)
    except Exception as e:
        logger.error(f"Gemini API error for section '{section_name}': {e}")
        raise

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/analyze/10k/<ticker>/<section>")
def analyze_10k(ticker, section):
    try:
        logger.info(f"Analyzing 10-K for {ticker} - {section}")
        cik = get_cik(ticker)
        if not cik:
            return jsonify({"error": "Ticker not found"}), 404
        url = get_latest_10k_url(cik)
        if not url:
            return jsonify({"error": "No 10-K found"}), 404
        text = fetch_10k_text(url)
        if not text:
            return jsonify({"error": "Failed to fetch 10-K content"}), 500
        
        sections = extract_sections(text)

        # Normalize keys for lookup
        normalized_sections = {k.lower(): v for k, v in sections.items()}

        # Build a combined section of Business + Risk Factors + MD&A
        combined_order = [
            "business",
            "risk factors",
            "management's discussion and analysis"
        ]
        combined_parts = []
        for key in combined_order:
            if key in normalized_sections:
                # add a clear header before each part
                header = key.title()
                combined_parts.append(f"{header}\n\n{normalized_sections[key]}")

        if combined_parts:
            normalized_sections["combined"] = "\n\n".join(combined_parts)

        print(f"✓ Found sections: {list(normalized_sections.keys())}")
        section_key = section.lower()

        if section_key not in normalized_sections:
            return jsonify({"error": f"Section {section} not found"}), 404

        summary = analyze_with_gemini(section, normalized_sections[section_key])
        if not summary:
            return jsonify({"error": "Failed to generate summary"}), 500

        # Return summary only (TTS disabled)
        return jsonify({"ticker": ticker, "section": section, "summary": summary})

    except Exception as e:
        logger.error(f"Error in analyze_10k: {e}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(debug=True)