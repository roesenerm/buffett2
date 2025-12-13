# Warren Buffett 10-K Analyzer

A production-ready Flask web application that analyzes SEC 10-K filings using Google Gemini AI, generates Warren Buffett-style summaries, and creates audio narration via Text-to-Speech.

## Features

- 🔍 **SEC Filing Analysis**: Fetch 10-K filings directly from SEC EDGAR
- 🤖 **AI-Powered Summaries**: Uses Google Gemini to generate insightful analysis
- 🎙️ **Text-to-Speech**: Generates audio narration of summaries
- 🎯 **Multiple Sections**: Analyze Business, Risk Factors, Financial Analysis, etc.
- 📱 **Responsive Web UI**: Clean, modern interface works on desktop and mobile
- 🔧 **Production Ready**: Error handling, logging, timeouts, environment configuration

## Quick Start

### Local Development

1. **Clone/setup directory**:
   ```bash
   cd buffett2
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup environment variables**:
   ```bash
   # Create .env file
   echo GOOGLE_API_KEY=your-api-key-here > .env
   echo FLASK_ENV=development >> .env
   ```

5. **Get your Google API key**:
   - Visit https://ai.google.dev/
   - Click "Get API Key"
   - Paste into `.env` file

6. **Run locally**:
   ```bash
   # Development (Flask dev server)
   python buffett_app.py
   
   # OR Production (Gunicorn)
   gunicorn -w 4 -b 0.0.0.0:8000 buffett_app:app
   ```

7. **Open browser**:
   ```
   http://localhost:5000  (Flask dev)
   http://localhost:8000  (Gunicorn production)
   ```

## API Endpoints

### GET `/`
Returns the web interface (index.html)

### GET `/analyze/10k/<ticker>/<section>`
Analyzes a 10-K section and returns JSON with summary + audio filename

**Parameters**:
- `ticker`: Stock ticker symbol (e.g., AAPL, MSFT)
- `section`: Section name (e.g., item-1, item-7, item-1a)

**Available Sections**:
- `item-1`: Business
- `item-1a`: Risk Factors
- `item-7`: Management's Discussion & Analysis (MD&A)
- `item-8`: Financial Statements
- `item-9`: Changes in and Disagreements with Accountants
- `item-10`: Directors, Executive Officers, Corporate Governance
- And more...

**Response**:
```json
{
  "ticker": "AAPL",
  "section": "item-7",
  "summary": "Apple's Item 7 analysis...",
  "audio_file": "AAPL_item-7_abc123def456.wav"
}
```

**Error Response**:
```json
{
  "error": "Ticker not found"
}
```

### GET `/audio/<filename>`
Serves the WAV audio file

**Example**:
```
GET /audio/AAPL_item-7_abc123def456.wav
```

## Production Deployment

### Option 1: GoDaddy Shared Hosting
See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed cPanel instructions

### Option 2: VPS/Dedicated Server
```bash
# SSH into server
ssh user@your-domain.com
cd /var/www/buffett2

# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env with your API key
echo GOOGLE_API_KEY=your-key > .env
echo FLASK_ENV=production >> .env

# Run with Gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 --timeout 120 buffett_app:app
```

### Option 3: Docker (Advanced)
```dockerfile
FROM python:3.11
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "buffett_app:app"]
```

## Configuration

### Environment Variables
Create `.env` file in project root:

```env
# Required
GOOGLE_API_KEY=your-google-generative-ai-api-key

# Optional
FLASK_ENV=production
FLASK_DEBUG=False
LOG_LEVEL=INFO
```

### Logging
The app logs to console by default. In production, redirect to file:

```bash
gunicorn ... buffett_app:app > app.log 2>&1 &
```

## Project Structure

```
buffett2/
├── buffett_app.py          # Main Flask application
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variable template
├── .env                   # Your actual secrets (not in git)
├── README.md              # This file
├── DEPLOYMENT.md          # Detailed deployment guide
├── start.sh               # Linux/Mac startup script
├── start.bat              # Windows startup script
├── templates/
│   └── index.html         # Web interface
└── audio_files/           # Generated audio WAV files
    ├── AAPL_item-7_*.wav
    ├── MSFT_item-1a_*.wav
    └── ...
```

## Dependencies

- **Flask 3.0.3**: Web framework
- **google-genai 0.4.2**: Gemini AI API client
- **requests 2.31.0**: HTTP library for SEC EDGAR
- **beautifulsoup4 4.12.2**: HTML parsing
- **python-dotenv 1.0.0**: Environment variable management
- **gunicorn 21.2.0**: WSGI production server

## API Limits & Costs

### Google Generative AI
- Free tier includes generous daily quotas
- Monitor usage at https://ai.google.dev/dashboard
- Each 10-K analysis = ~2 API calls (text analysis + TTS)

### SEC EDGAR
- Public API, no authentication required
- Rate limit: ~10 requests per second
- No cost

## Troubleshooting

### "No 10-K found"
- Ensure ticker is correct (AAPL, MSFT, etc.)
- Company must have filed 10-K with SEC

### Audio not generating
- Verify GOOGLE_API_KEY is valid in .env
- Check API quota at Google AI dashboard
- Review logs for error details

### Slow responses
- Initial analysis takes 10-20 seconds (normal)
- Audio generation takes 5-10 seconds (normal)
- Increase `--timeout` in Gunicorn if getting timeouts

### Port already in use
```bash
# Use different port
gunicorn -b 0.0.0.0:8001 buffett_app:app

# Or kill existing process
lsof -ti:8000 | xargs kill -9
```

## Performance Tips

1. **Cache summaries** for repeated requests
2. **Cleanup old audio files** periodically:
   ```bash
   find audio_files -type f -mtime +30 -delete  # Older than 30 days
   ```
3. **Increase Gunicorn workers** based on CPU cores:
   ```bash
   gunicorn -w 8 buffett_app:app  # 8 workers
   ```
4. **Use Redis/Memcached** for session/cache in future

## Security Considerations

- ✅ Never commit `.env` with real API keys
- ✅ Use HTTPS in production
- ✅ Disable Flask debug mode (done by default)
- ⚠️ Consider rate limiting for public deployment
- ⚠️ Monitor API costs to prevent surprises

## Future Enhancements

- [ ] Caching system for summaries
- [ ] User accounts and favorites
- [ ] Export summaries as PDF
- [ ] Multiple AI models (Claude, GPT, etc.)
- [ ] Batch analysis (multiple companies)
- [ ] Email scheduled reports
- [ ] Admin dashboard with analytics

## License

This project is provided as-is for educational and investment research purposes.

## Support

For issues or questions:
1. Review logs in `app.log` or console
2. Check GOOGLE_API_KEY configuration
3. Verify network connectivity to SEC EDGAR and Google APIs
4. See [DEPLOYMENT.md](DEPLOYMENT.md) for production-specific help
