from aws_cdk import CfnOutput, Stack
from constructs import Construct

from .api import add_api
from .compute import add_query_handler
from .database import add_database
from .network import add_network
from .storage import add_upload_bucket

EMBEDDINGS_MODEL_ID = "amazon.titan-embed-text-v2:0"
LLM_MODEL_ID = "openai.gpt-oss-20b-1:0"


class BackendStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        vpc = add_network(self)
        database = add_database(self, vpc)
        upload_bucket = add_upload_bucket(self)

        lambda_function = add_query_handler(
            self,
            vpc=vpc,
            database=database,
            upload_bucket=upload_bucket,
            embeddings_model_id=EMBEDDINGS_MODEL_ID,
            llm_model_id=LLM_MODEL_ID,
        )

        api = add_api(self, lambda_function)

        CfnOutput(self, "LambdaFunctionName", value=lambda_function.function_name)
        CfnOutput(self, "UploadBucketName", value=upload_bucket.bucket_name)
        CfnOutput(self, "DatabaseEndpoint", value=database.db_instance_endpoint_address)

        self.api = api
        self.lambda_function = lambda_function
        self.upload_bucket = upload_bucket
