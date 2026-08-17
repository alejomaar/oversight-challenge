#!/usr/bin/env python3
import os

import aws_cdk as cdk

from infrastructure.backend_stack import BackendStack
from infrastructure.frontend_stack import FrontendStack


app = cdk.App()

env = cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION'))

# Frontend: S3 + CloudFront
frontend_stack = FrontendStack(app, "FrontendStack", env=env)

# Backend: Lambda (Docker) + API Gateway + S3 Files
backend_stack = BackendStack(app, "BackendStack", env=env)

app.synth()
