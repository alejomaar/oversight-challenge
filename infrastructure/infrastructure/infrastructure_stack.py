from aws_cdk import (
    Stack,
    CfnOutput,
    RemovalPolicy,
)
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_iam as iam
from constructs import Construct


class InfrastructureStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create S3 bucket for CloudFront origin
        self.hosting_bucket = s3.Bucket(
            self,
            "HostingBucket",
            bucket_name=f"kb-rag-frontend-{self.account}",
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=False,
                block_public_policy=False,
                ignore_public_acls=False,
                restrict_public_buckets=False,
            ),
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # Enable public read access for CloudFront
        self.hosting_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="PublicRead",
                effect=iam.Effect.ALLOW,
                principals=[iam.AnyPrincipal()],
                actions=["s3:GetObject"],
                resources=[self.hosting_bucket.arn_for_objects("*")],
            )
        )

        CfnOutput(
            self,
            "S3BucketName",
            value=self.hosting_bucket.bucket_name,
            description="S3 bucket for CloudFront origin",
        )

        CfnOutput(
            self,
            "S3BucketArn",
            value=self.hosting_bucket.bucket_arn,
            description="S3 bucket ARN",
        )
