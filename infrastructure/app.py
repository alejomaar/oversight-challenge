#!/usr/bin/env python3
import os

import aws_cdk as cdk

from infrastructure.backend_stack import BackendStack
from infrastructure.frontend_stack import FrontendStack


app = cdk.App()

env = cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION'))

# Backend: Lambda (Docker) + API Gateway + S3 Files (deploy first)
backend_stack = BackendStack(app, "BackendStack", env=env)

# Frontend: S3 + CloudFront (with backend API URL from backend stack)
frontend_stack = FrontendStack(
    app,
    "FrontendStack",
    backend_api_url=backend_stack.api.url,
    env=env
)

# Frontend depends on backend being deployed
frontend_stack.add_dependency(backend_stack)

app.synth()
