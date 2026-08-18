#!/usr/bin/env python3
import os

import aws_cdk as cdk
from aws_cdk import Tags

from infrastructure.shared.network_stack import NetworkStack
from infrastructure.workloads.rag_chat.backend_stack import BackendStack
from infrastructure.workloads.rag_chat.frontend_stack import FrontendStack


app = cdk.App()

env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION"),
)

network_stack = NetworkStack(app, "SharedNetworkStack", env=env)
backend_stack = BackendStack(app, "RagChatBackendStack", env=env)
frontend_stack = FrontendStack(app, "RagChatFrontendStack", env=env)

Tags.of(app).add("project", "challenge")

app.synth()
