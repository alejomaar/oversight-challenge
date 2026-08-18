import os

from aws_cdk import (
    BundlingOptions,
    CfnOutput,
    DockerImage,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from constructs import Construct


class FrontendStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        api_url = self.node.try_get_context("apiUrl") or "https://api-not-configured.example.com"

        frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "frontend")

        hosting_bucket = s3.Bucket(
            self,
            "HostingBucket",
            bucket_name=f"rag-chat-frontend-hosting-{self.account}",
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=True,
                block_public_policy=True,
                ignore_public_acls=True,
                restrict_public_buckets=True,
            ),
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        hosting_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="CloudFrontAccess",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
                actions=["s3:GetObject"],
                resources=[hosting_bucket.arn_for_objects("*")],
            )
        )

        oai = cloudfront.OriginAccessIdentity(
            self,
            "OAI",
            comment="rag-chat-frontend-oai",
        )

        distribution = cloudfront.Distribution(
            self,
            "Distribution",
            comment="rag-chat-frontend-distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(hosting_bucket, origin_access_identity=oai),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                compress=True,
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(5),
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(5),
                ),
            ],
        )

        s3deploy.BucketDeployment(
            self,
            "DeployFrontend",
            sources=[
                s3deploy.Source.asset(
                    frontend_dir,
                    bundling=BundlingOptions(
                        image=DockerImage.from_registry("node:20-slim"),
                        command=[
                            "bash",
                            "-c",
                            f"npm ci && NEXT_PUBLIC_API_URL={api_url} npm run build && cp -r out/* /asset-output/",
                        ],
                    ),
                )
            ],
            destination_bucket=hosting_bucket,
            distribution=distribution,
            distribution_paths=["/*"],
        )

        CfnOutput(self, "CloudFrontUrl", value=f"https://{distribution.domain_name}")
        CfnOutput(self, "CloudFrontDistributionId", value=distribution.distribution_id)

        self.hosting_bucket = hosting_bucket
        self.distribution = distribution
