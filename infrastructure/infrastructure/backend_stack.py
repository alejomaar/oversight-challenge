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

        vpc = ec2.Vpc(
            self,
            "Vpc",
            vpc_name="main-vpc",
            max_azs=1,
            nat_gateways=1,
        )

        upload_bucket = s3.Bucket(
            self,
            "UploadBucket",
            bucket_name="oversight-app",
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        s3files_role = iam.Role(
            self,
            "S3FilesRole",
            role_name="s3files-mount-role",
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

        sg = ec2.SecurityGroup(
            self,
            "MountTargetSG",
            security_group_name="mount-target-sg",
            vpc=vpc,
            allow_all_outbound=True,
        )

        s3files.CfnMountTarget(
            self,
            "MountTarget",
            file_system_id=file_system.attr_file_system_id,
            subnet_id=vpc.private_subnets[0].subnet_id,
            security_groups=[sg.security_group_id],
        )

        access_point = s3files.CfnAccessPoint(
            self,
            "AccessPoint",
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

        lambda_function = lambda_.DockerImageFunction(
            self,
            "Function",
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
            environment={
                "UPLOAD_DIR": "/mnt/s3",
            },
        )

        lambda_function.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")
        )

        api = apigw.RestApi(
            self,
            "Api",
            rest_api_name="backend-api",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["*"],
            ),
        )

        api.root.add_proxy(
            default_integration=apigw.LambdaIntegration(lambda_function),
            any_method=True,
        )

        CfnOutput(self, "ApiEndpoint", value=api.url)
        CfnOutput(self, "LambdaFunctionName", value=lambda_function.function_name)
        CfnOutput(self, "UploadBucketName", value=upload_bucket.bucket_name)

        self.api = api
        self.lambda_function = lambda_function
        self.upload_bucket = upload_bucket
