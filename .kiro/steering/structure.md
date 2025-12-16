# Project Structure

## Multi-Workspace Organization

The Healthmate ecosystem consists of three separate workspace folders:

```
Healthmate-HealthManager/          # MCP server backend
HealthCoachAI/            # AI agent
HealthmateUI/             # Web frontend
```

## Healthmate-HealthManager Structure

```
Healthmate-HealthManager/
├── cdk/                           # AWS CDK infrastructure
│   ├── cdk/                      # CDK Python modules
│   ├── app.py                    # CDK app entry point
│   ├── requirements.txt          # CDK dependencies
│   └── cdk.json                  # CDK configuration
├── lambda/                       # Lambda function handlers
│   ├── user/handler.py          # User management Lambda
│   ├── health_goal/handler.py   # Health goal Lambda
│   ├── health_policy/handler.py # Health policy Lambda
│   └── activity/handler.py      # Activity management Lambda
├── tests/                       # Test suites
│   ├── unit/                    # Unit tests
│   └── integration/             # Integration tests
├── *-mcp-schema.json           # MCP tool schemas
├── create-gateway-targets.sh   # Gateway setup script
├── delete-gateway-targets.sh   # Gateway cleanup script
├── test_mcp_client.py          # Integration test client
├── requirements.txt            # Python dependencies
└── pytest.ini                 # Test configuration
```

## HealthCoachAI Structure

```
HealthCoachAI/
├── health_coach_ai/
│   ├── __init__.py
│   └── agent.py                 # Main agent implementation
├── .bedrock_agentcore.yaml     # AgentCore configuration
├── deploy_to_aws.sh            # Deployment script
├── create_custom_iam_role.py   # IAM role creation
├── manual_test_agent.py        # Interactive testing
├── manual_test_deployed_agent.py # Deployed agent testing
├── check_deployment_status.py  # Status checking
├── agentcore-trust-policy.json # IAM trust policy
├── bedrock-agentcore-runtime-policy.json # Runtime policy
└── requirements.txt            # Python dependencies
```

## HealthmateUI Structure

```
HealthmateUI/
└── .kiro/
    └── specs/                  # UI specifications
        └── healthmate-ui/
            ├── requirements.md
            ├── design.md
            └── tasks.md
```

## Key File Patterns

### Lambda Handlers
- **Location**: `lambda/{service}/handler.py`
- **Pattern**: Each service has its own Lambda function
- **Naming**: `{service}Lambda` (e.g., UserLambda, ActivityLambda)
- **Structure**: Standard AWS Lambda handler with error handling and logging

### MCP Schemas
- **Location**: Root directory
- **Pattern**: `{service}-management-mcp-schema.json`
- **Purpose**: Define MCP tool interfaces for each service
- **Services**: user, health-goal, health-policy, activity

### Test Organization
- **Unit Tests**: `tests/unit/` - Mock AWS services, test business logic
- **Integration Tests**: `tests/integration/` - Test with real AWS services
- **Manual Tests**: Root level Python scripts for interactive testing

### Configuration Files
- **CDK**: `cdk/cdk.json` - CDK-specific configuration
- **pytest**: `pytest.ini` - Test runner configuration
- **AgentCore**: `.bedrock_agentcore.yaml` - Agent deployment config
- **Requirements**: `requirements.txt` - Python dependencies per project

## Naming Conventions

### Services
- **Healthmate-HealthManager**: Backend MCP server
- **HealthCoachAI**: AI agent
- **HealthmateUI**: Frontend application

### AWS Resources
- **Prefix**: `healthmate-` for all resources
- **Tables**: `healthmate-{entity}` (users, goals, policies, activities)
- **Functions**: `healthmate-{Service}Lambda`
- **Gateway**: `healthmate-gateway`

### Code Structure
- **Classes**: PascalCase
- **Functions**: snake_case
- **Constants**: UPPER_SNAKE_CASE
- **Files**: snake_case.py

## Development Workflow

### Local Development
1. Set up virtual environment in each project
2. Install dependencies with `pip install -r requirements.txt`
3. Use project-specific test commands
4. Deploy infrastructure before testing integration

### Deployment Order
1. **Healthmate-HealthManager**: Deploy CDK stack first
2. **HealthCoachAI**: Deploy agent after MCP backend
3. **HealthmateUI**: Deploy frontend last

### Testing Strategy
- **Unit tests**: Fast, isolated, mocked dependencies
- **Integration tests**: Real AWS services, end-to-end flows
- **Manual tests**: Interactive scripts for development and debugging