from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_s3 as s3


def add_upload_bucket(stack: Stack) -> s3.Bucket:
    """Holds the original uploaded files. Extracted text, chunks and
    embeddings live in Postgres, which is what the agent tools read.
    """

    return s3.Bucket(
        stack,
        "UploadBucket",

        bucket_name="rag-chat-document-bucket",

        versioned=True,

        block_public_access=s3.BlockPublicAccess.BLOCK_ALL,

        removal_policy=RemovalPolicy.DESTROY,
        auto_delete_objects=True,
    )
