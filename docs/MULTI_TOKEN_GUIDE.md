# Multi-Token Management Guide

This guide explains how to add multiple Bearer tokens at once by pasting them into the `token.txt` file.

## 🎯 Overview

The system now supports adding multiple Bearer tokens from the `token.txt` file in various formats:

1. **One token per line** (recommended)
2. **Comma-separated tokens**
3. **Space-separated tokens** (where "Bearer" acts as separator)
4. **Mixed formats**

## 📁 Supported Formats

### Format 1: One Token Per Line (Recommended)

```
Bearer EwAIA61DAAAUGik12345abcdefghijklmnopqrstuvwxyz...
Bearer EwAIA61DAAAUGik67890abcdefghijklmnopqrstuvwxyz...
Bearer EwAIA61DAAAUGikABCDEFabcdefghijklmnopqrstuvwxyz...
```

### Format 2: Comma-Separated

```
Bearer EwAIA61DAAAUGik12345..., Bearer EwAIA61DAAAUGik67890..., Bearer EwAIA61DAAAUGikABCDEF...
```

### Format 3: Space-Separated (Auto-detected)

```
Bearer EwAIA61DAAAUGik12345... Bearer EwAIA61DAAAUGik67890... Bearer EwAIA61DAAAUGikABCDEF...
```

### Format 4: Without "Bearer" Prefix

The system automatically adds the "Bearer " prefix if it's missing:

```
EwAIA61DAAAUGik12345abcdefghijklmnopqrstuvwxyz...
EwAIA61DAAAUGik67890abcdefghijklmnopqrstuvwxyz...
EwAIA61DAAAUGikABCDEFabcdefghijklmnopqrstuvwxyz...
```

## 🚀 How to Use

### Method 1: Command Line Utility

1. **Add your tokens to `token.txt`** using any of the supported formats above
2. **Run the utility:**
   ```bash
   python multi_token_utility.py --add
   ```
3. **Check status:**
   ```bash
   python multi_token_utility.py --status
   ```

### Method 2: API Endpoint

1. **Add your tokens to `token.txt`**
2. **Call the API endpoint:**
   ```bash
   curl -X POST http://localhost:8000/tokens/add-multiple-from-file
   ```

### Method 3: Using Custom File

If you want to use a different file instead of `token.txt`:

```bash
# Command line
python multi_token_utility.py --add --file my_tokens.txt

# API (file must be named token.txt for the endpoint)
```

## 📋 Step-by-Step Instructions

### Step 1: Prepare Your Tokens

1. **Copy your Bearer tokens** from your source (browser dev tools, API responses, etc.)
2. **Open `token.txt`** in any text editor
3. **Paste the tokens** using one of these methods:

   **Option A: One per line (easiest)**

   ```
   Bearer EwAIA61DAAAUGik12345...
   Bearer EwAIA61DAAAUGik67890...
   Bearer EwAIA61DAAAUGikABCDEF...
   ```

   **Option B: Copy-paste multiple tokens with commas**

   ```
   Bearer EwAIA61DAAAUGik12345..., Bearer EwAIA61DAAAUGik67890..., Bearer EwAIA61DAAAUGikABCDEF...
   ```

   **Option C: Just paste tokens (system adds Bearer prefix)**

   ```
   EwAIA61DAAAUGik12345...
   EwAIA61DAAAUGik67890...
   EwAIA61DAAAUGikABCDEF...
   ```

### Step 2: Add Tokens to System

**Using Command Line:**

```bash
python multi_token_utility.py --add
```

**Using API:**

```bash
curl -X POST http://localhost:8000/tokens/add-multiple-from-file
```

### Step 3: Verify Results

The system will show you:

- ✅ Successfully added tokens
- ❌ Failed tokens (duplicates or invalid)
- 📊 Summary statistics

**Example Output:**

```
📄 Found 3 tokens in token.txt
✅ Token 1/3 added: Bearer EwAIA61DAAAUGik12345...
✅ Token 2/3 added: Bearer EwAIA61DAAAUGik67890...
❌ Token 3/3 failed: Bearer EwAIA61DAAAUGikABCDEF... - Failed to add to DynamoDB (may be duplicate or invalid)

📊 Results:
=====================================
Success: True
Message: Added 2/3 tokens successfully
Tokens Added: 2
Tokens Failed: 1
Total Processed: 3
```

## 🔧 Advanced Usage

### Create Sample File for Testing

```bash
python multi_token_utility.py --create-sample
```

This creates `sample_tokens.txt` with dummy tokens for testing.

### Check Current Token Status

```bash
python multi_token_utility.py --status
```

Shows all tokens currently in the system with their status.

### Use Different File

```bash
python multi_token_utility.py --add --file my_custom_tokens.txt
```

## 🛠️ API Endpoints

### Add Multiple Tokens from File

```http
POST /tokens/add-multiple-from-file
```

**Response:**

```json
{
  "success": true,
  "message": "Added 2/3 tokens successfully",
  "tokens_added": 2,
  "tokens_failed": 1,
  "total_tokens": 3,
  "details": [
    {
      "token_number": 1,
      "status": "success",
      "preview": "Bearer EwAIA61DAAAUGik12345..."
    },
    {
      "token_number": 2,
      "status": "success",
      "preview": "Bearer EwAIA61DAAAUGik67890..."
    },
    {
      "token_number": 3,
      "status": "failed",
      "preview": "Bearer EwAIA61DAAAUGikABCDEF...",
      "error": "Failed to add to DynamoDB (may be duplicate or invalid)"
    }
  ]
}
```

### Add Single Token (Original)

```http
POST /tokens/add-from-file
```

### Check Token Status

```http
GET /tokens/status
```

## ⚠️ Important Notes

1. **Token Validation**: Tokens must be at least 50 characters long to be considered valid
2. **Duplicates**: The system will reject duplicate tokens
3. **Format Flexibility**: The parser is smart and handles mixed formats automatically
4. **Bearer Prefix**: Automatically added if missing
5. **Error Handling**: Failed tokens are reported with specific error messages
6. **File Safety**: Original `token.txt` is not modified during processing

## 🐛 Troubleshooting

### "No valid tokens found in file"

- Check that tokens are at least 50 characters long
- Ensure tokens are properly formatted
- Try different separation methods (lines, commas)

### "Token already exists" errors

- These are normal for duplicate tokens
- Check existing tokens with `--status` flag

### "File not found" error

- Ensure `token.txt` exists in the current directory
- Or specify custom file with `--file` parameter

## 📝 Examples

### Example 1: Quick Add

```bash
# 1. Paste tokens in token.txt (one per line)
# 2. Run this command:
python multi_token_utility.py --add
```

### Example 2: Check Status First

```bash
# Check what's currently in the system
python multi_token_utility.py --status

# Add new tokens
python multi_token_utility.py --add

# Check updated status
python multi_token_utility.py --status
```

### Example 3: Using API

```bash
# Add tokens via API
curl -X POST http://localhost:8000/tokens/add-multiple-from-file

# Check status via API
curl -X GET http://localhost:8000/tokens/status
```

This system makes it easy to manage multiple Bearer tokens efficiently, whether you're adding them one at a time or in bulk!

