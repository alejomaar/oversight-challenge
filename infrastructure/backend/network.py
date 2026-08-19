from aws_cdk import Stack
from aws_cdk import aws_ec2 as ec2


def add_network(stack: Stack) -> ec2.Vpc:
    """Isolated-subnet VPC with no NAT gateway, the single largest idle cost
    in a setup like this. Services are reached through VPC endpoints instead.

    A public subnet (and its Internet Gateway) is included only so the
    database can be reached directly for local development; it carries no
    idle cost on its own since there's no NAT gateway behind it.
    """

    vpc = ec2.Vpc(
        stack,
        "Vpc",

        vpc_name="rag-chat-vpc",

        max_azs=2,

        nat_gateways=0,

        subnet_configuration=[
            ec2.SubnetConfiguration(
                name="isolated",
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                cidr_mask=24,
            ),
            ec2.SubnetConfiguration(
                name="public",
                subnet_type=ec2.SubnetType.PUBLIC,
                cidr_mask=24,
            ),
        ],
    )

    # S3 goes through a gateway endpoint, which is free.
    vpc.add_gateway_endpoint(
        "S3Endpoint",
        service=ec2.GatewayVpcEndpointAwsService.S3,
    )

    # Bedrock and Secrets Manager need interface endpoints.
    vpc.add_interface_endpoint(
        "BedrockRuntimeEndpoint",
        service=ec2.InterfaceVpcEndpointAwsService.BEDROCK_RUNTIME,
    )

    vpc.add_interface_endpoint(
        "SecretsManagerEndpoint",
        service=ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
    )

    return vpc
