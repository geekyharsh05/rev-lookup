# 📊 LinkedIn Profiles DynamoDB Integration

## 🎯 **Overview**

The batch processing system now automatically saves LinkedIn profile results to the `linkedin_profiles` DynamoDB table during processing and provides endpoints for manual saving.

## 🔧 **Integration Features**

### ✅ **Automatic Saving**

- **Real-time**: Profiles saved immediately when fetched
- **Each successful API call** automatically saves to `linkedin_profiles` table
- **Error handling**: Continues processing even if save fails
- **Status tracking**: Each result includes `saved_to_linkedin_profiles` flag

### ✅ **Manual Batch Saving**

- **Post-processing**: Save all job results manually after completion
- **Retry mechanism**: Re-save failed profiles
- **Bulk operations**: Efficient batch saving to DynamoDB

### ✅ **Enhanced Endpoints**

- **Job creation** shows auto-save status
- **Results endpoint** includes LinkedIn save statistics
- **Manual save endpoint** for completed jobs

## 📡 **API Endpoints**

### 🔄 **Automatic Integration**

When you create a batch job, profiles are automatically saved:

```bash
curl -X POST "http://localhost:8000/jobs/create-batch" \
  -H "Content-Type: application/json" \
  -d '{
    "emails": ["john@company.com", "jane@company.com"],
    "priority": "HIGH"
  }'
```

**Response includes:**

```json
{
  "success": true,
  "job_id": "uuid-here",
  "linkedin_profiles_auto_save": true,
  "message": "Batch job created and queued for processing. LinkedIn profiles will be automatically saved to DynamoDB."
}
```

### 📊 **Enhanced Results**

```bash
curl "http://localhost:8000/jobs/{job_id}/results"
```

**Response includes LinkedIn save stats:**

```json
{
  "job_id": "uuid-here",
  "status": "completed",
  "results": [
    {
      "email": "john@company.com",
      "success": true,
      "data": {...},
      "saved_to_linkedin_profiles": true
    }
  ],
  "linkedin_profiles_stats": {
    "total_profiles_fetched": 2,
    "saved_to_linkedin_profiles": 2,
    "failed_to_save_linkedin": 0,
    "linkedin_db_available": true
  }
}
```

### 💾 **Manual Batch Save**

For completed jobs, manually save all results:

```bash
curl -X POST "http://localhost:8000/jobs/{job_id}/save-to-linkedin-profiles"
```

**Response:**

```json
{
  "success": true,
  "message": "Batch save completed",
  "job_id": "uuid-here",
  "total_results": 2,
  "saved_count": 2,
  "failed_count": 0,
  "linkedin_profiles_table": "linkedin_profiles"
}
```

## 🗃️ **DynamoDB Table Structure**

The `linkedin_profiles` table stores:

```json
{
  "email": "john@company.com",           // Partition key
  "timestamp": "2024-01-15T10:30:00Z",   // Sort key
  "success": true,
  "profile_data": {...},                 // LinkedIn API response
  "saved_at": "2024-01-15T10:30:00Z",
  "token_used": "token_abc123",
  "email_number": 1
}
```

## 🔄 **Workflow Examples**

### **Example 1: Automatic Processing**

```bash
# 1. Create batch job
RESPONSE=$(curl -s -X POST "http://localhost:8000/jobs/create-batch" \
  -H "Content-Type: application/json" \
  -d '{"emails": ["test1@example.com", "test2@example.com"]}')

JOB_ID=$(echo $RESPONSE | jq -r '.job_id')

# 2. Monitor progress
curl "http://localhost:8000/jobs/$JOB_ID"

# 3. Check results (profiles automatically saved)
curl "http://localhost:8000/jobs/$JOB_ID/results" | jq '.linkedin_profiles_stats'
```

### **Example 2: Manual Save for Failed Auto-saves**

```bash
# If auto-save failed for some profiles, manually save them
curl -X POST "http://localhost:8000/jobs/$JOB_ID/save-to-linkedin-profiles"
```

### **Example 3: System Status Check**

```bash
# Check if LinkedIn profiles integration is working
curl "http://localhost:8000/system/info" | jq '.linkedin_profiles_integration'
```

## ⚙️ **Configuration**

### **Environment Variables**

```bash
# Same AWS credentials used for both token storage and LinkedIn profiles
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1

# Table names (optional, defaults provided)
DYNAMODB_TABLE_NAME=linkedin_profiles  # For profiles
BEARER_TOKENS_TABLE=bearer_tokens       # For tokens
```

### **Table Management**

The system automatically:

- ✅ **Creates tables** if they don't exist
- ✅ **Handles permissions** and billing
- ✅ **Manages TTL** for token expiry (22 hours)
- ✅ **Replaces existing profiles** with same email

## 🚨 **Error Handling**

### **Auto-save Failures**

- **Continue processing**: Job continues even if LinkedIn save fails
- **Error tracking**: Failed saves logged in results
- **Manual retry**: Use manual save endpoint for retry

### **Manual Save Failures**

- **Detailed errors**: Specific error messages per profile
- **Partial success**: Shows count of successful vs failed saves
- **Error limits**: Only shows first 10 errors to prevent overflow

### **DynamoDB Unavailable**

- **Graceful degradation**: Processing continues without save
- **Clear messaging**: Status endpoints show availability
- **Manual recovery**: Can save results later when DB is available

## 📊 **Monitoring**

### **Real-time Status**

```bash
# Check overall system health
curl "http://localhost:8000/system/health" | jq '.components'

# Check active jobs with save status
curl "http://localhost:8000/jobs/active" | jq '.[].linkedin_profiles_stats'

# Check service metrics
curl "http://localhost:8000/system/metrics"
```

### **LinkedIn Profile Statistics**

Each job result includes:

- `total_profiles_fetched`: Successful LinkedIn API calls
- `saved_to_linkedin_profiles`: Successfully saved to DynamoDB
- `failed_to_save_linkedin`: Failed DynamoDB saves
- `linkedin_db_available`: DynamoDB availability status

## 🎯 **Best Practices**

### **For Large Batches**

1. **Monitor save rates**: Check `linkedin_profiles_stats` regularly
2. **Handle partial failures**: Use manual save for failed auto-saves
3. **Verify AWS limits**: Ensure DynamoDB capacity for write volume

### **For Production**

1. **Set up monitoring**: CloudWatch alarms for DynamoDB errors
2. **Backup strategy**: Point-in-time recovery for both tables
3. **Error alerting**: Monitor failed save rates

### **For Development**

1. **Test with small batches**: Verify integration works
2. **Check credentials**: Ensure AWS permissions for both tables
3. **Monitor logs**: Watch for DynamoDB connection issues

## 🔧 **Troubleshooting**

### **Common Issues**

**1. Auto-save not working:**

```bash
# Check DynamoDB availability
curl "http://localhost:8000/system/info" | jq '.linkedin_profiles_integration'

# Verify AWS credentials
curl "http://localhost:8000/system/health" | jq '.components.linkedin_profiles'
```

**2. Manual save fails:**

```bash
# Check job completion status
curl "http://localhost:8000/jobs/{job_id}" | jq '.status'

# Verify results exist
curl "http://localhost:8000/jobs/{job_id}/results" | jq '.total_results'
```

**3. Permissions issues:**

- Ensure AWS credentials have `dynamodb:PutItem`, `dynamodb:UpdateItem`, `dynamodb:CreateTable` permissions
- Check IAM policies for both `bearer_tokens` and `linkedin_profiles` tables

This integration provides seamless LinkedIn profile storage with both automatic and manual saving options! 🚀
