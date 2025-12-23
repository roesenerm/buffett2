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
    MAX_TEXT_LENGTH = 15000
    truncated_text = section_text[:MAX_TEXT_LENGTH]
    if len(section_text) > MAX_TEXT_LENGTH:
        truncated_text += f"\n\n[Text truncated - original length: {len(section_text)} characters]"
    
    prompt = f"""
    You are a Berkshire-style analyst applying The Warren Buffett Way tenets. " \
    "Task: From the {section_name} and {truncated_text}, evaluate: economic moat (brand, network effects, data flywheel, economies of scale, switching costs), " \
    "customer/user retention, moat trajectory, 100-year durability & 5-year market closure resilience," \
    "return on invested capital (ROIC) and its sustainability, and intrinsic value vs. market value. " \
    "Conclude with how Buffett/Munger might view the company." \
    "Sources/Constraints: Be specific, show math, and call out data gaps. " \
    "Plan (Buffett Way):" \
    "A: Business Tenets - Is the business simple and understandable? Does it have a consistent record and favorable long-term prospects supported by moat pillars?" \
    "B: Management Tenets - Is management rational, candid, and resistant to the institutional imperative? Is capital allocation owner oriented?" \
    "C: Financial Tenets - Compute ROIC. Are returns on invested capital high and increasing? Is the company free cash flow positive with strong margins? Is retained earnings growing more than its market value per year?" \
    "D: Valuation Tenets - Estimate instrinsic value (DCF/free cash flow) Is the stock price significantly below intrinsic value with a margin of safety? Is the market undervaluing the company's long-term prospects? Compare to market value (disocunt/fair/premium)"  \
    "Checkpoints: After each section, note the evidence that supports/contradicts the tenet (e.g., 'Retnetion metric located in MD&A section shows; reconciles to Notes)'. " \
    "If a check fails, stop, explain the gap, revise the plan, and resume that section." \
    "In-step refine (self-query): When the 10k is vague, ask one targeted question (e.g., 'Where is cusomter concetration discolsed?') and use that answer to proceed. " \
    "Delieverable:" \
    "Moat & Durability memo (bulleted; 1 page)" \
    "Owner-Earnings & ROIC worksheet (inputs, formulas, results)" \
    "Valuation summary (method, assumptions, range, market vs. intrinsic value, margin of safety)" \
    "Buffett/Munger lens (pass, fail per tent, with citations)"
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction="You are Warren Buffett."),
            contents=prompt
        )
        return response.text
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
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