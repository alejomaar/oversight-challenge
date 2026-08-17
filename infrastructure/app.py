#!/usr/bin/env python3
import os

import aws_cdk as cdk

from infrastructure.infrastructure_stack import InfrastructureStack
from infrastructure.cloudfront_stack import CloudFrontStack


app = cdk.App()

# Create infrastructure stack (S3, IAM, Amplify)
infra_stack = InfrastructureStack(app, "InfrastructureStack",
    env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),
    # For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html
)

# Create CloudFront distribution stack pointing to S3 bucket
# This runs after infrastructure stack to reference the S3 bucket
cloudfront_stack = CloudFrontStack(
    app,
    "CloudFrontStack",
    s3_bucket=infra_stack.hosting_bucket,
    env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),
)
cloudfront_stack.add_dependency(infra_stack)

app.synth()
