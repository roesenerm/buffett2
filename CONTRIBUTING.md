# Contributing to Warren Buffett 10-K Analyzer

Thank you for your interest in contributing! This document provides guidelines and instructions.

## Code of Conduct

- Be respectful and constructive in all interactions
- Focus on the code, not the person
- Help others learn and grow

## How to Contribute

### Reporting Bugs
1. Check if the bug has already been reported in Issues
2. Include:
   - Python version and OS
   - Steps to reproduce
   - Expected vs actual behavior
   - Error messages/logs

### Suggesting Features
1. Open an Issue with the title "Feature: [description]"
2. Explain the use case and benefits
3. Provide examples if applicable

### Pull Requests
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Test thoroughly
5. Commit with clear messages: `git commit -m "Add amazing feature"`
6. Push to your fork: `git push origin feature/amazing-feature`
7. Open a Pull Request with a clear description

## Development Setup

```bash
# Clone your fork
git clone https://github.com/your-username/buffett.git
cd buffett2

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup .env for testing
cp .env.example .env
# Add your GOOGLE_API_KEY
```

## Testing

```bash
# Run the app locally
python buffett_app.py

# Test with Gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 buffett_app:app

# Test specific endpoint
curl http://localhost:8000/
curl "http://localhost:8000/analyze/10k/AAPL/item-7"
```

## Code Style

- Follow PEP 8 Python style guide
- Use meaningful variable names
- Add comments for complex logic
- Keep functions focused and DRY (Don't Repeat Yourself)

## Areas for Contribution

- 🐛 Bug fixes
- 📚 Documentation improvements
- ⚡ Performance optimizations
- 🎨 UI/UX improvements
- 🔧 Additional AI models (Claude, GPT, etc.)
- 📊 Caching system
- 🔐 Security enhancements
- 🧪 Testing framework

## Questions?

Open an Issue with the label "question" or check existing discussions.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
