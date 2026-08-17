import os
import subprocess
from aws_cdk import (
    Stack,
    CfnOutput,
    RemovalPolicy,
    Duration,
)
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3_deployment as s3deploy
from constructs import Construct


class FrontendStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, backend_api_url: str = None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")

        # Create S3 bucket for CloudFront origin
        hosting_bucket = s3.Bucket(
            self,
            "HostingBucket",
            bucket_name=f"kb-rag-frontend-{self.account}",
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=True,
                block_public_policy=True,
                ignore_public_acls=True,
                restrict_public_buckets=True,
            ),
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # CloudFront can access the bucket
        hosting_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="CloudFrontAccess",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
                actions=["s3:GetObject"],
                resources=[hosting_bucket.arn_for_objects("*")],
            )
        )

        # Create CloudFront distribution with OAI
        oai = cloudfront.OriginAccessIdentity(
            self,
            "OAI",
            comment="OAI for frontend bucket"
        )

        # Create CloudFront distribution
        distribution = cloudfront.Distribution(
            self,
            "FrontendDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(
                    hosting_bucket,
                    origin_access_identity=oai
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                compress=True,
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(5),
                )
            ],
        )

        # Deploy exported frontend to S3 with CloudFront invalidation
        s3deploy.BucketDeployment(
            self,
            "DeployFrontend",
            sources=[s3deploy.Source.asset(
                os.path.join(frontend_dir, "out")
            )],
            destination_bucket=hosting_bucket,
            distribution=distribution,
            distribution_paths=["/*"],
        )

        CfnOutput(
            self,
            "S3BucketName",
            value=hosting_bucket.bucket_name,
            description="S3 bucket for CloudFront origin",
            export_name="S3BucketName",
        )

        CfnOutput(
            self,
            "CloudFrontDomainName",
            value=distribution.domain_name,
            description="CloudFront distribution domain name",
            export_name="CloudFrontDomainName",
        )

        CfnOutput(
            self,
            "CloudFrontDistributionId",
            value=distribution.distribution_id,
            description="CloudFront distribution ID",
            export_name="CloudFrontDistributionId",
        )

        CfnOutput(
            self,
            "CloudFrontUrl",
            value=f"https://{distribution.domain_name}",
            description="CloudFront distribution URL (HTTPS)",
            export_name="CloudFrontUrl",
        )

        self.hosting_bucket = hosting_bucket
        self.distribution = distribution
