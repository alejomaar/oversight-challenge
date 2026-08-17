import os

from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
)
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3files as s3files
from constructs import Construct


class BackendStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        project_root = os.path.join(os.path.dirname(__file__), "..", "..", "backend")

        # VPC for S3 Files mount targets
        vpc = ec2.Vpc(self, "LambdaVpc", max_azs=2)

        # S3 bucket for document uploads (versioning required for S3 Files)
        upload_bucket = s3.Bucket(
            self,
            "UploadBucket",
            bucket_name=f"kb-rag-uploads-{self.account}",
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        s3files_role = iam.Role(
            self,
            "S3FilesRole",
            assumed_by=iam.ServicePrincipal("elasticfilesystem.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")
            ],
        )

        file_system = s3files.CfnFileSystem(
            self,
            "S3FileSystem",
            bucket=upload_bucket.bucket_arn,
            role_arn=s3files_role.role_arn,
        )

        # Security group for S3 Files mount targets
        sg = ec2.SecurityGroup(
            self,
            "S3FilesSG",
            vpc=vpc,
            allow_all_outbound=True,
        )
        sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.all_traffic())

        for i, subnet in enumerate(vpc.private_subnets):
            s3files.CfnMountTarget(
                self,
                f"S3FilesMountTarget{i}",
                file_system_id=file_system.attr_file_system_id,
                subnet_id=subnet.subnet_id,
                security_groups=[sg.security_group_id],
            )

        access_point = s3files.CfnAccessPoint(
            self,
            "S3FilesAccessPoint",
            file_system_id=file_system.attr_file_system_id,
            root_directory=s3files.CfnAccessPoint.RootDirectoryProperty(
                path="/",
                creation_permissions=s3files.CfnAccessPoint.CreationPermissionsProperty(
                    owner_uid="0",
                    owner_gid="0",
                    permissions="777",
                ),
            ),
            posix_user=s3files.CfnAccessPoint.PosixUserProperty(
                uid="0",
                gid="0",
            ),
        )

        # Lambda function with Docker image from backend/
        lambda_function = lambda_.DockerImageFunction(
            self,
            "RagBackendFunction",
            function_name="kb-rag-backend",
            code=lambda_.DockerImageCode.from_image_asset(
                directory=project_root,
                platform=ecr_assets.Platform.LINUX_AMD64,
            ),
            memory_size=512,
            timeout=Duration.seconds(60),
            vpc=vpc,
            filesystem=lambda_.FileSystem.from_s3_files_access_point(
                access_point,
                "/mnt/s3",
            ),
            description="Knowledge Base RAG API Backend (FastAPI + Mangum)",
        )

        lambda_function.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")
        )

        # API Gateway
        api = apigw.RestApi(
            self,
            "RagApi",
            rest_api_name="Knowledge-Base-RAG-API",
            description="REST API for Knowledge Base RAG backend",
        )

        integration = apigw.LambdaIntegration(lambda_function)

        # Root endpoint
        api.root.add_method("GET", integration)
        api.root.add_method("POST", integration)

        # /api resource
        api_resource = api.root.add_resource("api")

        # /api/upload endpoint
        upload_resource = api_resource.add_resource("upload")
        upload_resource.add_method("POST", integration)
        upload_resource.add_method("GET", integration)

        # /api/upload/batch endpoint
        batch_resource = upload_resource.add_resource("batch")
        batch_resource.add_method("POST", integration)

        # /api/query endpoint
        query_resource = api_resource.add_resource("query")
        query_resource.add_method("POST", integration)

        # /api/files endpoint
        files_resource = api_resource.add_resource("files")
        files_resource.add_method("GET", integration)
        files_resource.add_method("POST", integration)

        # /api/files/{file_id} endpoint
        file_id_resource = files_resource.add_resource("{file_id}")
        file_id_resource.add_method("GET", integration)
        file_id_resource.add_method("DELETE", integration)

        # /api/health endpoint
        health_resource = api_resource.add_resource("health")
        health_resource.add_method("GET", integration)

        # /api/health/detailed endpoint
        health_detailed_resource = health_resource.add_resource("detailed")
        health_detailed_resource.add_method("GET", integration)

        CfnOutput(
            self,
            "ApiEndpoint",
            value=api.url,
            description="API Gateway endpoint URL",
            export_name="ApiEndpoint",
        )

        CfnOutput(
            self,
            "LambdaFunctionName",
            value=lambda_function.function_name,
            description="Lambda function name",
            export_name="LambdaFunctionName",
        )

        CfnOutput(
            self,
            "UploadBucketName",
            value=upload_bucket.bucket_name,
            description="S3 bucket for document uploads",
            export_name="UploadBucketName",
        )

        self.api = api
        self.lambda_function = lambda_function
        self.upload_bucket = upload_bucket
