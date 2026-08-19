import os
import string

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_rds as rds


def add_database(stack: Stack, vpc: ec2.Vpc) -> rds.DatabaseInstance:
    """RDS PostgreSQL instance, publicly reachable only from DEV_ACCESS_IP."""

    subnet_group = rds.SubnetGroup(
        stack,
        "PublicSubnetGroup",
        vpc=vpc,
        vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        description="Public subnets for direct dev access to the database",
    )

    database = rds.DatabaseInstance(
        stack,
        "Database",

        engine=rds.DatabaseInstanceEngine.postgres(
            version=rds.PostgresEngineVersion.VER_16,
        ),

        database_name="rag_db",

        instance_identifier="rag-chat-db",

        credentials=rds.Credentials.from_generated_secret(
            "rag_user",
            exclude_characters=string.punctuation.replace("_", ""),
        ),

        instance_type=ec2.InstanceType.of(
            ec2.InstanceClass.BURSTABLE4_GRAVITON,
            ec2.InstanceSize.MICRO,
        ),

        vpc=vpc,

        subnet_group=subnet_group,

        publicly_accessible=True,

        allocated_storage=20,
        storage_encrypted=True,
        multi_az=False,

        backup_retention=Duration.days(0),
        deletion_protection=False,
        removal_policy=RemovalPolicy.DESTROY,
    )

    database.connections.allow_default_port_from(
        ec2.Peer.ipv4(f"{os.environ['DEV_ACCESS_IP']}/32"),
        "Local dev access to Postgres",
    )

    database.node.add_dependency(vpc.internet_connectivity_established)

    return database
