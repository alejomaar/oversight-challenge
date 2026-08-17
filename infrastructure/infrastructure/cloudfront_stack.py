from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
)
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_certificatemanager as acm
from constructs import Construct


class CloudFrontStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, s3_bucket: s3.Bucket, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create CloudFront distribution pointing to S3 bucket
        distribution = cloudfront.Distribution(
            self,
            "FrontendDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(s3_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                compress=True,
            ),
            # Redirect index.html for root and nested paths
            additional_behaviors={
                "/": cloudfront.BehaviorOptions(
                    origin=origins.S3Origin(s3_bucket),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                    compress=True,
                )
            },
            # Default root object
            default_root_object="index.html",
            # Custom error responses for SPA routing
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(5),
                )
            ],
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

        self.distribution = distribution
