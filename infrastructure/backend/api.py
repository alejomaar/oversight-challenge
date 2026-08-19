from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_lambda as lambda_


def add_api(stack: Stack, handler: lambda_.IFunction) -> apigw.RestApi:
    """Public REST API in front of the query Lambda, gated by an API key."""

    api = apigw.RestApi(
        stack,
        "Api",

        rest_api_name="rag-chat-api",

        binary_media_types=["multipart/form-data"],

        default_cors_preflight_options=apigw.CorsOptions(
            allow_origins=apigw.Cors.ALL_ORIGINS,
            allow_methods=apigw.Cors.ALL_METHODS,
            allow_headers=["*"],
        ),
    )

    api.root.add_proxy(
        default_integration=apigw.LambdaIntegration(handler),
        any_method=True,
        default_method_options=apigw.MethodOptions(
            api_key_required=True,
        ),
    )

    api_key = api.add_api_key("ApiKey", api_key_name="rag-chat-api-key")

    usage_plan = api.add_usage_plan(
        "UsagePlan",
        name="rag-chat-usage-plan",
        api_stages=[
            apigw.UsagePlanPerApiStage(
                stage=api.deployment_stage,
            ),
        ],
    )

    usage_plan.add_api_key(api_key)

    CfnOutput(stack, "ApiEndpoint", value=api.url)
    CfnOutput(stack, "ApiKeyId", value=api_key.key_id)

    return api
