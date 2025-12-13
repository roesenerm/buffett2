# Production Deployment Guide

## Overview
This Flask app analyzes SEC 10-K filings using Google Gemini AI and generates audio summaries. This guide covers deployment to GoDaddy or similar shared/dedicated hosting.

## Prerequisites
- Python 3.8+
- Access to your hosting server (SSH, cPanel, or file manager)
- Domain name configured to point to your server
- Google Generative AI API key

## Step 1: Setup on Your Server

### Using GoDaddy Shared Hosting (cPanel)
1. Log into cPanel
2. Navigate to "File Manager" or use SFTP to upload files
3. Upload the entire `buffett2` folder to your `public_html` directory
4. Go to "Setup Python App" in cPanel (or use SSH if not available)

### Using GoDaddy VPS or Dedicated Server (SSH)
```powershell
# SSH into your server
ssh user@your-domain.com

# Navigate to your app directory
cd /home/username/public_html/buffett2

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Environment Configuration

1. Create a `.env` file in your app directory:
```
GOOGLE_API_KEY=your-actual-google-api-key-here
FLASK_ENV=production
```

2. Get your Google API key:
   - Go to https://ai.google.dev/
   - Click "Get API Key"
   - Copy your key into `.env`

## Step 3: File Structure
Your server directory should look like:
```
buffett2/
├── buffett_app.py
├── requirements.txt
├── .env (keep this secret!)
├── DEPLOYMENT.md (this file)
├── templates/
│   └── index.html
├── audio_files/ (will be created automatically)
└── venv/ (created after pip install)
```

## Step 4: Running on Production

### Option A: Using Gunicorn (Recommended for VPS/Dedicated)
```bash
# Activate virtual environment
source venv/bin/activate

# Run with Gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 buffett_app:app --timeout 120 --access-logfile - --error-logfile -
```

### Option B: Using Python directly (Shared hosting with app configuration)
```bash
python buffett_app.py
```

### Option C: Using cPanel Python App Selector (GoDaddy Shared Hosting)
1. Go to cPanel → Setup Python App
2. Create new application
3. Select Python version (3.8+)
4. Set app root to your buffett2 directory
5. Configure domain/subdomain
6. cPanel will handle WSGI automatically

## Step 5: Configure Your Domain

### In GoDaddy DNS Settings:
1. Log into GoDaddy account
2. Go to "My Products" → "Domains"
3. Manage DNS for your domain
4. Point A record to your server IP
5. If using a subdomain (e.g., analysis.yourdomain.com):
   - Add new CNAME record
   - Name: `analysis`
   - Points to: `yourdomain.com`

### If using GoDaddy Shared Hosting (cPanel):
- Use "Addon Domains" or "Subdomains" section in cPanel
- cPanel automatically configures DNS

## Step 6: SSL Certificate (HTTPS)

### Using Let's Encrypt (Free):
```bash
# Most hosting providers support Let's Encrypt in cPanel
# In cPanel: AutoSSL (automatic) or manual Let's Encrypt
```

### Using GoDaddy SSL:
1. Purchase SSL certificate from GoDaddy
2. Install through cPanel or your hosting control panel

**Important:** Keep `FLASK_ENV=production` in `.env` when running on production server.

## Step 7: Monitor Your App

### Check logs:
```bash
# If using Gunicorn, logs appear in terminal
# Save to file:
gunicorn -w 4 -b 0.0.0.0:8000 buffett_app:app > /var/log/buffett.log 2>&1 &

# View logs:
tail -f /var/log/buffett.log
```

### Test your app:
```bash
# From your local machine
curl https://yourdomain.com/
curl https://yourdomain.com/analyze/10k/AAPL/item-7

# Check audio file serving
curl https://yourdomain.com/audio/AAPL_item-7_*.wav
```

## Troubleshooting

### "Module not found" errors:
```bash
# Ensure virtual environment is activated and requirements installed
pip install -r requirements.txt
```

### Audio files not generating:
1. Verify GOOGLE_API_KEY in `.env` is correct
2. Check API quota and billing in Google Cloud Console
3. Review logs for specific error messages

### Port already in use:
```bash
# Use different port
gunicorn -w 4 -b 0.0.0.0:8001 buffett_app:app
```

### Connection refused:
1. Ensure firewall allows your port
2. Verify domain DNS is pointing to server
3. Check if app is running: `ps aux | grep gunicorn`

## Performance Tips

1. **Increase Gunicorn workers** (if server has RAM):
   ```bash
   gunicorn -w 8 buffett_app:app  # Adjust based on CPU cores
   ```

2. **Enable caching** (for repeated requests):
   - Add Redis or simple file-based cache in future versions

3. **Cleanup old audio files** (periodic maintenance):
   ```bash
   # Remove audio files older than 7 days
   find audio_files/ -type f -mtime +7 -delete
   ```

4. **Set up log rotation** (prevent disk space issues):
   ```bash
   # Create logrotate config for /var/log/buffett.log
   ```

## Security Notes

- Keep `.env` file private (never commit to git)
- Use HTTPS only in production
- Disable Flask debug mode (already done in production)
- Consider adding rate limiting for API calls
- Monitor API usage to avoid unexpected costs

## Support

If you encounter issues:
1. Check application logs
2. Verify GOOGLE_API_KEY is active and has quota
3. Test with curl commands above
4. Review Flask error messages in terminal/logs
