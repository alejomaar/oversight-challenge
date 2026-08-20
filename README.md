# 📚 Knowledge Base AI Agent — AWS-Native

A **Knowledge Base AI Agent** that lets you upload documents (PDF, Word, or plain text), builds a
searchable knowledge base out of them, and answers questions about their contents — with the
sources it used and how confident it is in the answer, so nothing is ever just made up. It runs
entirely on AWS, and a small local Streamlit app is the chat window you talk to it through.

## ✨ Key Features

- 📄 **Upload almost anything** — PDF, Word, or plain text, with duplicate uploads rejected automatically.
- 🔍 **Finds the right passage two ways at once** — by meaning, so paraphrased questions work, and by exact wording, so names and codes aren't missed.
- 🤖 **Searches like a person would** — it decides how much digging a question needs and reads the full passage around anything it finds.
- 📊 **Shows its work** — every answer carries the passages it was built from and a confidence score with its breakdown.
- 🔐 **Locked behind an access token**, deployed and torn down with one command, and costing nothing while idle.

---

## 🧭 How It Works

The system has two paths: **ingestion**, which turns an uploaded file into searchable records, and
**query**, which answers a question from those records.

### Ingestion

1. The original file is stored untouched in S3, so the source remains recoverable.
2. Text is extracted, using the appropriate reader for the file type.
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

The justification for the added complexity is that a fixed pipeline applies identical retrieval
effort to every question, which is rarely appropriate: a narrow factual question is resolved by one
targeted search and one expanded read, a comparative question needs several searches across
documents, and a question about the corpus itself needs no retrieval at all.

`read_document` is the tool that most affects answer quality. A search hit is a chunk cut at an
arbitrary boundary, so the prompt requires the agent to expand each hit to its complete paragraph
or section before answering.

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

- **API Gateway** — managed HTTPS front door. Validates the API key and forwards to the Lambda.
- **Lambda** — the API process, billed per request, nothing while idle. The tradeoff is cold start
  on the first request after an idle period.
- **Mangum** — adapts Lambda's event format to ASGI, so the same FastAPI app runs unchanged as a
  Lambda and as a local server.
- **RDS Postgres** — the knowledge base itself. `pgvector` supplies the vector column type and
  similarity operators, keeping retrieval a SQL query rather than a second datastore to
  synchronize; `pg_trgm` backs fuzzy text matching.
- **S3** — original uploaded files only. Postgres is authoritative for everything the agent reads.
- **Bedrock** — managed model inference inside AWS: Titan for embeddings, a chat model for
  generation.
- **Secrets Manager** — holds the generated database password, read by the Lambda at cold start.

### Networking

The Lambda runs in private isolated subnets with no route to the internet, and reaches Bedrock, S3,
and Secrets Manager through VPC endpoints — private routes from inside the VPC directly to an AWS
service. Traffic never traverses the public internet, and the design carries no per-hour egress
infrastructure.

The database is the deliberate exception: it sits in a public subnet so migrations and inspection
can be run from a developer machine, with its security group restricted to the single address in
`DEV_ACCESS_IP`.

---

## 🛠️ Tech Stack

| Layer | Choice | Why |
|---|---|---|
| API compute | AWS Lambda (Docker image via Mangum) | Pay-per-invocation, zero idle cost, fits FastAPI unchanged |
| API entry point | Amazon API Gateway (REST) | Managed auth (API key + usage plan) without writing an authorizer |
| Vector store | RDS Postgres + pgvector (HNSW index) | One database holds metadata, text, and embeddings — nothing else to run or keep in sync |
| Keyword search | Postgres `pg_trgm` / `~*` regex | No separate search engine for a small corpus |
| Embeddings | Bedrock Titan `amazon.titan-embed-text-v2:0` | AWS-native, cheap, no data leaves AWS |
| LLM | Bedrock `openai.gpt-oss-20b-1:0` | AWS-hosted, pay-per-token, no data leaves AWS |
| Orchestration | LangGraph (ReAct-style loop + `ToolNode`) | Lets the agent decide *how much* retrieval a question needs |
| Storage | S3 (original files only) | Provenance only — Postgres is authoritative for content |
| IaC | AWS CDK (Python), one stack | Readable, reproducible, tears down cleanly |
| Frontend | Streamlit (thin HTTP client) | No retrieval or generation logic in the client |

**Bedrock Knowledge Bases** would have handled retrieval end-to-end, but it still needs a vector
store underneath, and with pgvector already in place a hand-rolled agent gives more control over
blending semantic and keyword evidence. **Bedrock AgentCore** would have hosted the agent itself
with managed memory and tracing — the natural upgrade path if this ever needs conversation memory
or several cooperating agents, but more operational surface than one stateless agent requires
today. The LLM is `openai.gpt-oss-20b-1:0` rather than the suggested Claude 3 Haiku; both are
pay-per-token inside AWS, and swapping is a one-line change to `LLM_MODEL_ID` in
[`backend_stack.py`](infrastructure/backend/backend_stack.py).

---

## 📁 Project Structure

```
backend/                 The API. Lambda in AWS, uvicorn locally.
  api/                    HTTP routes only — thin, no business logic
  domain/                 document.py (upload pipeline) and search.py (agent + scoring)
  models/                 Database tables (SQLAlchemy) — the schema source of truth
  schemas/api/            Request/response shapes (Pydantic)
  services/agent/         graph.py, nodes.py (LLM + system prompt), tools.py, state.py
  infrastructure/         DB connection and sessions — NOT the CDK app
  config/                 Settings, driven by environment variables

frontend/                Streamlit client — api_client.py (HTTP) and ui.py (rendering)

infrastructure/          CDK. One stack, split by concern:
  backend/network.py      VPC, subnets, VPC endpoints
  backend/database.py     RDS Postgres
  backend/storage.py      S3 bucket
  backend/compute.py      Lambda + IAM permissions
  backend/api.py          API Gateway + API key
  backend/backend_stack.py  Assembles everything; model IDs set here

alembic/                 Database migrations
Makefile                 Shortcuts for deploys, migrations, and local dev servers
```

---

## 🚀 Getting Started

**Prerequisites:** Python 3.12, Docker running, AWS CLI configured, and the CDK CLI
(`npm install -g aws-cdk`). Bedrock model access is opt-in per account and region — enable both the
embedding model and the chat model in your deployment region first. Each of the three areas keeps
its own virtualenv; activate the right one before running anything in it.

### Option A — Run it locally

```bash
docker-compose up -d pgvector    # Postgres + pgvector on :5432
make db-upgrade                  # create extensions, tables, index
make run                         # backend on :8000  (interactive docs at /docs)
make run-streamlit               # Streamlit client on :8501
```

`.env` needs `DATABASE_URL=postgresql+asyncpg://rag_user:rag_password@localhost:5432/rag_db`.

Two constraints: **Bedrock calls still go to real AWS** (there is no local model, so embedding and
generation are billed normally), and **there is no authentication locally** — the token is enforced
by API Gateway, which isn't in the path when running directly.

### Option B — Deploy to AWS

```bash
cd infrastructure && python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

cdk bootstrap                              # once per account/region
export DEV_ACCESS_IP=$(curl -s ifconfig.me)   # required — the DB firewall rule
cdk synth                                  # dry run, touches nothing in AWS
cdk deploy RagChatBackendStack --require-approval=never
```

Deploy takes 10–15 minutes on a fresh account, most of it provisioning RDS, and prints the outputs
every following step needs: `ApiEndpoint`, `ApiKeyId`, `DatabaseEndpoint`, `UploadBucketName`,
`LambdaFunctionName`.

`ApiKeyId` is an identifier, not the token. Exchange it, then populate `.env.prod` (gitignored):

```bash
aws apigateway get-api-key --api-key <ApiKeyId> --include-value --query value --output text
```

Create the schema — **migrations do not run automatically**, and this runs from your machine, which
is why `DEV_ACCESS_IP` matters:

```bash
make db-upgrade ENV=prod
```

Add documents and ask a question:

```bash
set -a && source .env.prod && set +a          # API_BASE_URL and API_TOKEN

curl -X POST "$API_BASE_URL/api/upload/" -H "x-api-key: $API_TOKEN" -F "file=@doc.pdf"

curl -s -X POST "$API_BASE_URL/api/query/" \
  -H "x-api-key: $API_TOKEN" -H "Content-Type: application/json" \
  -d '{"question": "What does the knowledge base cover?", "top_k": 5}' | python -m json.tool
```

For the UI: `cd frontend`, install requirements, copy `.streamlit/secrets.toml.example` to
`secrets.toml` with `API_BASE_URL` and `API_TOKEN`, then `streamlit run app.py`.

### 🧹 Cleanup

```bash
make destroy    # cdk destroy --all --force
```

The S3 bucket empties itself and RDS leaves no snapshot. The one leftover is the database password
in Secrets Manager, which AWS retains for a recovery window and bills ~$0.40/month until it lapses;
`aws secretsmanager delete-secret --force-delete-without-recovery` removes it immediately.

---

## 📡 API Reference

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health/` | Liveness check |
| POST | `/api/upload/` | Upload one file — `multipart/form-data`, field `file` |
| POST | `/api/upload/batch` | Upload several files |
| GET | `/api/files/` | Paginated document list (`skip`, `limit`) |
| GET | `/api/files/{file_id}` | One document's metadata |
| GET | `/api/files/{file_id}/download` | Short-lived presigned S3 URL for the original |
| DELETE | `/api/files/{file_id}` | Delete a document and its chunks |
| POST | `/api/query/` | Ask the knowledge base a question |
| GET | `/api/query/count` | Total indexed chunk count |

### Authentication

Every route requires `x-api-key: <token>`, validated by API Gateway itself, so a request without a
valid key is rejected at the edge and never reaches the Lambda. There is no authentication logic in
the application code. The key is created by CDK, retrieved after deploy with
`aws apigateway get-api-key`, and stored in `.env.prod` and `frontend/.streamlit/secrets.toml` —
both gitignored.

### `POST /api/query/`

`question` is required (1–1000 chars). `top_k` (1–20, default 5) caps how many source passages come
back; it does not limit how much the agent searches internally.

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
    "best_similarity": 0.91, "avg_similarity": 0.84,
    "consistency": 0.93, "keyword_match": 0.62, "final_score": 0.84
  },
  "similarity_scores": [0.91, 0.84, 0.78],
  "query": "What is the refund policy for enterprise customers?",
  "timestamp": "2026-08-20T10:15:00",
  "explain_mode": false
}
```

---

## 🧠 Inside the RAG Pipeline

**Ingestion** (`backend/domain/document.py`) is three steps: original bytes to S3, text extraction,
then chunking and embedding into Postgres in one transaction. Splitting is boundary-aware — it
breaks on paragraphs first, then sentences, then words. Embedding calls run 16 at a time with
adaptive retries, since Titan embeds one chunk per call and throttles per account.

**The four tools** (`backend/services/agent/tools.py`):

| Tool | What it does |
|---|---|
| `semantic_search(concept)` | Nearest chunks by cosine distance via the HNSW index. Returns text, filename, similarity, offsets |
| `keyword_search(pattern)` | Case-insensitive regex over document text, guarded by a 5-second statement timeout |
| `list_documents()` | Filenames only, for questions about the corpus itself |
| `read_document(id, start, end)` | A character range of the extracted text, capped at 8000 characters — how a hit is expanded into full context |

The system prompt in `nodes.py` carries most of the behavior worth reviewing: expand every hit
before answering, match search effort to question complexity, never state a confidence figure, and
say plainly where the documents stop covering the question.

**Scoring** (`backend/domain/search.py`). Semantic and keyword hits accumulate as the agent works,
then fuse per chunk:

```
combined = 1 - (1 - keyword_score) × (1 - semantic_score)
```

The two signals are treated as independent evidence, so the combined score is the complement of
both being wrong at once — a passage both searches agree on scores higher than under either alone
(0.80 and 0.70 fuse to 0.94), while a passage found by only one keeps that score. Anything at or
below 0.2 is treated as noise and dropped; what survives is sorted and cut to `top_k`.

**Confidence** is derived entirely from retrieval, never asked of the model: best similarity,
average similarity, consistency (`1 - (best - min)` — whether the top results agree or one is a
lucky outlier), and keyword strength. It signals that retrieval went well, not that the answer is
correct.


---

## 🔐 Security

- **API boundary** — API key + usage plan on every route. Nothing is publicly callable.
- **Network** — the Lambda has no internet route; it reaches AWS services through VPC endpoints
  only. The database is firewalled to a single IP.
- **Secrets** — the database password is generated by CDK into Secrets Manager and read at startup.
  Never in source, never in an environment variable. `.env`, `.env.prod`, and `secrets.toml` are
  gitignored.
- **IAM** — the Lambda's role is scoped to `bedrock:InvokeModel` on exactly the two model ARNs it
  uses, read on one secret, read/write on one bucket. No wildcard grants.
- **Data residency** — every model call goes to Bedrock inside your own account. Documents, chunks,
  and embeddings stay in your RDS instance. Nothing calls a non-AWS service.

---

## 💸 Cost Notes (sandbox account, $20 budget)

| Resource | Ongoing cost driver |
|---|---|
| Lambda, API Gateway, S3 gateway endpoint | Pay-per-use — $0 idle |
| RDS `db.t4g.micro`, 20GB | ~$12–13/month if left running |
| 2× VPC interface endpoints across 2 AZs | ~$14–15/month if left running |
| Bedrock (embeddings + LLM) | Pay-per-token, near-zero at demo volume |
| Secrets Manager | ~$0.40/month per secret |

RDS and the interface endpoints bill by the hour regardless of traffic and together approach the
$20 budget within a month. Fine for a review window — **run `make destroy` when evaluation is
done**.

---

## 📎 Evidence of Execution

*(Template — attach after a real run: the Streamlit question, the API request, the JSON response,
and a screenshot or the relevant CloudWatch log lines.)*

---

## ⚠️ Assumptions & Known Limitations

- **Migrations aren't automatic** — a fresh deploy leaves an empty database until `make db-upgrade
  ENV=prod` is run against it.
- **The S3 bucket name is hardcoded**, and S3 names are globally unique, so a deploy into another
  account collides. Change it in `infrastructure/backend/storage.py`.
- **No `metadata` in query responses** — no `request_id`, `latency_ms`, or `model`, which makes
  correlating a request with its CloudWatch log entry harder than it should be.
- **`explain_like_10` is accepted but not implemented**, and **`top_k` shapes returned sources, not
  retrieval depth**.
- **No conversation memory** — every request is independent, so follow-up questions don't resolve
  against earlier turns.
- **No automated citation check** — nothing verifies the prose is supported by the sources beside
  it, beyond the prompt.
- **29-second ceiling** — API Gateway caps a request at 29 seconds while the Lambda is allowed 3
  minutes, and the agent has no hard cap on tool-call iterations.
- **CORS is open** to all origins, and **RDS is publicly reachable** (locked to a single IP) rather
  than fully private.

---

## 🏭 Productionization — What I'd Change for Real Use

The architecture is already the shape a production system would take — serverless compute behind a
managed gateway, one database, infrastructure as code, secrets never in source. What it would need
before carrying real traffic:

**Security** — move RDS fully private and run migrations from inside the VPC; replace the shared API
key with a Lambda authorizer (JWT/Cognito) once per-user identity matters; scope CORS to the real
frontend origin.

**Reliability and cost** — cap agent tool-call iterations so a pathological question can't run past
the gateway ceiling; collapse the double retry (three attempts around a graph that itself retries
each node three times) into one bounded layer; set the usage plan's throttle and quota, currently
unlimited.

**Observability** — a request id generated at the API boundary, propagated through logs and into
the response, plus structured JSON logs and CloudWatch alarms on failure rate, p99 latency, and RDS
connections.

**Scaling** — two ceilings would bite first: RDS connection limits, since Lambda scales out faster
than a `t4g.micro` accepts connections (RDS Proxy solves it), and Bedrock's per-account throttle. A
larger corpus would need HNSW tuning and a re-embedding strategy for model upgrades.
