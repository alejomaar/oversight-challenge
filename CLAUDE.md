# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Knowledge Base AI Agent**: A serverless RAG (Retrieval-Augmented Generation) chatbot on AWS. Users upload documents, the system embeds them, stores in FAISS, and answers questions using AWS Bedrock (Claude 3.5 Sonnet).

**Architecture Principle**: Serverless + low cost > performance. Simplicity matters most. Make it work matters more than complexity. No try/except blocks unless necessary—let errors surface naturally.

## Core Stack

- **Backend**: FastAPI + async Python, deployed as AWS Lambda with Mangum
- **Storage**: Local filesystem (`Path` from pathlib, no os module)
- **Vectors**: FAISS (in-process, no external DB)
- **LLM**: AWS Bedrock (Claude 3.5 Sonnet)
- **Embeddings**: Bedrock (same as LLM)
- **Frontend**: Next.js (separate deployment)
- **Infrastructure**: AWS CDK (Python) for stack definitions

## Repo Structure (Backend Focus)

```
backend/
├── app.py                    # FastAPI entry point
├── core/config.py            # Settings from env vars
├── api/routes/
│   ├── upload.py             # POST /api/upload/ → save to filesystem
│   ├── files.py              # GET /api/files/ → list, GET /{id}, DELETE
│   ├── query.py              # POST /api/query/ → retrieve + generate answer
│   └── health.py             # GET /api/health/
├── rag/
│   ├── processor.py           # Load & split documents
│   ├── embedder.py            # Generate embeddings via Bedrock
│   ├── retriever.py           # FAISS vector search + BM25 keyword matching
│   └── generator.py           # Answer generation via Bedrock
└── models/
    └── file.py               # Pydantic schemas
```

## Key Patterns & Constraints

### File Operations
- Use `pathlib.Path` everywhere
- No `os.path` or `os` module
- Files saved to `settings.UPLOAD_DIR` (configured in `.env`)
- List files via `Path.iterdir()`, retrieve metadata from `Path.stat()`

### Configuration
- All settings in `backend/core/config.py` via `Settings` (pydantic-settings)
- Loads from `.env` file; environment variables override
- Key vars: `UPLOAD_DIR`, `S3_BUCKET_NAME` (for reference only), `BEDROCK_MODEL_ID`, `VECTOR_STORE_PATH`

### No Database Dependencies
- **Not MongoDB**: Metadata lives in files (filename, size, type, timestamp from filesystem)
- **Not S3**: Files stored locally; `s3_key` field is just the filename
- **FAISS**: Vector index cached to disk in `settings.VECTOR_STORE_PATH`

### Error Handling
- Functions return data or raise `HTTPException` naturally
- No try/catch blocks wrapping entire functions
- Use specific exceptions at boundaries (e.g., file not found → 404)

## Common Commands

### Backend Development
```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Local dev server (reload on changes)
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Test endpoint (after uploading a file via UI)
curl http://localhost:8000/api/files/

# Run health check
curl http://localhost:8000/api/health/
```

### Deploying to AWS
```bash
cd infrastructure

# Install CDK dependencies
pip install -r requirements.txt
npm install -g aws-cdk

# Deploy (requires AWS credentials configured)
cdk deploy FrontendStack --require-approval=never
cdk deploy BackendStack --require-approval=never

# View logs
cdk logs BackendStack
```

### Testing Endpoints
Use `test_upload_and_list.py` (existing) to invoke Lambda and test upload/list flows.

## Workflow: Adding a New Feature

1. **Endpoint logic**: Add/modify route in `backend/api/routes/*.py`
2. **Data model**: Update `backend/models/file.py` if response shape changes
3. **RAG pipeline**: Modify `backend/rag/*.py` if retrieval/generation logic changes
4. **Config**: Add new settings to `backend/core/config.py` if needed
5. **Test locally**: `uvicorn app:app --reload`, then use curl or Postman
6. **Deploy**: `cdk deploy` from infrastructure/ directory

## Deployment: Lambda + API Gateway

- FastAPI app wrapped by Mangum (ASGI → Lambda event handler)
- CloudFormation stacks in `backend/infrastructure/`
- Each request: API Gateway → Lambda → FastAPI route
- Uploads stay in `/tmp/` (ephemeral) during request; persisted to EBS mount or S3 between requests
- Current pattern: filesystem (`Path`) for simplicity

## Environment Variables (Backend)

```env
ENVIRONMENT=production
DEBUG=False
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
AWS_REGION=us-east-1
UPLOAD_DIR=/tmp/uploads
VECTOR_STORE_PATH=/tmp/vectorstore
MAX_FILE_SIZE=52428800  # 50MB
ALLOWED_EXTENSIONS=.pdf,.docx,.doc,.txt
```

## Gotchas & Decision Log

- **No MongoDB**: Simplified to filesystem + FAISS; metadata stored as file attributes
- **No S3 client**: Files saved locally; `s3_key` is just filename for compatibility with older code
- **Path over os**: All file ops use `pathlib.Path` (more explicit, no string concatenation)
- **Bedrock for both embeddings & generation**: Consolidates vendor, simplifies keys
- **Async endpoints**: FastAPI defaults, enables Lambda concurrency
- **FAISS persisted**: Rebuilt on Lambda cold start; in production, cache or store index in EBS/S3

## Frontend Integration

- Next.js at `frontend/` (separate stack in CDK)
- API calls to `{BACKEND_URL}/api/upload`, `/api/query`, `/api/files/`
- CORS enabled for `localhost:3000`, `localhost:3001` (dev) + deployed domains (prod)
- Environment: `NEXT_PUBLIC_API_URL` set at build time

## Testing & Validation

- **Postman/curl**: Quick endpoint smoke tests
- **Python scripts**: `test_upload_and_list.py` for Lambda integration
- **Local uvicorn**: Full FastAPI testing before deploy
- No unit test suite yet; focus on integration via Lambda invoke

---

**Last Updated**: 2026-08-16  
**Current Status**: Serverless MVP with filesystem storage, FAISS vectors, Bedrock LLM
