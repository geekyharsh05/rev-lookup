# 🚀 Enhanced Batch Processing System Setup Guide

## 📋 System Overview

This enhanced system provides:

- **DynamoDB Token Storage**: Store up to 50+ Bearer tokens with automatic 22-hour expiry
- **In-Memory Job Queue**: Fast job processing with priority support
- **Heartbeat Polling Service**: Continuous monitoring and batch processing
- **Rate Limiting**: 500 requests/day per token with automatic rotation
- **Real-time Monitoring**: Live progress tracking and health checks

## 🛠️ Installation & Setup

### 1. **Environment Variables**

Create/update your `.env` file:

```bash
# AWS Credentials for DynamoDB
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1

# Outlook Credentials
OUTLOOK_EMAIL=your_email@outlook.com
OUTLOOK_PASSWORD=your_password

# DynamoDB Table (optional, defaults to 'bearer_tokens')
DYNAMODB_TABLE_NAME=bearer_tokens
```

### 2. **DynamoDB Table Structure**

The system automatically creates a table with:

- **Partition Key**: `token_id` (String)
- **TTL Field**: `ttl` (Number) - for automatic expiry
- **Attributes**:
  - `token` (String) - The Bearer token
  - `created_at` (String) - ISO timestamp
  - `expires_at` (String) - ISO timestamp
  - `daily_usage` (Number) - Current day usage count
  - `total_usage` (Number) - Lifetime usage count
  - `is_active` (Boolean) - Token status
  - `error_count` (Number) - Error tracking

### 3. **File Structure**

```
outlook-login/
├── dynamo_token_manager.py        # DynamoDB token management
├── memory_job_queue.py             # In-memory job queue
├── heartbeat_polling_service.py    # Polling service
├── enhanced_batch_api.py           # API endpoints
├── api_server.py                   # Main server (updated)
└── token.txt                       # Single token file (optional)
```

## 🎯 Quick Start

### 1. **Start the Server**

```bash
python api_server.py
```

The server will automatically:

- Initialize DynamoDB connection
- Create the tokens table if needed
- Start the heartbeat polling service
- Add token from `token.txt` if it exists

### 2. **Add Multiple Tokens**

```bash
# Add single token
curl -X POST "http://localhost:8000/tokens/add" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "Bearer EwAYBN2CBAAUVyZrnn9x...",
    "token_id": "token_001"
  }'

# Add multiple tokens
curl -X POST "http://localhost:8000/tokens/add-multiple" \
  -H "Content-Type: application/json" \
  -d '{
    "tokens": [
      "Bearer EwAYBN2CBAAUVyZrnn9x...",
      "Bearer EwBYBN3DCAAUWyZrnn8x...",
      "Bearer EwCYBN4EBAAUXyZrnn7x..."
    ]
  }'

# Add from token.txt file
curl -X POST "http://localhost:8000/tokens/add-from-file"
```

### 3. **Create Batch Jobs**

```bash
# Create a batch job
curl -X POST "http://localhost:8000/jobs/create-batch" \
  -H "Content-Type: application/json" \
  -d '{
    "emails": [
      "john.doe@company.com",
      "jane.smith@company.com",
      "bob.wilson@company.com"
    ],
    "priority": "HIGH",
    "config": {
      "delay_seconds": 2,
      "save_to_dynamodb": true
    }
  }'
```

### 4. **Monitor Progress**

```bash
# Check job status
curl "http://localhost:8000/jobs/{job_id}"

# Get active jobs
curl "http://localhost:8000/jobs/active"

# System health
curl "http://localhost:8000/system/health"

# Token status
curl "http://localhost:8000/tokens/status"
```

## 📡 API Endpoints

### 🔑 Token Management

| Method   | Endpoint                | Description           |
| -------- | ----------------------- | --------------------- |
| `POST`   | `/tokens/add`           | Add single token      |
| `POST`   | `/tokens/add-multiple`  | Add multiple tokens   |
| `POST`   | `/tokens/add-from-file` | Add from token.txt    |
| `GET`    | `/tokens/status`        | Get all tokens status |
| `DELETE` | `/tokens/{token_id}`    | Delete specific token |

### 📋 Job Management

| Method | Endpoint                 | Description               |
| ------ | ------------------------ | ------------------------- |
| `POST` | `/jobs/create-batch`     | Create batch job          |
| `GET`  | `/jobs/{job_id}`         | Get job details           |
| `GET`  | `/jobs/{job_id}/results` | Get job results           |
| `POST` | `/jobs/{job_id}/cancel`  | Cancel job                |
| `GET`  | `/jobs/active`           | Get active jobs           |
| `GET`  | `/jobs/pending`          | Get pending jobs          |
| `GET`  | `/jobs/recent`           | Get recent completed jobs |

### 🫀 Service Management

| Method | Endpoint          | Description             |
| ------ | ----------------- | ----------------------- |
| `POST` | `/service/start`  | Start heartbeat service |
| `POST` | `/service/stop`   | Stop heartbeat service  |
| `GET`  | `/service/status` | Get service status      |
| `POST` | `/service/config` | Update configuration    |

### 🏥 System Health

| Method | Endpoint          | Description         |
| ------ | ----------------- | ------------------- |
| `GET`  | `/system/health`  | Health check        |
| `GET`  | `/system/metrics` | Performance metrics |
| `GET`  | `/system/info`    | System information  |
| `POST` | `/system/cleanup` | Manual cleanup      |

## 🔧 Configuration

### Heartbeat Service Config

```python
config = {
    "polling_interval": 3,        # seconds between polls
    "max_concurrent_jobs": 5,     # max simultaneous jobs
    "delay_between_emails": 2.0,  # seconds between emails
    "max_errors_per_token": 5     # before token deactivation
}
```

### Job Priorities

- `URGENT` (4) - Highest priority
- `HIGH` (3) - High priority
- `NORMAL` (2) - Default priority
- `LOW` (1) - Lowest priority

## 📊 Monitoring & Analytics

### Real-time Status

```bash
# System overview
curl "http://localhost:8000/system/health" | jq '.'

# Token utilization
curl "http://localhost:8000/tokens/status" | jq '.usage_percentage'

# Active processing
curl "http://localhost:8000/jobs/active" | jq 'length'

# Queue size
curl "http://localhost:8000/jobs/queue/status" | jq '.status_breakdown'
```

### Health Monitoring

The system provides automatic health scoring:

- **Excellent (95-100)**: All systems optimal
- **Good (80-94)**: Minor issues
- **Fair (60-79)**: Some problems
- **Poor (<60)**: Significant issues

## 🚨 Troubleshooting

### Common Issues

1. **No Available Tokens**

   ```bash
   # Check token status
   curl "http://localhost:8000/tokens/status"

   # Add more tokens
   curl -X POST "http://localhost:8000/tokens/add-multiple" -d '{"tokens": [...]}'
   ```

2. **Jobs Stuck in Pending**

   ```bash
   # Check service status
   curl "http://localhost:8000/service/status"

   # Restart service if needed
   curl -X POST "http://localhost:8000/service/stop"
   curl -X POST "http://localhost:8000/service/start"
   ```

3. **High Error Rates**

   ```bash
   # Check token errors
   curl "http://localhost:8000/tokens/status" | jq '.token_details[] | select(.error_count > 0)'

   # Check recent job errors
   curl "http://localhost:8000/jobs/recent" | jq '.[] | select(.errors_count > 0)'
   ```

### Log Monitoring

Key log messages to watch:

- `✅ Added token X to DynamoDB`
- `🫀 Heartbeat loop started`
- `📧 Processing X/Y: email@domain.com`
- `❌ No available tokens`
- `⚠️ Token expires soon`

## 🎛️ Advanced Usage

### Batch Processing 1000s of Emails

```python
# Split large batches
emails = [...1000s of emails...]
batch_size = 100

for i in range(0, len(emails), batch_size):
    batch = emails[i:i + batch_size]

    response = requests.post("http://localhost:8000/jobs/create-batch", json={
        "emails": batch,
        "priority": "NORMAL",
        "config": {"delay_seconds": 1}
    })

    print(f"Created job: {response.json()['job_id']}")
```

### Token Rotation Strategy

```python
# Add tokens in batches throughout the day
def add_tokens_batch(tokens):
    response = requests.post("http://localhost:8000/tokens/add-multiple",
                           json={"tokens": tokens})
    return response.json()

# Monitor and add tokens as needed
def monitor_capacity():
    status = requests.get("http://localhost:8000/tokens/status").json()
    if status['available_capacity'] < 1000:
        # Add more tokens
        new_tokens = get_fresh_tokens()  # Your token source
        add_tokens_batch(new_tokens)
```

## 📈 Performance Optimization

### Recommended Settings for Scale

**For 10,000+ emails/day:**

```python
config = {
    "polling_interval": 2,
    "max_concurrent_jobs": 10,
    "delay_between_emails": 1.0,
    "max_errors_per_token": 3
}
```

**For 50+ tokens:**

- Set `max_concurrent_jobs` to 10-15
- Use `delay_between_emails` of 1.0-1.5 seconds
- Monitor token error rates closely
- Consider geographic token distribution

### DynamoDB Optimization

- Use **On-Demand billing** for variable workloads
- Enable **Point-in-time recovery** for production
- Set up **CloudWatch monitoring** for table metrics
- Consider **Global Tables** for multi-region setup

## 🔒 Security Considerations

1. **Token Security**

   - Store tokens with 22-hour TTL
   - Monitor for token abuse
   - Use separate AWS account for production

2. **API Security**

   - Add authentication middleware
   - Implement rate limiting
   - Use HTTPS in production

3. **Data Protection**
   - Encrypt DynamoDB table
   - Use VPC for secure communication
   - Regular security audits

## 📞 Support

For issues or questions:

1. Check system health: `GET /system/health`
2. Review logs for error patterns
3. Monitor token utilization
4. Verify DynamoDB connectivity

Remember: The system automatically handles token rotation, rate limiting, and error recovery. Focus on monitoring and adding tokens as needed!
