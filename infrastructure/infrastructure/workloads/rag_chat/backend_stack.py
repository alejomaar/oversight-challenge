import string
from pathlib import Path

from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
    RemovalPolicy,
)
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_rds as rds
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3files as s3files
from constructs import Construct


class BackendStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        root_folder = (Path(__file__).parent / ".." / ".." / ".." / "..").resolve()
        project_root = str(root_folder / "backend")

        # ---------------------------------------------------------
        # Network (looked up, not referenced across stacks)
        # ---------------------------------------------------------

        vpc_id = self.node.get_context("vpcId")
        mount_sg_id = self.node.get_context("mountSecurityGroupId")

        vpc = ec2.Vpc.from_lookup(self, "Vpc", vpc_id=vpc_id)
        mount_security_group = ec2.SecurityGroup.from_security_group_id(
            self, "MountAccessSecurityGroup", mount_sg_id,
        )

        # ---------------------------------------------------------
        # RDS PostgreSQL - PUBLIC
        # ---------------------------------------------------------

        database = rds.DatabaseInstance(
            self,
            "Database",

            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16,
            ),

            database_name="rag_db",

            credentials=rds.Credentials.from_generated_secret(
                "rag_user",
                exclude_characters=string.punctuation.replace("_", ""),
            ),

            instance_identifier="rag-chat-document-store",

            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE4_GRAVITON,
                ec2.InstanceSize.MICRO,
            ),

            vpc=vpc,

            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PUBLIC,
            ),

            publicly_accessible=True,

            allocated_storage=20,
            storage_encrypted=True,
            multi_az=False,

            backup_retention=Duration.days(0),
            deletion_protection=False,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ---------------------------------------------------------
        # S3 Upload Bucket
        # ---------------------------------------------------------

        upload_bucket = s3.Bucket(
            self,
            "UploadBucket",

            bucket_name="rag-chat-document-bucket",

            versioned=True,

            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,

            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # ---------------------------------------------------------
        # S3 Files Role
        # ---------------------------------------------------------

        s3files_role = iam.Role(
            self,
            "S3MountRole",

            role_name="rag-chat-document-storage-access",

            assumed_by=iam.ServicePrincipal(
                "elasticfilesystem.amazonaws.com"
            ),

            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AdministratorAccess"
                )
            ],
        )

        # ---------------------------------------------------------
        # S3 File System
        # ---------------------------------------------------------

        file_system = s3files.CfnFileSystem(
            self,
            "S3FileSystem",

            bucket=upload_bucket.bucket_arn,
            role_arn=s3files_role.role_arn,
        )

        # ---------------------------------------------------------
        # S3 File System Mount Targets
        # ---------------------------------------------------------

        for index, subnet in enumerate(vpc.private_subnets):
            s3files.CfnMountTarget(
                self,
                f"S3MountTarget{index + 1}",

                file_system_id=file_system.attr_file_system_id,

                subnet_id=subnet.subnet_id,

                security_groups=[
                    mount_security_group.security_group_id
                ],
            )

        # ---------------------------------------------------------
        # S3 Files Access Point
        # ---------------------------------------------------------

        access_point = s3files.CfnAccessPoint(
            self,
            "S3AccessPoint",

            file_system_id=file_system.attr_file_system_id,

            root_directory=s3files.CfnAccessPoint.RootDirectoryProperty(
                path="/",

                creation_permissions=(
                    s3files.CfnAccessPoint.CreationPermissionsProperty(
                        owner_uid="0",
                        owner_gid="0",
                        permissions="777",
                    )
                ),
            ),

            posix_user=s3files.CfnAccessPoint.PosixUserProperty(
                uid="0",
                gid="0",
            ),
        )

        # ---------------------------------------------------------
        # Lambda
        # ---------------------------------------------------------

        lambda_function = lambda_.DockerImageFunction(
            self,
            "QueryHandler",

            function_name="rag-chat-app",

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

                "DATABASE_URL": (
                    "postgresql+asyncpg://rag_user:"
                    f"{database.secret.secret_value_from_json('password').unsafe_unwrap()}"
                    "@"
                    f"{database.db_instance_endpoint_address}:"
                    f"{database.db_instance_endpoint_port}"
                    "/rag_db"
                ),
            },
        )

        # ---------------------------------------------------------
        # S3 Files Mount Security Group
        # ---------------------------------------------------------

        # Lambda -> S3 Files mount targets
        mount_security_group.connections.allow_from(
            lambda_function,
            ec2.Port.all_traffic(),
        )

        # ---------------------------------------------------------
        # RDS Security Group
        # ---------------------------------------------------------

        # Lambda -> PostgreSQL
        database.connections.allow_default_port_from(
            lambda_function
        )

        # Internet -> PostgreSQL
        database.connections.allow_from(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(5432),
        )

        # Lambda -> Secrets Manager
        database.secret.grant_read(
            lambda_function
        )

        # ---------------------------------------------------------
        # Lambda IAM
        # ---------------------------------------------------------

        lambda_function.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AdministratorAccess"
            )
        )

        # ---------------------------------------------------------
        # API Gateway
        # ---------------------------------------------------------

        api = apigw.RestApi(
            self,
            "Api",

            rest_api_name="rag-chat-api",

            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["*"],
            ),
        )

        api.root.add_proxy(
            default_integration=apigw.LambdaIntegration(
                lambda_function
            ),
            any_method=True,
        )

        # ---------------------------------------------------------
        # Outputs
        # ---------------------------------------------------------

        CfnOutput(self, "ApiEndpoint", value=api.url)

        CfnOutput(self, "LambdaFunctionName", value=lambda_function.function_name)

        CfnOutput(self, "UploadBucketName", value=upload_bucket.bucket_name)

        CfnOutput(self, "DatabaseEndpoint", value=database.db_instance_endpoint_address)

        # ---------------------------------------------------------
        # References
        # ---------------------------------------------------------

        self.api = api
        self.lambda_function = lambda_function
        self.upload_bucket = upload_bucket
