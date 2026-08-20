from aws_cdk import Duration, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_rds as rds
from aws_cdk import aws_s3 as s3

from config.settings import DB_NAME, PROJECT_ROOT, resource_name


def add_query_handler(
    stack: Stack,
    *,
    vpc: ec2.Vpc,
    database: rds.DatabaseInstance,
    upload_bucket: s3.Bucket,
    embeddings_model_id: str,
    llm_model_id: str,
) -> lambda_.DockerImageFunction:
    """The Lambda behind the API: document ingestion and RAG query handling."""

    function = lambda_.DockerImageFunction(
        stack,
        "QueryHandler",

        function_name=resource_name("lambda"),

        code=lambda_.DockerImageCode.from_image_asset(
            directory=PROJECT_ROOT,
            platform=ecr_assets.Platform.LINUX_AMD64,
        ),

        memory_size=1024,

        timeout=Duration.minutes(3),

        vpc=vpc,

        vpc_subnets=ec2.SubnetSelection(
            subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
        ),

        environment={
            # No password here - the function reads the secret at cold start.
            "DB_SECRET_ARN": database.secret.secret_arn,
            "DB_HOST": database.db_instance_endpoint_address,
            "DB_PORT": database.db_instance_endpoint_port,
            "DB_NAME": DB_NAME,

            "S3_BUCKET_NAME": upload_bucket.bucket_name,

            "BEDROCK_EMBEDDINGS_MODEL_ID": embeddings_model_id,
            "BEDROCK_LLM_MODEL_ID": llm_model_id,
        },
    )

    # IAM - scoped to the resources it actually uses
    database.connections.allow_default_port_from(function)
    database.secret.grant_read(function)
    upload_bucket.grant_read_write(function)

    function.add_to_role_policy(
        iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[
                stack.format_arn(
                    service="bedrock",
                    account="",
                    resource="foundation-model",
                    resource_name=model_id,
                )
                for model_id in (embeddings_model_id, llm_model_id)
            ],
        )
    )

    return function
