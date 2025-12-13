import os
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, send_file, render_template
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

# Create audio directory if it doesn't exist
AUDIO_DIR = os.path.join(os.getcwd(), "audio_files")
os.makedirs(AUDIO_DIR, exist_ok=True)

def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
   """Save PCM audio data as WAV file."""
   filepath = os.path.join(AUDIO_DIR, filename)
   with wave.open(filepath, "wb") as wf:
      wf.setnchannels(channels)
      wf.setsampwidth(sample_width)
      wf.setframerate(rate)
      wf.writeframes(pcm)
   logger.info(f"Saved audio file: {filename}")
   return filename

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
    prompt = f"""
    You are analyzing a 10-K filing.
    Section: {section_name}
    Text:
    {section_text}  # chunk to avoid token limits

    Task: Summarize the key points in plain English.
    """
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction="You are Warren Buffett. " \
            "Summarize financial documents clearly and concisely. " \
            "Using tenets from the document 'The Warren Buffett Way' by Robert Hagstrom in your analysis."),
        contents=prompt
    )
    return response.text

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/audio/<filename>")
def serve_audio(filename):
    """Serve audio files from the audio_files directory."""
    try:
        filepath = os.path.join(AUDIO_DIR, filename)
        if not os.path.exists(filepath):
            logger.warning(f"Audio file not found: {filename}")
            return jsonify({"error": "Audio file not found"}), 404
        return send_file(filepath, mimetype="audio/wav")
    except Exception as e:
        logger.error(f"Error serving audio file {filename}: {e}")
        return jsonify({"error": "Error serving audio file"}), 500

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

        # Generate TTS audio from summary using Gemini
        try:
            logger.info("Generating TTS audio...")
            tts_response = client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=f"Read this summary: {summary}",
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name='Kore',
                            )
                        )
                    ),
                )
            )

            data = tts_response.candidates[0].content.parts[0].inline_data.data
            filename = f"{ticker}_{section}_{uuid.uuid4().hex}.wav"
            wave_file(filename, data)
            logger.info(f"Successfully created audio file: {filename}")

            # Return JSON with summary and audio filename
            return jsonify({"ticker": ticker, "section": section, "summary": summary, "audio_file": filename})
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            return jsonify({"error": "Failed to generate audio"}), 500

    except Exception as e:
        logger.error(f"Error in analyze_10k: {e}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(debug=True)