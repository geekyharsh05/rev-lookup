# Production Deployment Guide

## 🚀 Quick Deployment

The Dockerfile has been optimized for production deployment with the following features:

### ✅ What's Included

- **Multi-stage build** for optimized image size
- **Non-root user** for enhanced security (uid:1000, gid:1000)
- **Chrome/Chromium** with all necessary dependencies for web scraping
- **Health checks** built-in for container orchestration
- **Proper logging** and error handling
- **Environment variable configuration**
- **Optimized layer caching** for faster builds

### 🔧 Environment Variables

Create a `.env` file with these required variables:

```bash
# Application Settings
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Chrome/Selenium Settings (pre-configured for Docker)
CHROME_BIN=/usr/bin/chromium
CHROMEDRIVER=/usr/bin/chromedriver
CHROME_OPTS=--headless --no-sandbox --disable-dev-shm-usage --disable-gpu --disable-web-security --allow-running-insecure-content
DISPLAY=:99

# AWS Configuration for DynamoDB
AWS_ACCESS_KEY_ID=your_aws_access_key_here
AWS_SECRET_ACCESS_KEY=your_aws_secret_key_here
AWS_REGION=us-east-1
DYNAMODB_TABLE_NAME=linkedin_profiles

# Session Management
SESSION_TIMEOUT=3600
TOKEN_REFRESH_INTERVAL=1800
AUTO_REFRESH_ENABLED=true

# Security Settings
ALLOWED_ORIGINS=*
CORS_ENABLED=true

# Performance Settings
MAX_CONCURRENT_REQUESTS=10
REQUEST_TIMEOUT=30
BATCH_SIZE_LIMIT=1000
```

### 🐳 Docker Commands

#### Build the Image

```bash
docker build -t outlook-linkedin-api .
```

#### Run Single Container

```bash
docker run -d \
  --name outlook-api \
  --env-file .env \
  -p 8000:8000 \
  -v $(pwd)/logs:/var/log/api \
  --restart unless-stopped \
  outlook-linkedin-api
```

#### Using Docker Compose (Recommended)

```bash
# Start the full stack (API + Caddy reverse proxy)
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

### 🏗️ Production Architecture

The setup includes:

1. **API Container**: Your LinkedIn extraction service
2. **Caddy Reverse Proxy**: Handles SSL, compression, and routing
3. **Health Monitoring**: Built-in health checks and logging

### 📊 Monitoring

#### Health Check Endpoint

```bash
curl http://localhost:8000/health
```

#### Container Health Status

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

#### Application Logs

```bash
# Follow logs in real-time
docker logs -f outlook-api

# Or using compose
docker-compose logs -f api
```

### 🔐 Security Features

- **Non-root user**: Container runs as user 1000:1000
- **Read-only filesystem** where possible
- **Minimal attack surface**: Only necessary packages installed
- **Environment variable** based configuration
- **CORS configuration** for API security

### 🚀 Cloud Deployment

#### AWS ECS

```bash
# Build and push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ECR_URI
docker tag outlook-linkedin-api:latest YOUR_ECR_URI/outlook-linkedin-api:latest
docker push YOUR_ECR_URI/outlook-linkedin-api:latest
```

#### Google Cloud Run

```bash
# Build and deploy
gcloud builds submit --tag gcr.io/YOUR_PROJECT/outlook-linkedin-api
gcloud run deploy --image gcr.io/YOUR_PROJECT/outlook-linkedin-api --platform managed
```

#### DigitalOcean App Platform

- Upload your repository
- Set environment variables in the control panel
- Deploy with auto-scaling

### 🔧 Performance Tuning

#### For High Load

```bash
# Run with multiple workers (in compose.yml)
CMD ["uv", "run", "uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

#### Memory Optimization

```bash
# Add memory limits to compose.yml
deploy:
  resources:
    limits:
      memory: 2G
    reservations:
      memory: 1G
```

### 🐛 Troubleshooting

#### Chrome Issues

```bash
# Check Chrome installation
docker exec -it outlook-api chromium --version

# Test headless mode
docker exec -it outlook-api chromium --headless --dump-dom https://google.com
```

#### Permission Issues

```bash
# Fix file permissions
sudo chown -R 1000:1000 ./logs ./temp
```

#### Memory Issues

```bash
# Increase shared memory for Chrome
docker run --shm-size=2g ...
```

### 📈 Scaling

For production workloads:

1. **Horizontal Scaling**: Run multiple container instances behind a load balancer
2. **Vertical Scaling**: Increase memory/CPU limits
3. **Database**: Use external DynamoDB for session sharing
4. **Caching**: Implement Redis for token caching
5. **Queue System**: Use SQS/RabbitMQ for batch processing

### 🔄 Updates

```bash
# Rolling update with zero downtime
docker-compose pull
docker-compose up -d --no-deps api
```

This Dockerfile is ready for production deployment on any container platform! 🎉
