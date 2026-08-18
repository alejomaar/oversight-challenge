from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_ec2 as ec2
from constructs import Construct


class NetworkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---------------------------------------------------------
        # VPC
        # ---------------------------------------------------------

        vpc = ec2.Vpc(
            self,
            "Vpc",
            vpc_name="network-vpc",
            max_azs=2,
            nat_gateways=1,
        )

        # ---------------------------------------------------------
        # Security Group for storage mount targets
        # ---------------------------------------------------------

        mount_security_group = ec2.SecurityGroup(
            self,
            "MountAccessSecurityGroup",

            security_group_name="network-mount-access",

            vpc=vpc,

            allow_all_outbound=True,
        )

        # ---------------------------------------------------------
        # Outputs
        # ---------------------------------------------------------

        CfnOutput(self, "VpcId", value=vpc.vpc_id)

        CfnOutput(self, "MountSecurityGroupId", value=mount_security_group.security_group_id)

        # ---------------------------------------------------------
        # References
        # ---------------------------------------------------------

        self.vpc = vpc
        self.mount_security_group = mount_security_group
