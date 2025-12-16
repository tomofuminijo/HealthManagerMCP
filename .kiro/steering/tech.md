# Technology Stack

## Architecture

**Serverless, cloud-native architecture** using AWS services with Model Context Protocol (MCP) for AI integration.

## Core Technologies

### Backend (Healthmate-HealthManager)
- **Runtime**: Python 3.12+
- **Infrastructure**: AWS CDK (Python)
- **Compute**: AWS Lambda functions
- **Database**: Amazon DynamoDB
- **Authentication**: Amazon Cognito (OAuth 2.0)
- **API Gateway**: Amazon Bedrock AgentCore Gateway
- **Protocol**: Model Context Protocol (MCP)

### AI Agent (HealthCoachAI)
- **Framework**: Strands Agent SDK
- **Runtime**: Amazon Bedrock AgentCore Runtime
- **Platform**: Linux/ARM64 containers
- **Dependencies**: boto3, pytz, mcp

### Frontend (HealthmateUI)
- **Framework**: TBD (Web application)
- **Authentication**: Cognito OAuth 2.0 integration

## Development Tools

### Testing
- **Framework**: pytest with hypothesis (property-based testing)
- **Coverage**: pytest-cov
- **Mocking**: moto for AWS services
- **Config**: pytest.ini with verbose output and short tracebacks

### Code Quality
- **Formatting**: black
- **Linting**: flake8
- **Type Checking**: mypy

## Common Commands

### Healthmate-HealthManager

```bash
# Environment setup
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# CDK operations
cd cdk && npm install
cdk deploy --require-approval never
cd .. && ./create-gateway-targets.sh

# Testing
pytest tests/unit/ -v                    # Unit tests
python test_mcp_client.py               # Integration tests

# Cleanup
./delete-gateway-targets.sh
cdk destroy
```

### HealthCoachAI

```bash
# Setup and deploy
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
./deploy_to_aws.sh                      # One-command deploy

# Testing
python manual_test_agent.py             # Interactive testing
python manual_test_deployed_agent.py    # Test deployed agent
agentcore status                         # Check deployment status

# Development
agentcore invoke --dev "test message"   # Local development
```

## Configuration Management

### Environment Variables
- **AWS_REGION**: Default us-west-2
- **HEALTH_STACK_NAME**: CloudFormation stack name
- **HEALTHMANAGER_GATEWAY_ID**: MCP Gateway identifier
- **LOG_LEVEL**: DEBUG for development

### CloudFormation Outputs
Required stack outputs for integration:
- `GatewayId`: MCP Gateway ID
- `UserPoolId`: Cognito User Pool ID
- `UserPoolClientId`: Cognito Client ID

## Security Patterns

- **JWT Authentication**: All API calls require Cognito JWT tokens
- **IAM Roles**: Least privilege access with custom roles
- **Environment-based Config**: No hardcoded credentials
- **Encryption**: Data encrypted in transit and at rest

## Deployment Patterns

- **Infrastructure as Code**: AWS CDK for all resources
- **Serverless**: Lambda functions with DynamoDB
- **Container Deployment**: AgentCore Runtime for AI agents
- **Gateway Integration**: MCP protocol for AI connectivity