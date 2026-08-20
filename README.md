# 📚 Knowledge Base AI Agent — AWS-Native

A **Knowledge Base AI Agent** that lets you upload documents (PDF, Word, or plain text), builds a
searchable knowledge base out of them, and answers questions about their contents — with the
sources it used and how confident it is in the answer, so nothing is ever just made up. It runs
entirely on AWS, and a small local Streamlit app is the chat window you talk to it through.

## ✨ Key Features

- 📄 **Upload PDF, Word, or plain text** — duplicate uploads rejected automatically.
- 🔍 **Search by meaning and keywords** — semantic search for paraphrased questions, keyword search for exact names and codes.
- 🤖 **Searches like a person would** — it decides how much digging a question needs and reads the full passage around anything it finds.
- 📊 **Shows its work** — every answer carries the passages it was built from and a confidence score with its breakdown.
- 🔐 **Locked behind an access token**, deployed and torn down with one command, and costing nothing while idle.

---

## 🧭 How It Works

**Ingestion.** A file is uploaded to the API, split into chunks, and stored in Postgres. The
original goes to S3 untouched. Each file is hashed by content, so an identical re-upload is
rejected as a duplicate.

**Query.** Agentic RAG. The agent has four tools — semantic search, keyword search, list documents,
and read document — and can reason across several rounds of them before answering.

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



## 🧱 Architecture 

Four decisions determine how far this design carries beyond a demo.

### Postgres as the retrieval layer

Document metadata, chunk text, and embeddings live in one database and are written in one
transaction: a document and its chunks either both commit or neither does. Retrieval reads that
same data, so a result cannot reference a document that no longer exists.

All retrieval happens in Postgres. The same database serves ordinary CRUD over documents and chunks
and acts as the semantic layer that ranks them. Scaling it is a resource change on the instance,
and changing its shape is an Alembic migration.

The indexes are in place: HNSW with `vector_cosine_ops` on `chunk.embedding`, so similarity search
does not scan every row once the table holds thousands of vectors, and a trigram index on document
text so `keyword_search`'s regex is indexed rather than scanned. Restricting ranking to one user,
one domain, or a chosen set of documents is a `WHERE` clause.



### Lambda as a container image

Container packaging raises the artifact limit from 250 MB unzipped to 10 GB. Memory is
128 MB–10,240 MB in both cases and is unaffected by packaging. The larger limit is what
accommodates LangGraph, LangChain, SQLAlchemy, asyncpg, pypdf, python-docx and boto3 together. One
Dockerfile produces both the docker-compose container and the deployed artifact, so local and
deployed behaviour derive from the same image

### S3 for original files

Original files are stored untouched under `raw/{document_id}/`, and their metadata stays in
Postgres. Each upload is hashed by content, so the same document is never stored twice.

### Alembic for schema changes

Each schema change is a versioned file: reviewable, reversible, and applied to every environment in
the same order. The data model changes without manual DDL, and queries go through the ORM with
bound parameters.

---

## 📁 Project Structure

```
.
├── backend/              FastAPI service
│   ├── api/              HTTP routes
│   ├── domain/           upload pipeline, search
│   ├── models/           SQLAlchemy tables
│   ├── schemas/api/      Pydantic request/response
│   ├── services/agent/   LangGraph agent, tools
│   ├── infrastructure/   DB sessions (not the CDK app)
│   └── config/           settings
├── frontend/             Streamlit client
├── infrastructure/       CDK, one stack
│   └── backend/          network, database, storage, compute, api
├── alembic/              migrations
└── Makefile              deploys, migrations, dev servers
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

### Option B — Deploy to AWS



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

Every route requires `x-api-key: <token>`, validated by API Gateway itself

---

## 🧠 Inside the RAG Pipeline


| Tool | What it does |
|---|---|
| `semantic_search(concept)` | Search similar chunk by meaning |
| `keyword_search(pattern)` | Case-insensitive regex over document text
| `list_documents()` | Filenames only, for questions about the corpus itself |
| `read_document(id, start, end)` | A character range of the extracted text, capped at 8000 characters |


It uses the idea of P(A or B) = 1 - (1-A)(1-B) so both scorins are complementnary then 
`combined = 1 - (1 - keyword) × (1 - semantic)` 

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
| Bedrock (embeddings + LLM) | Pay-per-token, near-zero at demo volume |



---

## 📎 Evidence of Execution

*(Template — attach after a real run: the Streamlit question, the API request, the JSON response,
and a screenshot or the relevant CloudWatch log lines.)*


---

## 🏭 Productionization

I would change:

- **RDS private** — move it into the isolated subnets so nothing reaches it from the internet, and
  run migrations from inside the VPC instead of whitelisting a developer IP.
- **Cognito login** — no shared API key; a per-user JWT validated by a Lambda authorizer, so every
  request carries an identity and documents can be scoped to their owner.
- **Presigned S3 upload** — the client PUTs straight to S3 instead of streaming through the API,
  lifting API Gateway's 10 MB payload cap and the Lambda timeout out of the upload path.
- **Scale RDS** — a larger instance plus RDS Proxy, since Lambda scales out faster than a
  `t4g.micro` accepts connections.
- **Add LangSmith** — traces of every agent run: which tools fired, what they returned, and where
  the latency and tokens went.
