"""An AWS Python Pulumi program"""

import iam
import pulumi
import pulumi_aws as aws

region = aws.config.region

custom_stage_name = 'example'

##################
## Lambda Function
##################

# Create a Lambda function, using code from the `./app` folder.
lambda_func = aws.lambda_.Function("mylambda",
    role=iam.lambda_role.arn,
    runtime="python3.7",
    handler="hello.handler",
    code=pulumi.AssetArchive({
        '.': pulumi.FileArchive('./hello_lambda')
    })
)

##################
## CloudWatch Log Group for Lambda
##################

# Correctly create a CloudWatch Log Group for the Lambda function with a 14-day retention policy.
log_group = lambda_func.name.apply(lambda name: aws.cloudwatch.LogGroup("mylambda-log-group",
    name=f"/aws/lambda/{name}",
    retention_in_days=14
))
####################################################################
##
## API Gateway REST API (API Gateway V1 / original)
##    Specific POST route to the lambda function
##
####################################################################

# Create a Swagger spec route handler for a Lambda function that only accepts POST requests.
def swagger_post_route_handler(arn):
    return ({
        "post": {
            "x-amazon-apigateway-integration": {
                "uri": pulumi.Output.format('arn:aws:apigateway:{0}:lambda:path/2015-03-31/functions/{1}/invocations', region, arn),
                "passthroughBehavior": "when_no_match",
                "httpMethod": "POST",
                "type": "aws_proxy",
            },
        },
    })

# Create the API Gateway Rest API, using a swagger spec.
rest_api = aws.apigateway.RestApi("api",
    body=pulumi.Output.json_dumps({
        "swagger": "2.0",
        "info": {"title": "api", "version": "1.0"},
        "paths": {
            "/myroute": swagger_post_route_handler(lambda_func.arn),  # Change this to your desired path
        },
    }))

# Create a deployment of the Rest API.
deployment = aws.apigateway.Deployment("api-deployment",
    rest_api=rest_api.id,
    stage_name="",
)

# Create a stage, which is an addressable instance of the Rest API. Set it to point at the latest deployment.
stage = aws.apigateway.Stage("api-stage",
    rest_api=rest_api.id,
    deployment=deployment.id,
    stage_name=custom_stage_name,
)

# Give permissions from API Gateway to invoke the Lambda
rest_invoke_permission = aws.lambda_.Permission("api-rest-lambda-permission",
    action="lambda:invokeFunction",
    function=lambda_func.name,
    principal="apigateway.amazonaws.com",
    source_arn=deployment.execution_arn.apply(lambda arn: arn + "*/*"),
)

# Export the https endpoint of the running Rest API
pulumi.export("apigateway-rest-endpoint", deployment.invoke_url.apply(lambda url: url + custom_stage_name + '/myroute'))
