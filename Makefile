# Select env file with ENV=prod (defaults to local .env). Example:
#   make db-upgrade ENV=prod
ENV ?= local
ifeq ($(ENV),prod)
ENV_FILE := .env.prod
else
ENV_FILE := .env
endif

-include $(ENV_FILE)
export

# Docker targets
build:
	@echo "Building Docker containers..."
	docker-compose build

up: $(ENV_FILE)
	@echo "Starting Docker containers with $(ENV_FILE) configuration..."
	docker-compose up -d
	@echo "Backend: http://localhost:8000"
	@echo "Frontend: http://localhost:3000"

down:
	@echo "Stopping Docker containers..."
	docker-compose down

logs:
	docker-compose logs -f


# CDK Deployment targets
synth:
	@echo "Synthesizing all stacks..."
	cd infrastructure && . .venv/bin/activate && cdk synth

deploy-backend:
	@echo "Deploying backend stack to AWS..."
	cd infrastructure && . .venv/bin/activate && \
	cdk deploy RagChatBackendStack --require-approval=never
	@echo "Backend deployment complete!"

destroy:
	@echo "Tearing down all stacks..."
	cd infrastructure && . .venv/bin/activate && cdk destroy --all --force
	@echo "Teardown complete. Verify no S3 buckets or RDS snapshots remain."

# Database migrations (Alembic). The same migration also runs automatically
# at Lambda cold start in AWS, so these targets are mainly for local dev and
# for applying migrations ahead of a deploy (ENV=prod).
db-upgrade:
	@echo "Running Alembic migrations ($(ENV_FILE))..."
	. backend/.venv/bin/activate && alembic upgrade head

db-downgrade:
	@echo "Reverting last Alembic migration ($(ENV_FILE))..."
	. backend/.venv/bin/activate && alembic downgrade -1

db-revision:
	@echo "Creating new Alembic revision..."
	. backend/.venv/bin/activate && alembic revision -m "$(msg)"

# Local development server
run:
	@echo "Starting backend dev server with auto-reload..."
	cd backend && . .venv/bin/activate && uvicorn app:app --reload --host 0.0.0.0 --port 8000

run-streamlit:
	@echo "Starting Streamlit client..."
	cd frontend && . .venv/bin/activate && streamlit run app.py
