# Token Rotation System Guide

## Overview

The token rotation system efficiently distributes API requests across multiple DynamoDB tokens, preventing individual token exhaustion and maximizing throughput.

## How It Works

### 🔄 Smart Token Rotation

- **Reuse tokens**: Each token is used for multiple requests before switching
- **Automatic rotation**: When a token reaches its usage limit, the system automatically switches to the next available token
- **Round-robin distribution**: Tokens are cycled through to ensure even usage distribution
- **Fallback protection**: If no DynamoDB tokens are available, falls back to token.txt

### 📊 Token Usage Tracking

- **Daily limits**: Respects the 500 requests/day limit per token
- **Session tracking**: Tracks how many requests each token has made in the current rotation cycle
- **Priority-based selection**: Prefers tokens with lower usage and fewer errors

## Configuration

### Job-Level Configuration

```json
{
  "emails": ["email1@domain.com", "email2@domain.com"],
  "priority": "HIGH",
  "config": {
    "delay_seconds": 2,
    "save_to_dynamodb": true,
    "requests_per_token": 15
  }
}
```

### Configuration Options

| Parameter            | Default | Range   | Description                                  |
| -------------------- | ------- | ------- | -------------------------------------------- |
| `requests_per_token` | 15      | 1-50    | Number of requests per token before rotation |
| `delay_seconds`      | 2       | 0.5-10  | Delay between individual email requests      |
| `save_to_dynamodb`   | true    | boolean | Whether to save profiles to DynamoDB         |

## Usage Examples

### 1. Default Rotation (15 requests per token)

```bash
curl -X POST http://localhost:8000/jobs/create-batch \
  -H "Content-Type: application/json" \
  -d '{
    "emails": ["user1@domain.com", "user2@domain.com"],
    "priority": "NORMAL",
    "config": {
      "save_to_dynamodb": true
    }
  }'
```

### 2. Aggressive Rotation (5 requests per token)

```bash
curl -X POST http://localhost:8000/jobs/create-batch \
  -H "Content-Type: application/json" \
  -d '{
    "emails": ["user1@domain.com", "user2@domain.com"],
    "priority": "HIGH",
    "config": {
      "requests_per_token": 5,
      "delay_seconds": 1
    }
  }'
```

### 3. Conservative Rotation (25 requests per token)

```bash
curl -X POST http://localhost:8000/jobs/create-batch \
  -H "Content-Type: application/json" \
  -d '{
    "emails": ["user1@domain.com", "user2@domain.com"],
    "priority": "LOW",
    "config": {
      "requests_per_token": 25,
      "delay_seconds": 3
    }
  }'
```

## Log Output Examples

### Token Rotation in Action

```
🔍 Requesting token for user1@domain.com (attempt 1/50)
🆕 Switching to token abc12345 (daily usage: 15/500)
📧 Processing 1/50: user1@domain.com
✅ user1@domain.com: Profile fetched successfully

🔍 Requesting token for user2@domain.com (attempt 2/50)
🔄 Continuing with token abc12345 (usage: 2/15)
📧 Processing 2/50: user2@domain.com
✅ user2@domain.com: Profile fetched successfully

...

🔍 Requesting token for user16@domain.com (attempt 16/50)
🔃 Token abc12345 reached rotation limit (15), switching...
🆕 Switching to token def67890 (daily usage: 8/500)
📧 Processing 16/50: user16@domain.com
✅ user16@domain.com: Profile fetched successfully
```

### Job Statistics with Token Info

```
✅ Completed job f32ae973-816b-4f6b-bf3f-3fc811d1665b (45 successful, 5 failed)
   Error breakdown:
   🔒 user_restricted: 3
   🚫 access_denied: 2

🔄 Active jobs: f32ae973(current_token: abc12345..., usage: 12/15)
```

## API Response Example

### Job Creation Response

```json
{
  "success": true,
  "job_id": "f32ae973-816b-4f6b-bf3f-3fc811d1665b",
  "total_emails": 100,
  "priority": "HIGH",
  "estimated_capacity_used": 100,
  "available_capacity": 1206,
  "linkedin_profiles_auto_save": true,
  "token_rotation": {
    "requests_per_token": 15,
    "estimated_token_switches": 6,
    "description": "Each token will be used for 15 requests before rotating to the next"
  },
  "message": "Batch job created and queued for processing."
}
```

### Job Status with Token Info

```json
{
  "job_id": "f32ae973-816b-4f6b-bf3f-3fc811d1665b",
  "status": "processing",
  "progress_percentage": 34.5,
  "current_token_id": "abc12345...",
  "token_requests_made": 12,
  "requests_per_token": 15
}
```

## Best Practices

### 1. **Choose Appropriate Rotation Frequency**

- **High frequency (5-10)**: Better distribution, more switching overhead
- **Medium frequency (15-20)**: Balanced approach (recommended)
- **Low frequency (25-35)**: Fewer switches, higher token utilization

### 2. **Consider Your Token Pool Size**

- **Few tokens (1-3)**: Use higher `requests_per_token` (20-30)
- **Many tokens (5+)**: Use lower `requests_per_token` (10-15)

### 3. **Monitor Token Health**

```bash
# Check token status
curl http://localhost:8000/tokens/status

# Check system health
curl http://localhost:8000/system/health
```

### 4. **Error Handling**

- User restriction errors don't affect token rotation
- Only genuine token errors trigger token switches
- Failed tokens are automatically excluded from rotation

## Troubleshooting

### Issue: All tokens exhausted quickly

**Solution**: Increase `requests_per_token` or add more tokens to DynamoDB

### Issue: Uneven token distribution

**Solution**: Decrease `requests_per_token` to force more frequent rotation

### Issue: Too many token switches

**Solution**: Increase `requests_per_token` for fewer but longer token usage periods

## Advanced Features

### 1. **Fallback Protection**

If DynamoDB tokens are unavailable, the system automatically falls back to `token.txt`

### 2. **Error Classification**

Different error types are handled differently:

- 🔒 User restrictions: No token penalty
- 🚫 Access denied: No token penalty
- 🛡️ Header injection: No token penalty
- ❌ Token errors: Triggers token rotation

### 3. **Dynamic Configuration**

Each job can have its own rotation settings, allowing fine-tuned control per batch.

## Monitoring Commands

```bash
# Check current job with token info
curl http://localhost:8000/jobs/{job_id}

# View system metrics
curl http://localhost:8000/system/metrics

# Get detailed token status
curl http://localhost:8000/tokens/status
```


