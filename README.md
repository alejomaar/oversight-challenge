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

**Ingestion.** The original file goes to S3 untouched, its text is extracted, and that text is split
into ~1000-character chunks with 200 characters of overlap. Each chunk records its offset in the
source text — which is what later lets a search hit be expanded back into its surrounding context —
and is embedded by Bedrock's Titan model into a 1024-dimension vector. Chunk text, offsets, and
embeddings land in Postgres in one transaction. Files are hashed with SHA-256 first, so an
identical re-upload is rejected rather than duplicated.

**Query.** A conventional RAG implementation embeds the question, retrieves a fixed number of
nearest chunks, and passes them to the model in one prompt. This project instead exposes retrieval
as tools — semantic search, keyword search, list documents, read document — and lets the model
choose: it calls what it needs, reads the results, and either calls again or answers. That matters
because a fixed pipeline applies identical effort to every question: a narrow factual question
needs one search and one expanded read, a comparative question needs several across documents, and
a question about the corpus itself needs none. `read_document` is what most affects answer quality
— a search hit is a chunk cut at an arbitrary boundary, so the prompt requires the agent to expand
each hit to its complete paragraph or section before answering.

---

## 🏗️ Architecture

```
Local Streamlit ──HTTPS + x-api-key──▶ API Gateway (REST, API key + usage plan)
                                                  │
                                                  ▼
                                  Lambda — FastAPI via Mangum
                                  + LangGraph ReAct agent
                                  (Docker image, private isolated subnet)
                                       │         │          │
                         VPC endpoints │         │          │
                                       ▼         ▼          ▼
                                   Bedrock      S3     Secrets Manager
                                Titan + LLM  originals   DB password
                                       │
                                       ▼
                          RDS Postgres 16 + pgvector + pg_trgm
                          document / chunk tables, 1024-dim embeddings
```

**API Gateway** validates the API key and forwards to the **Lambda**, which runs the FastAPI app
(via **Mangum**, so the same app runs unchanged locally) and is billed per request with nothing
while idle. **RDS Postgres** is the knowledge base: `pgvector` supplies the vector column type and
similarity operators, keeping retrieval a SQL query rather than a second datastore to synchronize;
`pg_trgm` backs fuzzy matching. **S3** holds original files only, **Bedrock** provides both models,
and **Secrets Manager** holds the database password, read at cold start.

The Lambda runs in private isolated subnets with no route to the internet, reaching AWS services
through VPC endpoints — traffic never traverses the public internet, and the design carries no
per-hour egress infrastructure. The database is the deliberate exception: it sits in a public
subnet so migrations can run from a developer machine, with its security group restricted to the
single address in `DEV_ACCESS_IP`.

---

## 🛠️ Tech Stack

| Layer | Choice | Why |
|---|---|---|
| API compute | AWS Lambda (Docker image via Mangum) | Pay-per-invocation, zero idle cost, fits FastAPI unchanged |
| API entry point | Amazon API Gateway (REST) | Managed auth (API key + usage plan) without writing an authorizer |
| Vector store | RDS Postgres + pgvector (HNSW index) | One database holds metadata, text, and embeddings — nothing to keep in sync |
| Keyword search | Postgres `pg_trgm` / `~*` regex | No separate search engine for a small corpus |
| Embeddings | Bedrock Titan `amazon.titan-embed-text-v2:0` | AWS-native, cheap, no data leaves AWS |
| LLM | Bedrock `openai.gpt-oss-20b-1:0` | AWS-hosted, pay-per-token, no data leaves AWS |
| Orchestration | LangGraph (ReAct-style loop + `ToolNode`) | Lets the agent decide *how much* retrieval a question needs |
| IaC | AWS CDK (Python), one stack | Readable, reproducible, tears down cleanly |
| Frontend | Streamlit (thin HTTP client) | No retrieval or generation logic in the client |

**Bedrock Knowledge Bases** would have handled retrieval end-to-end but still needs a vector store
underneath, and with pgvector in place a hand-rolled agent gives more control over blending
semantic and keyword evidence. **Bedrock AgentCore** would have hosted the agent with managed
memory and tracing — the natural upgrade path for conversation memory or multiple agents, but more
operational surface than one stateless agent needs. The LLM is `openai.gpt-oss-20b-1:0` rather than
Claude 3 Haiku; both are pay-per-token inside AWS, and swapping is a one-line change to
`LLM_MODEL_ID` in [`backend_stack.py`](infrastructure/backend/backend_stack.py).

---

## 📁 Project Structure

```
backend/            api/ (thin HTTP routes) · domain/ (upload pipeline, agent + scoring)
                    models/ (SQLAlchemy, schema source of truth) · schemas/api/ (Pydantic)
                    services/agent/ (graph, nodes + system prompt, tools, state)
                    infrastructure/ (DB sessions — NOT the CDK app) · config/

frontend/           Streamlit client — api_client.py (HTTP), ui.py (rendering)

infrastructure/     CDK, one stack: network.py, database.py, storage.py, compute.py,
                    api.py, assembled in backend_stack.py

alembic/            Database migrations
Makefile            Deploys, migrations, local dev servers
```

---

## 🚀 Getting Started

**Prerequisites:** Python 3.12, Docker, AWS CLI configured, CDK CLI (`npm install -g aws-cdk`), and
Bedrock model access enabled for both models in your region. Each area keeps its own virtualenv.

### Option A — Run it locally

```bash
docker-compose up -d pgvector    # Postgres + pgvector on :5432
make db-upgrade                  # create extensions, tables, index
make run                         # backend on :8000  (interactive docs at /docs)
make run-streamlit               # Streamlit client on :8501
```

`.env` needs `DATABASE_URL=postgresql+asyncpg://rag_user:rag_password@localhost:5432/rag_db`.
Bedrock calls still go to real AWS and are billed normally, and there is no authentication locally
— the token is enforced by API Gateway, which isn't in the path.

### Option B — Deploy to AWS

```bash
cd infrastructure && python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

cdk bootstrap                                 # once per account/region
export DEV_ACCESS_IP=$(curl -s ifconfig.me)   # required — the DB firewall rule
cdk deploy RagChatBackendStack --require-approval=never
```

Deploy takes 10–15 minutes, mostly RDS, and prints `ApiEndpoint`, `ApiKeyId`, `DatabaseEndpoint`,
`UploadBucketName`, `LambdaFunctionName`. `ApiKeyId` is an identifier, not the token — exchange it
with `aws apigateway get-api-key --api-key <ApiKeyId> --include-value --query value --output text`
and populate `.env.prod` (gitignored). Then create the schema (**migrations do not run
automatically**, and this runs from your machine, which is why `DEV_ACCESS_IP` matters), add
documents, and ask a question:

```bash
make db-upgrade ENV=prod
set -a && source .env.prod && set +a          # API_BASE_URL and API_TOKEN

curl -X POST "$API_BASE_URL/api/upload/" -H "x-api-key: $API_TOKEN" -F "file=@doc.pdf"

curl -s -X POST "$API_BASE_URL/api/query/" \
  -H "x-api-key: $API_TOKEN" -H "Content-Type: application/json" \
  -d '{"question": "What does the knowledge base cover?", "top_k": 5}' | python -m json.tool
```

For the UI: `cd frontend`, install requirements, copy `.streamlit/secrets.toml.example` to
`secrets.toml` with `API_BASE_URL` and `API_TOKEN`, then `streamlit run app.py`.

`make destroy` removes everything; the S3 bucket empties itself and RDS leaves no snapshot. The one
leftover is the database password in Secrets Manager, billed at ~$0.40/month until its recovery
window lapses — `aws secretsmanager delete-secret --force-delete-without-recovery` clears it.

---

## 📡 API Reference

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health/` | Liveness check |
| POST | `/api/upload/` · `/api/upload/batch` | Upload one or several files (`multipart/form-data`) |
| GET | `/api/files/` · `/api/files/{id}` | Document list (`skip`, `limit`) and metadata |
| GET | `/api/files/{id}/download` | Short-lived presigned S3 URL for the original |
| DELETE | `/api/files/{id}` | Delete a document and its chunks |
| POST | `/api/query/` | Ask the knowledge base a question |
| GET | `/api/query/count` | Total indexed chunk count |

Every route requires `x-api-key: <token>`, validated by API Gateway itself, so a request without a
valid key never reaches the Lambda — there is no authentication logic in the application code. The
key is created by CDK and stored in `.env.prod` and `frontend/.streamlit/secrets.toml`, both
gitignored.

`POST /api/query/` takes `question` (required, 1–1000 chars) and `top_k` (1–20, default 5), which
caps how many source passages come back without limiting how much the agent searches internally:

```json
{
  "answer": "Enterprise customers can request a refund within the documented refund window...",
  "sources": [
    { "source": "refund_policy.pdf", "chunk_index": 4,
      "content_preview": "Enterprise refund requests must be reviewed...",
      "similarity_score": 0.91 }
  ],
  "confidence_score": 0.84,
  "confidence_breakdown": { "best_similarity": 0.91, "avg_similarity": 0.84,
    "consistency": 0.93, "keyword_match": 0.62, "final_score": 0.84 },
  "query": "What is the refund policy for enterprise customers?",
  "timestamp": "2026-08-20T10:15:00"
}
```

---

## 🧠 Inside the RAG Pipeline

Splitting is boundary-aware — paragraphs first, then sentences, then words. Embedding calls run 16
at a time with adaptive retries, since Titan embeds one chunk per call and throttles per account.

| Tool | What it does |
|---|---|
| `semantic_search(concept)` | Nearest chunks by cosine distance via the HNSW index — text, filename, similarity, offsets |
| `keyword_search(pattern)` | Case-insensitive regex over document text, guarded by a 5-second statement timeout |
| `list_documents()` | Filenames only, for questions about the corpus itself |
| `read_document(id, start, end)` | A character range of the extracted text, capped at 8000 characters |

The system prompt in `nodes.py` carries most of the behavior worth reviewing: expand every hit
before answering, match search effort to question complexity, never state a confidence figure, and
say plainly where the documents stop covering the question.

Semantic and keyword hits accumulate as the agent works, then fuse per chunk as
`combined = 1 - (1 - keyword) × (1 - semantic)` — the two treated as independent evidence, so the
score is the complement of both being wrong at once. A passage both searches agree on scores higher
than under either alone (0.80 and 0.70 fuse to 0.94); anything at or below 0.2 is noise and
dropped. **Confidence** is derived entirely from retrieval, never asked of the model: best
similarity, average, consistency (`1 - (best - min)`), and keyword strength. It signals that
retrieval went well, not that the answer is correct.

---

## 📚 Sample Documents & Seeding

Seed through the Streamlit uploader or `POST /api/upload/` — the same pipeline either way. The
documents used during development are ML papers rather than the business-style set (refund policy,
FAQ, handbook) the brief's example query implies; before a review demo, place 3–5 short business
documents in a `sample-docs/` folder and upload them.

---

## 🔐 Security

- **API boundary** — API key + usage plan on every route. Nothing is publicly callable.
- **Network** — the Lambda has no internet route, reaching AWS services through VPC endpoints only;
  the database is firewalled to a single IP.
- **Secrets** — the database password is generated by CDK into Secrets Manager and read at startup,
  never in source or an environment variable. `.env`, `.env.prod`, `secrets.toml` are gitignored.
- **IAM** — the Lambda's role is scoped to `bedrock:InvokeModel` on exactly the two model ARNs it
  uses, read on one secret, read/write on one bucket. No wildcard grants.
- **Data residency** — every model call goes to Bedrock inside your own account, and all content
  stays in your RDS instance. Nothing calls a non-AWS service.

---

## 💸 Cost Notes (sandbox account, $20 budget)

| Resource | Ongoing cost driver |
|---|---|
| Lambda, API Gateway, S3 gateway endpoint | Pay-per-use — $0 idle |
| RDS `db.t4g.micro`, 20GB | ~$12–13/month if left running |
| 2× VPC interface endpoints across 2 AZs | ~$14–15/month if left running |
| Bedrock (embeddings + LLM) | Pay-per-token, near-zero at demo volume |
| Secrets Manager | ~$0.40/month per secret |

RDS and the interface endpoints bill hourly regardless of traffic and together approach the $20
budget within a month — **run `make destroy` when evaluation is done**.

---

## 📎 Evidence of Execution

*(Template — attach after a real run: the Streamlit question, the API request, the JSON response,
and a screenshot or the relevant CloudWatch log lines.)*

---

## ⚠️ Assumptions & Known Limitations

- **Migrations aren't automatic** — a fresh deploy leaves an empty database until `make db-upgrade
  ENV=prod` runs against it.
- **there is no conversation memory**, so follow-ups don't resolve against
  earlier turns.
- **CORS is open** to all origins, and **RDS is publicly reachable** (locked to a single IP) rather
  than fully private.

---

## 🏭 Productionization — What I'd Change for Real Use

The architecture is already the shape a production system would take — serverless compute behind a
managed gateway, one database, infrastructure as code, secrets never in source. Before it carried
real traffic it would need:

- **Security** — RDS fully private with migrations run from inside the VPC; a Lambda authorizer
  (JWT/Cognito) in place of the shared API key once per-user identity matters; CORS scoped to the
  real frontend origin.
- **Reliability and cost** — a cap on agent tool-call iterations so a pathological question can't
  run past the gateway ceiling; the double retry (three attempts around a graph that itself retries
  each node three times) collapsed into one bounded layer; the usage plan's throttle and quota set.
- **Observability** — a request id generated at the API boundary, propagated through logs and into
  the response, plus structured JSON logs and alarms on failure rate, p99 latency, and RDS
  connections.
- **Scaling** — two ceilings bite first: RDS connection limits, since Lambda scales out faster than
  a `t4g.micro` accepts connections (RDS Proxy solves it), and Bedrock's per-account throttle. A
  larger corpus would need HNSW tuning and a re-embedding strategy for model upgrades.
