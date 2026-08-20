# 📚 Knowledge Base AI Agent — AWS-Native

A **Knowledge Base AI Agent** that lets you upload documents (PDF, Word, or plain text), builds a
searchable knowledge base out of them, and answers questions about their contents — with the
sources it used and how confident it is in the answer, so nothing is ever just made up. It runs
entirely on AWS, and a small local Streamlit app is the chat window you talk to it through.

## ✨ Key Features

- 📄 **Upload almost anything** — PDF, Word, or plain text. Uploading the same file twice is caught automatically, so the knowledge base never fills up with duplicates.
- 🔍 **Finds the right passage two ways at once** — by meaning, so a paraphrased question still works, and by exact wording, so names, codes, and quoted phrases aren't missed.
- 🤖 **Searches like a person would** — it decides how much digging a question needs and reads the full passage around anything it finds, instead of grabbing a fixed number of disconnected snippets.
- 📊 **Shows its work** — every answer comes with the exact passages it was built from, so it can be checked, not just trusted.
- 🎯 **Says how sure it is** — a confidence score with a breakdown of what drove it, not one number to take on faith.
- 🔐 **Locked behind an access token** — no one can call the API without one.
- 🏗️ **Deploys and tears down with one command** — the whole AWS setup is defined as code, nothing clicked together by hand.
- 💸 **Costs next to nothing when no one's using it** — no servers running around the clock.

---

## 🧭 How It Works

The system has two paths: **ingestion**, which turns an uploaded file into searchable records, and
**query**, which answers a question from those records.

### Ingestion

```
Your file ──▶ [1] saved as-is to S3 ──▶ [2] text extracted ──▶ [3] split into chunks
                                                                       │
                                                                       ▼
                                              [5] chunks + embeddings saved to Postgres
                                                                       ▲
                                                                       │
                                              [4] each chunk sent to an AI model
                                                  that returns its embedding
```

1. The original file is stored untouched in S3, so the source remains recoverable.
2. Text is extracted — `pypdf` for PDF, `python-docx` for Word, direct decode for `.txt`.
3. The text is split into ~1000-character chunks with 200 characters of overlap. Each chunk records
   its start and end offset in the original text, which is what later allows a search hit to be
   expanded back into its surrounding context.
4. Each chunk is embedded by Bedrock's Titan model, producing a 1024-dimension vector.
5. Chunk text, offsets, and embedding are written to Postgres in a single transaction.

Ahead of all of it, the file's bytes are hashed with SHA-256. If that hash already exists, the
upload is rejected with `409 Conflict` rather than producing a duplicate set of chunks.

### Query

A conventional RAG implementation embeds the question, retrieves a fixed number of nearest chunks,
and passes them to the model in one prompt. This project instead exposes retrieval as a set of
tools and lets the model drive:

```
Your question
     │
     ▼
┌──────────────────────────────────────────────────┐
│  The AI model looks at the question and picks     │◀────────────┐
│  which tool(s) to use — or decides it's ready     │             │
│  to answer                                        │             │
└───────────────────┬──────────────────────────────┘             │
                    │                                             │
     ┌──────────────┼──────────────┬────────────────┐            │
     ▼              ▼              ▼                ▼            │
 search by      search by      list what      read more of       │
 meaning        exact words    documents      a document ────────┘
                               exist          (results go back to the model)
                    │
                    ▼
        Final answer + the passages it used + a confidence score
```

The model receives the question, may request one or more tool calls, receives their results, and
then either requests further calls or produces the final answer. LangGraph manages that loop and
the state carried through it.

The justification for the added complexity is that a fixed pipeline applies identical retrieval
effort to every question, which is rarely appropriate:

- A narrow factual question — *"What is the refund window for enterprise customers?"* — is resolved
  by one targeted search and one expanded read. A fixed top-5 would contribute four passages of
  noise to the prompt.
- A comparative question — *"How does the escalation process in the support policy differ from the
  SLA?"* — requires several searches across multiple documents, each expanded before the comparison
  is sound.
- A question about the corpus itself — *"Which documents are available?"* — requires no retrieval at
  all.

`read_document` is the tool that most affects answer quality. A search hit is a chunk cut at an
arbitrary boundary, so it may begin mid-sentence or stop short of a qualifying clause that changes
its meaning. The prompt requires the agent to expand each hit to its complete paragraph or section
before answering.

---

## 🏗️ Architecture

```
┌─────────────────────────┐        HTTPS + x-api-key         ┌──────────────────────────────────────┐
│   Local Streamlit app    │ ────────────────────────────────▶ │        API Gateway (REST API)          │
│  (reviewer's machine)    │                                   │  API key + usage plan, CORS enabled    │
└─────────────────────────┘                                   └───────────────────┬────────────────────┘
                                                                                    │ Lambda proxy integration
                                                                                    ▼
                                                          ┌──────────────────────────────────────────┐
                                                          │   Lambda (Docker image, private subnet)    │
                                                          │   FastAPI app via Mangum                   │
                                                          │   /api/health  /api/upload  /api/files      │
                                                          │   /api/query  →  LangGraph ReAct agent      │
                                                          └───┬───────────────┬───────────────┬────────┘
                                                              │               │               │
                                              VPC interface   │   VPC gateway │   VPC interface│
                                              endpoint        ▼   endpoint    ▼   endpoint     ▼
                                          ┌─────────────┐ ┌─────────┐  ┌──────────────┐
                                          │   Bedrock    │ │   S3     │  │Secrets Manager│
                                          │ Titan Embed  │ │ raw file │  │  DB password  │
                                          │ + LLM (chat) │ │provenance│  │ (fetched once │
                                          └─────────────┘ └─────────┘  │ at cold start) │
                                                                        └──────────────┘
                                                              │
                                                              ▼
                                                   ┌───────────────────────┐
                                                   │  RDS Postgres 16       │
                                                   │  + pgvector + pg_trgm  │
                                                   │  document / chunk      │
                                                   │  tables (text, offsets,│
                                                   │  1024-dim embeddings)  │
                                                   └───────────────────────┘
```

### The components

- **API Gateway** — the managed HTTPS front door. Validates the API key and forwards to the Lambda;
  no web server to run or patch.
- **Lambda** — the API process, billed per request and per millisecond of execution, nothing while
  idle. The tradeoff is cold start: the first request after an idle period waits on container boot,
  a few seconds here given the image size.
- **Mangum** — adapts Lambda's event format to ASGI, so the same FastAPI app runs unchanged as a
  Lambda and as a local `uvicorn` server.
- **RDS Postgres** — the knowledge base itself. `pgvector` supplies the vector column type and
  similarity operators, keeping retrieval a SQL query rather than a second datastore to synchronize;
  `pg_trgm` backs fuzzy text matching.
- **S3** — original uploaded files only. Postgres is authoritative for everything the agent reads.
- **Bedrock** — managed model inference inside AWS: Titan for embeddings, a chat model for
  generation.
- **Secrets Manager** — holds the generated database password, read by the Lambda at cold start
  rather than passed in as an environment variable.

### Networking

The Lambda runs in private isolated subnets, which have no route to the internet. It still needs
Bedrock, S3, and Secrets Manager, and the conventional way to provide that is a NAT gateway —
which bills roughly $32/month regardless of traffic and would dominate the cost of this design.

VPC endpoints replace it, routing from inside the VPC directly to an AWS service. S3 uses a gateway
endpoint (free); Bedrock and Secrets Manager use interface endpoints (~$0.01/hour per availability
zone). Cheaper than NAT, and traffic never traverses the public internet.

The database is the deliberate exception: it sits in a public subnet so migrations and inspection
can be run from a developer machine, with its security group restricted to the single address in
`DEV_ACCESS_IP`.

---

## 🛠️ Tech Stack

| Layer | Choice | Why |
|---|---|---|
| API compute | AWS Lambda (Docker image via Mangum) | Pay-per-invocation, zero idle cost, fits FastAPI unchanged |
| API entry point | Amazon API Gateway (REST) | Managed auth (API key + usage plan) without writing an authorizer |
| Vector store | RDS Postgres + pgvector (HNSW index) | One database holds metadata, extracted text, and embeddings together — nothing else to run or keep in sync |
| Keyword search | Postgres `pg_trgm` / `~*` regex | Free — no separate search engine for a small corpus |
| Embeddings | Bedrock Titan `amazon.titan-embed-text-v2:0` | AWS-native, cheap, no data leaves AWS |
| LLM | Bedrock `openai.gpt-oss-20b-1:0` | AWS-hosted, pay-per-token, no data leaves AWS ([model choice explained below](#model-choice)) |
| Orchestration | LangGraph (ReAct-style single-node loop + `ToolNode`) | Lets the agent decide *how much* retrieval a question needs instead of a fixed pipeline |
| Storage | S3 (original files only) | Provenance only — Postgres is authoritative for content |
| IaC | AWS CDK (Python), one stack | Readable, no cross-account bootstrapping beyond default CDK assets |
| Frontend | Streamlit (thin HTTP client) | No retrieval/generation logic in the client — everything runs behind the API |

**HNSW** is the index type on the embedding column — an approximate nearest-neighbor structure
that avoids scanning every vector as the corpus grows, trading a small amount of recall for a large
speedup.

Two AWS-managed alternatives sit next to these choices worth naming. **Bedrock Knowledge Bases**
would have handled retrieval end-to-end, but it still needs a vector store underneath — either
OpenSearch Serverless or RDS pgvector — and with pgvector already doing the job, a hand-rolled
agent gives more control over blending semantic and keyword evidence and expanding a hit into its
full surrounding context, which a managed KB's fixed retrieve-then-generate flow doesn't expose.
**Bedrock AgentCore** would have hosted the agent itself, with managed session memory and tracing
— genuinely useful, but for a single agent answering one question per request, a LangGraph graph
inside one Lambda is simpler to build, deploy, and tear down, and it's the natural upgrade path if
this ever needs conversation memory or several cooperating agents (see
[Productionization](#-productionization--what-id-change-for-real-use)).

<a name="model-choice"></a>The LLM is also a deliberate choice, not the brief's suggested default:
the brief points at Claude 3 Haiku for near-zero inference cost, but this deployment uses Bedrock's
`openai.gpt-oss-20b-1:0` — also pay-per-token, also never leaves AWS, comparably cheap at this
volume, and already proven out during development. Swapping to Haiku is a one-line change
(`LLM_MODEL_ID` in [`infrastructure/backend/backend_stack.py`](infrastructure/backend/backend_stack.py)),
with nothing else affected, if the sandbox account's budget calls for it.

---

## 📁 Project Structure

Three independently deployable areas. The rule while working in this repo: **pick one area and stay
in it** — a change to the backend shouldn't drag in the CDK app or the Streamlit client.

```
backend/                 The API. Runs as a Lambda in AWS, as uvicorn locally.
  api/                    HTTP routes only — parse request, call domain/, return response.
                          Deliberately thin: no business logic here.
  domain/                 The actual logic.
                            document.py — upload pipeline (S3 → extract → chunk → embed → save),
                                          plus list/get/delete
                            search.py   — runs the agent, fuses the search scores, builds the
                                          response with sources + confidence
  models/                 Database tables as Python classes (SQLAlchemy ORM).
                          THIS is the schema source of truth — change a table here first.
  schemas/api/            Request/response shapes (Pydantic). Different from models/:
                          these describe JSON over HTTP, those describe database rows.
  services/agent/         The agent.
                            graph.py  — wires the loop together
                            nodes.py  — the LLM call + the system prompt (worth reading)
                            tools.py  — the four tools the agent can call
                            state.py  — what gets carried between loop iterations
  infrastructure/         Database connection + session handling.
                          NOT the CDK app — same word, different thing. Easy to confuse.
  config/                 Settings, all driven by environment variables.

frontend/                The Streamlit chat client. Pure HTTP calls — no AI logic lives here.
  api_client.py           Every network call to the API
  ui.py                   All rendering and Streamlit state

infrastructure/          The AWS definition (CDK, Python). One stack, split by concern:
  backend/network.py      VPC, subnets, VPC endpoints
  backend/database.py     RDS Postgres
  backend/storage.py      S3 bucket
  backend/compute.py      The Lambda + its IAM permissions
  backend/api.py          API Gateway + the API key
  backend/backend_stack.py  Assembles all of the above; model IDs are set here

alembic/                 Database migrations (versioned schema changes)
testing/                 Scripts that call the DEPLOYED API. Not unit tests — these cost real money.
docker-compose.yml       Run Postgres + backend + frontend locally, no AWS deploy needed
Makefile                 Shortcuts for everything below
```

**Where to change what:**

| I want to… | Edit |
|---|---|
| Change how the agent behaves / its instructions | `backend/services/agent/nodes.py` (the system prompt) |
| Add a new capability the agent can use | `backend/services/agent/tools.py` |
| Change chunk size or overlap | `backend/config/settings.py` |
| Change which AI model is used | `infrastructure/backend/backend_stack.py`, then redeploy |
| Add a database column | `backend/models/`, then generate a migration |
| Add an API endpoint | `backend/api/` + a schema in `backend/schemas/api/` |
| Change how confidence is calculated | `backend/domain/search.py` |

---

## 🚀 Getting Started

### What you need first

| Requirement | Why | Check it |
|---|---|---|
| **Python 3.12** | The Lambda image is 3.12; matching locally avoids surprises | `python3 --version` |
| **Docker**, running | The Lambda is packaged as a container image, and local dev uses docker-compose | `docker ps` |
| **AWS CLI**, configured | CDK and the helper scripts use your credentials | `aws sts get-caller-identity` |
| **AWS CDK CLI** | Turns the Python infrastructure code into real AWS resources | `npm install -g aws-cdk` then `cdk --version` |
| **Bedrock model access** | Bedrock models are opt-in per account **and per region** | Bedrock console → Model access |

Model access is worth confirming before deploying: without it the stack deploys cleanly and then
every query fails with `AccessDeniedException`. Enable both the embedding model and the chat model
in the deployment region.

Each of the three areas keeps its own virtualenv, and nothing is installed globally — commands run
without activating the right one fail with import errors.

---

### Option A — Run it locally first (recommended)

Fastest way to see it work, and it creates no AWS infrastructure.

**1. Start a local Postgres with pgvector** (the one service worth containerizing locally):

```bash
docker-compose up -d pgvector      # Postgres 18 + pgvector on localhost:5432
```

**2. Point the backend at it and create the tables.** `.env` should contain:

```
DATABASE_URL=postgresql+asyncpg://rag_user:rag_password@localhost:5432/rag_db
```

then:

```bash
make db-upgrade     # creates the extensions, tables, and index
```

**3. Run the two apps**, each in its own terminal:

```bash
make run             # backend with auto-reload on :8000
make run-streamlit   # Streamlit client on :8501
```

The API's interactive docs are at `http://localhost:8000/docs` — FastAPI generates them from the
code, so it's the quickest way to see every endpoint and try one without writing a curl command.

Two constraints apply to the local setup:

- **Bedrock calls still go to real AWS.** There is no local model, so embedding and generation are
  billed normally and AWS credentials must be available to the backend process. Everything else —
  database, API, UI — runs locally.
- **There is no authentication locally.** The token is enforced by API Gateway, which isn't in the
  path when `uvicorn` is run directly, so local testing cannot validate auth behavior.

> ⚠️ `docker-compose up` (all services) does **not** currently work: the compose file builds
> `frontend/Dockerfile`, which isn't in the repo, and the backend service builds the Lambda runtime
> image whose entrypoint is the Lambda handler rather than a web server on `:8000`. Use the
> `pgvector` service plus `make run` / `make run-streamlit` as above until that's fixed.

---

### Option B — Deploy to AWS

#### Step 1 — Install the infrastructure dependencies

```bash
cd infrastructure
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

#### Step 2 — Bootstrap CDK (first time per account/region only)

```bash
cdk bootstrap
```

CDK needs somewhere to upload the Docker image and templates it builds. `bootstrap` creates that
staging area once. Skipping it produces an error along the lines of *"This stack uses assets,
so the toolkit stack must be deployed"*.

#### Step 3 — Tell it which IP may reach the database

```bash
export DEV_ACCESS_IP=$(curl -s ifconfig.me)
```

This becomes the single-IP firewall rule on the database. It's **required** — without it, `cdk
synth` fails immediately with a `KeyError: 'DEV_ACCESS_IP'`. Re-export it if your IP changes (home
vs. office vs. VPN), or you'll be locked out of your own database.

#### Step 4 — Check, then deploy

```bash
cdk synth    # renders the CloudFormation template; catches errors without touching AWS
cdk deploy RagChatBackendStack --require-approval=never
```

`synth` is a dry run and catches most configuration errors locally. `deploy` takes roughly 10–15
minutes on a fresh account, most of it provisioning RDS.

When it finishes, CDK prints the **outputs** — save these, every following step needs them:

```
RagChatBackendStack.ApiEndpoint       = https://abc123.execute-api.us-east-1.amazonaws.com/prod/
RagChatBackendStack.ApiKeyId          = x8acrmbp9l
RagChatBackendStack.DatabaseEndpoint  = rag-chat-db.xxxx.us-east-1.rds.amazonaws.com
RagChatBackendStack.UploadBucketName  = rag-chat-document-bucket
RagChatBackendStack.LambdaFunctionName = rag-chat-app
```

#### Step 5 — Get the real access token

`ApiKeyId` is an identifier, **not** the token. Exchange it for the actual value:

```bash
aws apigateway get-api-key --api-key <ApiKeyId> --include-value --query value --output text
```

Put that value in `.env.prod` as `API_TOKEN`, along with the other outputs. That file is gitignored
— never commit it.

#### Step 6 — Create the database tables

The deploy creates an *empty* Postgres instance. The tables don't exist yet, and **migrations do
not run automatically** — you must run them yourself after every fresh deploy:

```bash
make db-upgrade ENV=prod
```

The migrations in `alembic/versions/` build the schema from nothing when run in order: enable the
`vector` and `pg_trgm` extensions, create the `document` and `chunk` tables, add the HNSW index.
Skipping this step leaves every request failing with "relation does not exist".

This runs from your machine, over the internet, to the database — which is exactly why Step 3's
`DEV_ACCESS_IP` matters.

#### Step 7 — Put some documents in

```bash
set -a && source .env.prod && set +a          # load API_BASE_URL and API_TOKEN into your shell
python testing/upload_batch.py path/to/doc1.pdf path/to/doc2.txt
```

Verify they landed:

```bash
python testing/list_files.py
python testing/query_count.py    # how many chunks are indexed
```

#### Step 8 — Run the Streamlit client

```bash
cd frontend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit it:
#   API_BASE_URL = "<ApiEndpoint from step 4>"
#   API_TOKEN    = "<token value from step 5>"

streamlit run app.py
```

Opens at `http://localhost:8501`. Click **Check connection** in the sidebar first — it confirms the
URL and token are wired up before you waste a question on a misconfiguration.

#### Step 9 — Ask something

Through the UI, or straight from the terminal:

```bash
curl -s -X POST "$API_BASE_URL/api/query/" \
  -H "x-api-key: $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "What does the knowledge base cover?", "top_k": 5}' | python -m json.tool
```

or the scripted equivalent:

```bash
python testing/query.py "What does the knowledge base cover?"
```

---

### 🔧 Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `KeyError: 'DEV_ACCESS_IP'` on synth/deploy | Env var not set | `export DEV_ACCESS_IP=$(curl -s ifconfig.me)` |
| `BucketAlreadyExists` on deploy | The bucket name is hardcoded, and S3 names are globally unique across all AWS accounts | Change `bucket_name` in `infrastructure/backend/storage.py` to something unique |
| `{"message":"Forbidden"}` | Missing or wrong `x-api-key` | You probably used `ApiKeyId` instead of the key *value* — see Step 5 |
| `relation "document" does not exist` | Migrations never ran | `make db-upgrade ENV=prod` |
| Migration hangs, then times out | Your IP isn't the one allowed on the DB | Re-export `DEV_ACCESS_IP` and redeploy, or update the security group in the console |
| `AccessDeniedException` from Bedrock | Model access not enabled in this region | Bedrock console → Model access → enable both models |
| First request takes ~10s, later ones are fast | Lambda cold start | Expected — see the Lambda note in [Architecture](#what-each-box-is) |
| Query returns a gateway timeout | API Gateway caps a request at 29s; a multi-search question can exceed it | Ask a narrower question, or see [Known Limitations](#known-limitations) |

---

### 🧹 Cleanup

```bash
make destroy    # cdk destroy --all --force
```

The S3 bucket is configured with `auto_delete_objects`, so this empties and removes it — no manual
step. RDS has deletion protection off and no backup retention, so it goes cleanly with no leftover
snapshot.

**One thing this doesn't remove:** the database password in Secrets Manager. AWS keeps deleted
secrets for a recovery window (default 30 days) and bills ~$0.40/month until it lapses. To remove
it immediately:

```bash
aws secretsmanager delete-secret --secret-id <name> --force-delete-without-recovery
```

Afterwards, confirm nothing is left in the CloudFormation console — a stack stuck in
`DELETE_FAILED` usually means a resource still has something in it.

---

## 📡 API Reference

Everything is served under the API Gateway URL from Step 4, e.g.
`https://abc123.execute-api.us-east-1.amazonaws.com/prod`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health/` | Liveness check, no side effects |
| POST | `/api/upload/` | Upload one file — `multipart/form-data`, field `file` |
| POST | `/api/upload/batch` | Upload several files in one request |
| GET | `/api/files/?skip=0&limit=100` | Paginated document list |
| GET | `/api/files/{file_id}` | One document's metadata |
| GET | `/api/files/{file_id}/download` | Short-lived (5 min) presigned S3 URL for the original file |
| DELETE | `/api/files/{file_id}` | Delete a document (S3 original + Postgres row + its chunks) |
| POST | `/api/query/` | Ask the knowledge base a question (the core endpoint) |
| GET | `/api/query/count` | Total indexed chunk count |

A **presigned URL** is a temporary link that grants access to a private S3 file without making the
bucket public. The bucket stays fully locked down; the link expires after 5 minutes.

### Authentication

Every route requires this header:

```
x-api-key: <token>
```

It's checked by API Gateway itself, before your code runs — there's no authentication logic
anywhere in the application. A request with a missing or wrong key never reaches the Lambda:

```
403 Forbidden
{ "message": "Forbidden" }
```

That body is API Gateway's own format, not this project's. Normalizing it would require a custom
Lambda authorizer — see [Known Limitations](#known-limitations).

**How the token is managed:**
- Created by CDK (`add_api_key` in `infrastructure/backend/api.py`) — never hardcoded in source.
- Retrieved after deploy with the `aws apigateway get-api-key` command in Step 5.
- Stored in `.env.prod` (for scripts) and `frontend/.streamlit/secrets.toml` (for the UI). Both are
  gitignored. `frontend/api_client.py` attaches it to every request.

### `POST /api/query/`

Request:
```json
{
  "question": "What is the refund policy for enterprise customers?",
  "top_k": 5,
  "explain_like_10": false
}
```

| Field | Required | Meaning |
|---|---|---|
| `question` | yes | 1–1000 characters |
| `top_k` | no (default 5) | 1–20. Caps how many source passages come back in the response. Note it does **not** limit how much the agent searches internally — see [Inside the RAG pipeline](#-inside-the-rag-pipeline). |
| `explain_like_10` | no (default false) | Accepted and echoed back, but does not currently change the answer — see [Known Limitations](#known-limitations) |

Response:
```json
{
  "answer": "Enterprise customers can request a refund within the documented refund window...",
  "sources": [
    {
      "source": "refund_policy.pdf",
      "chunk_index": 4,
      "file_path": "raw/9e2b.../refund_policy.pdf",
      "content_preview": "Enterprise refund requests must be reviewed...",
      "similarity_score": 0.91
    }
  ],
  "confidence_score": 0.84,
  "confidence_breakdown": {
    "best_similarity": 0.91,
    "avg_similarity": 0.84,
    "consistency": 0.93,
    "keyword_match": 0.62,
    "final_score": 0.84
  },
  "similarity_scores": [0.91, 0.84, 0.78],
  "query": "What is the refund policy for enterprise customers?",
  "timestamp": "2026-08-20T10:15:00",
  "explain_mode": false
}
```

| Field | What it tells you |
|---|---|
| `answer` | The generated response, built only from retrieved passages |
| `sources` | The passages behind it. `source` is the filename, `chunk_index` its position in that document, `content_preview` the actual text |
| `similarity_score` | How strong a match that passage was, 0–1 |
| `confidence_score` | Overall confidence in the answer, 0–1 |
| `confidence_breakdown` | The components behind that number — see [Confidence](#confidence-explained) |

This differs slightly from the schema in the brief: sources are flattened (no separate
`document_id`/`chunk_id` — `source` + `chunk_index` identify a passage), and there's no `metadata`
block (`model`, `request_id`, `latency_ms`) yet. Both noted in
[Known Limitations](#known-limitations).

### Error responses

| Case | Status | Body |
|---|---|---|
| Missing/invalid `x-api-key` | 403 | `{"message": "Forbidden"}` — from API Gateway, before the Lambda runs |
| Invalid request body (e.g. empty `question`) | 422 | FastAPI's default `{"detail": [...]}` |
| Duplicate upload (same content hash) | 409 | `{"detail": "A document with identical content already exists in the knowledge base"}` |
| Unknown `file_id` | 404 | `{"detail": "File not found"}` |
| Unhandled server error | 500 | FastAPI default, no redaction applied |

---

## 🧠 Inside the RAG Pipeline

The implementation detail behind [How It Works](#-how-it-works).

### Ingestion — `backend/domain/document.py`

Three steps, in order:

1. **ingest** — original bytes to S3 under `raw/{document_id}/{filename}`.
2. **transform** — text extraction: `pypdf`, `python-docx`, or a UTF-8 decode.
3. **index** — `RecursiveCharacterTextSplitter` (1000 chars, 200 overlap, `add_start_index=True` so
   each chunk records its character offset), then one Titan embedding call per chunk, then a single
   database transaction inserting the document and all its chunks.

The splitter breaks on paragraph boundaries first, then sentences, then words, falling back to a
hard character cut only when nothing better is available — so chunks land on natural boundaries far
more often than under fixed-width splitting.

Embedding calls run 16 at a time with adaptive retries. Titan embeds one chunk per call, so a
200-chunk document processed sequentially is 200 round trips of pure latency. The concurrency bound
exists because Bedrock throttles per account; adaptive retry backs off when it does.

### The four tools — `backend/services/agent/tools.py`

| Tool | What it does |
|---|---|
| `semantic_search(concept)` | Embeds the phrase, finds nearest chunks by cosine distance via the HNSW index. Returns text, filename, similarity, and character offsets |
| `keyword_search(pattern)` | Postgres case-insensitive regex (`~*`) over full document text. Guarded by a 5-second statement timeout so a pathological pattern can't tie up a connection |
| `list_documents()` | Filenames only, no content — cheap, for questions about the corpus itself |
| `read_document(document_id, char_start, char_end)` | Reads a character range of the extracted text, capped at 8000 characters per call. This is how a search hit gets expanded into full context |

The system prompt in `nodes.py` carries most of the behavior worth reviewing. It instructs the
model to expand every hit before answering, match search effort to question complexity, stop once
the evidence is sufficient rather than searching exhaustively, never state a confidence figure
itself, and state plainly where the documents stop covering the question.

### Combining the two searches — `backend/domain/search.py`

As the agent works, hits accumulate: semantic hits keyed by chunk (keeping the best score seen),
keyword hits keyed by document. Afterwards the two are fused per chunk:

```
combined = 1 - (1 - keyword_score) × (1 - semantic_score)
```

The form treats the two signals as independent evidence: the combined score is the complement of
both being wrong at once. A passage both searches agree on therefore scores higher than under
either alone, while a passage found by only one keeps that one's score.

| semantic | keyword | combined | reading |
|---|---|---|---|
| 0.80 | 0.00 | 0.80 | strong meaning match only |
| 0.00 | 0.70 | 0.70 | exact phrase match only |
| 0.80 | 0.70 | 0.94 | both agree — much stronger evidence |

Any signal at or below **0.2** is treated as noise and zeroed; a chunk left with no signal is
dropped. Whatever survives is sorted and cut to `top_k`.

### <a name="confidence-explained"></a>Confidence

Four components, all derived from retrieval — never asked of the model:

| Component | Meaning |
|---|---|
| `best_similarity` | The strongest single match |
| `avg_similarity` | Average across the returned passages |
| `consistency` | `1 - (best - min)`. Do the top results agree, or is one a lucky outlier? |
| `keyword_match` | Strongest exact-wording signal |
| `final_score` | The average of the fused scores — since fusion already folds in both signals |

The UI colors it green above 0.7, amber above 0.4, red below. Deliberately coarse: it's a *signal
that retrieval went well*, not a probability the answer is correct. High confidence with wrong
retrieval is still possible — the score reflects how well the search matched, not whether the
document was right.

---

## 📚 Sample Documents & Seeding

A full document-ingestion workflow was optional in the brief; this project implements one anyway,
so the knowledge base can be filled either way:

1. **Streamlit uploader** — drag files into the sidebar, it POSTs to `/api/upload/`.
2. **Script** — `testing/upload.py` or `testing/upload_batch.py`, same auth as everything else.

`testing/assets/` currently holds two PDFs (`transformers.pdf`, `word2vec.pdf` — ML papers) used
while developing the ingestion path. **These are not the business-style sample set (refund policy,
FAQ, handbook) the brief's example query implies** — a known gap: drop 3–5 short business documents
into a `sample-docs/` folder and run them through `upload_batch.py` before a review demo.

---

## 🔐 Security

- **API boundary** — API key + usage plan on every route. Nothing is publicly callable.
- **Network** — the Lambda has no internet route at all; it reaches AWS services through VPC
  endpoints only. The database is firewalled to a single IP, not `0.0.0.0/0`.
- **Secrets** — the database password is generated by CDK straight into Secrets Manager and read by
  the Lambda at startup. It is never in source, never in an environment variable, and never printed.
  `.env`, `.env.prod`, and `secrets.toml` are all gitignored.
- **IAM** — the Lambda's role is narrow by design: `bedrock:InvokeModel` on exactly the two model
  ARNs it uses, read on one secret, read/write on one bucket. No wildcard grants.
- **CORS** — currently open to all origins for demo convenience. See
  [Known Limitations](#known-limitations).
- **Data residency** — every AI call goes to Amazon Bedrock inside your own AWS account. No
  third-party AI API is involved. Documents, chunks, and embeddings stay in your RDS instance;
  originals stay in your S3 bucket. Nothing in the ingestion or query path calls a non-AWS service.

---

## 💸 Cost Notes (sandbox account, $20 budget)

| Resource | Ongoing cost driver |
|---|---|
| Lambda | Pay-per-invocation only — $0 idle |
| API Gateway | Pay-per-request only — $0 idle |
| RDS `db.t4g.micro`, 20GB | ~$12–13/month if left running — **the main thing to tear down** |
| 2× VPC interface endpoints (Bedrock, Secrets Manager), 2 AZs | ~$0.01/hr per AZ-endpoint ≈ $14–15/month if left running |
| S3 gateway endpoint | Free |
| Bedrock (Titan embeddings + LLM) | Pay-per-token, near-zero at demo volume |
| Secrets Manager | ~$0.40/month per secret while it exists |

The two lines that matter are RDS and the interface endpoints: both bill by the hour regardless of
traffic, and together they approach the $20 budget within a month. Fine for a multi-day review
window — but **run `make destroy` as soon as evaluation is done**, don't leave it up.

---

## 📎 Evidence of Execution

*(Template — attach after a real run: the Streamlit question, the resulting `x-api-key`-authenticated
API request, the JSON response, and either a screenshot or the relevant CloudWatch log lines showing
the request id and latency. Nothing here should be filled in without actually having run it.)*

---

## ⚠️ Assumptions & Known Limitations

<a name="known-limitations"></a>

- **Migrations aren't automatic** — a fresh `cdk deploy` leaves an empty database until you run
  `make db-upgrade ENV=prod` yourself. Easy to forget; the failure looks like a 500 on every call.
- **The S3 bucket name is hardcoded**, and S3 names are globally unique across all of AWS, so a
  deploy into a different account collides. Change it in `infrastructure/backend/storage.py`.
- **No `metadata` in query responses** — no `request_id`, `latency_ms`, or `model`, which makes
  correlating a user-reported problem with a CloudWatch log entry harder than it should be.
- **`explain_like_10` is accepted but not implemented** — echoed back as `explain_mode`, but it
  doesn't change the generated answer.
- **`top_k` shapes returned sources, not retrieval depth** — the agent decides how much to search;
  `top_k` only caps how many results come back.
- **No conversation memory** — every request is independent. The chat history in the UI is display
  only; previous turns are never sent back, so follow-ups like "and what about enterprise?" won't
  resolve.
- **No automated citation check** — nothing verifies the generated prose is actually supported by
  the sources returned beside it, beyond the prompt instructing the model to stay grounded.
- **CORS is wide open** (`allow_origins=["*"]`) for demo convenience.
- **29-second ceiling** — API Gateway caps a request at 29 seconds, while the Lambda is allowed 3
  minutes and the agent has no hard cap on tool-call iterations. A question triggering several
  rounds of search can time out at the gateway while the Lambda is still working.
- **Retries stack** — `api/query.py` retries the whole agent 3× and the graph retries each node 3×,
  so a persistently failing request can cost far more than one run.
- **`docker-compose up` is partly broken** — the `frontend` service builds a `frontend/Dockerfile`
  that doesn't exist, and the `backend` service builds the Lambda image (entrypoint `index.handler`)
  rather than a web server. Only the `pgvector` service is usable as-is; local dev runs through
  `make run` / `make run-streamlit`.
- **RDS is publicly reachable** (locked to a single IP) rather than fully private — a deliberate
  tradeoff for local migration/inspection convenience.

---

## 🏭 Productionization — What I'd Change for Real Use

**Security**
- Move RDS fully into the private isolated subnet; run Alembic from inside the VPC (a one-off ECS
  task, or a CDK custom resource) instead of exposing the DB to a dev IP.
- Replace the API Gateway API key with a Lambda authorizer (JWT/Cognito) if this ever needs
  per-user identity instead of one shared token; API keys don't expire or scope per caller.
- Scope CORS to the actual frontend origin(s).
- Normalize error responses into `{error, message, request_id}` and stop leaking framework-default
  bodies (FastAPI `detail`, API Gateway `message`) directly to callers.

**Reliability / cost control**
- Cap agent tool-call iterations (`recursion_limit` on the LangGraph invocation) so a pathological
  question can't run indefinitely or blow past the 29-second gateway ceiling.
- Collapse the double retry into a single bounded layer.
- Rate-limit per caller via the usage plan's throttle/quota settings (currently unset — unlimited
  by default).

**Observability**
- Add a request id generated at the API boundary, propagate it through logs and into the response
  `metadata` block, and switch `logging.basicConfig` to structured JSON logs so CloudWatch Insights
  queries are actually usable.
- A CloudWatch dashboard/alarm on Lambda error rate, p99 latency, and RDS connections would catch
  regressions before a user reports them.

**Data lifecycle**
- Automate the Alembic migration as part of deploy (CDK custom resource or a cold-start guard) so
  a fresh `cdk deploy` doesn't require a manual step.
- Add a retention/lifecycle policy for uploaded originals in S3 if documents are ever meant to
  expire.

**Scaling**
- Current scale is fine, but two ceilings would bite first: **RDS connection limits** (Lambda scales
  out faster than a `t4g.micro` accepts connections — RDS Proxy or pgbouncer solves it) and
  **Bedrock's per-account throttle** (already retried, but a real burst would exhaust it).
- A larger corpus would need HNSW index tuning and probably a re-embedding strategy for when the
  embedding model is upgraded.
