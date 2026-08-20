#!/usr/bin/env python3
import aws_cdk as cdk
from aws_cdk import Tags

from backend.backend_stack import BackendStack
from config.settings import AWS_ACCOUNT, AWS_REGION


app = cdk.App()

env = cdk.Environment(account=AWS_ACCOUNT, region=AWS_REGION)

BackendStack(app, "BackendStack", env=env)

Tags.of(app).add("project", "rag-chat")

app.synth()
