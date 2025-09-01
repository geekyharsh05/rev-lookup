# 🚀 LinkedIn Profile Extractor API

A comprehensive system for extracting LinkedIn profiles through Outlook authentication with automatic token management.

## 🏗️ Features

- **Automatic Token Management**: Handles 2-hour token expiration automatically
- **Multiple API Endpoints**: GET and POST endpoints for single and batch processing
- **Enhanced Batch Processing**: JavaScript-style batch processing with progress tracking
- **Persistent Sessions**: Browser session management with auto-restart
- **Token Storage**: Always uses `token.txt` for reliable token persistence
- **Rate Limiting**: Smart delays and break intervals to avoid API limits

## 📦 Installation

### Use uv as the package manager

Download UV from here: [Click Here](https://docs.astral.sh/uv/getting-started/installation/#__tabbed_1_2)

```bash
# Install dependencies
uv sync
```

## ⚙️ Configuration

Set the environment variables:

```bash
OUTLOOK_EMAIL=your@outlook.com
OUTLOOK_PASSWORD=your_password
```

## 🚀 Quick Start

### 1. Start the Complete System

```bash
# Start both persistent session and API server
uv run launch_complete_system.py
```

### 2. Or Start Components Individually

```bash
# Option A: Just the API server
uv run uvicorn api_server:app --host 0.0.0.0 --port 8000

# Option B: Just extract tokens
uv run outlook.py

# Option C: Test the API
uv run test_api.py
```

## 📡 API Endpoints

### Single Profile Endpoints

```bash
# GET endpoint (email in URL)
GET /profile/{email}

# POST endpoint (email in body) - NEW!
POST /profile
Body: {"email": "user@example.com"}
```

### Batch Processing Endpoints

```bash
# Standard batch processing
POST /profiles/batch
Body: {
  "emails": ["email1@example.com", "email2@example.com"],
  "delay_seconds": 2
}

# Enhanced batch processing with JavaScript-style features
POST /profiles/batch/enhanced
Body: {
  "emails": ["email1@example.com", "email2@example.com"],
  "delay_seconds": 2,
  "stop_on_error": false,
  "save_individual_files": true,
  "long_break_interval": 10,
  "long_break_duration": 10
}
```

### Token Management

```bash
# Check token status
GET /token/status

# Force token refresh
POST /token/refresh

# Health check
GET /health
```

## 💡 Usage Examples

### Python Examples

```python
import requests

# Single profile (POST)
response = requests.post("http://localhost:8000/profile",
                        json={"email": "user@example.com"})

# Batch processing
response = requests.post("http://localhost:8000/profiles/batch",
                        json={
                            "emails": ["user1@example.com", "user2@example.com"],
                            "delay_seconds": 2
                        })
```

### cURL Examples

```bash
# Single profile
curl -X POST "http://localhost:8000/profile" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}'

# Batch processing
curl -X POST "http://localhost:8000/profiles/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "emails": ["user1@example.com", "user2@example.com"],
    "delay_seconds": 2
  }'
```

## 🔧 Advanced Features

### Automatic Token Management

The system automatically:

- Loads tokens from `token.txt` on startup
- Monitors token expiration (checks every 2 minutes)
- Refreshes tokens 15 minutes before expiry
- Deletes expired tokens and replaces with fresh ones
- Falls back to browser session if needed

### Enhanced Batch Processing

Includes all features from your JavaScript implementation:

- Progress tracking with percentages
- Configurable delays between requests
- Long breaks every N profiles
- Individual file saving option
- Detailed statistics and timing
- Error handling with continue/stop options

## 📁 File Structure

```
proxy-outlook/
├── api_server.py           # FastAPI server with all endpoints
├── token_manager.py        # NEW: Enhanced token management
├── persistent_session.py   # Browser session management
├── outlook.py             # Core Outlook automation
├── launch_complete_system.py # System orchestrator
├── test_api.py            # NEW: API testing suite
├── usage_examples.py      # NEW: Usage examples
├── token.txt             # Token storage (auto-managed)
└── temp/                 # Downloaded profiles
```

## 🔄 Token Management Flow

1. **Startup**: Load token from `token.txt`
2. **Validation**: Check if token is valid (not expired)
3. **Auto-Refresh**: Monitor expiration and refresh proactively
4. **File Management**: Always save fresh tokens to `token.txt`
5. **Cleanup**: Delete expired tokens automatically

## 🧪 Testing

```bash
# Run comprehensive API tests
uv run test_api.py

# Run usage examples
uv run usage_examples.py

# Test individual components
uv run token_manager.py
```

## 📊 Monitoring

Check system status:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/token/status
```

The API provides detailed status information including:

- Session health
- Token validity and expiration
- Auto-refresh status
- Processing statistics
