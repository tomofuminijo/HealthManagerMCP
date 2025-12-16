# Healthmate-HealthManager サービス - MCP Backend

## Service Overview

Healthmate-HealthManager サービスは、Healthmate プロダクトのバックエンドを担当するModel Context Protocol (MCP) サーバーです。健康データの永続化と外部AIクライアントへのAPI提供を行います。

### Primary Responsibilities

- **Health Data Management**: ユーザー、目標、ポリシー、活動データの管理
- **MCP API Provider**: 外部AIクライアント（ChatGPT、Claude、HealthCoachAI）向けAPI提供
- **Authentication & Authorization**: Cognito OAuth 2.0による認証・認可
- **Data Persistence**: DynamoDBによる健康データの永続化

### Technology Stack

- **Protocol**: Model Context Protocol (MCP) 
- **Runtime**: Python 3.12+
- **Compute**: AWS Lambda functions
- **Database**: Amazon DynamoDB
- **Authentication**: Amazon Cognito User Pool
- **API Gateway**: Amazon Bedrock AgentCore Gateway
- **Infrastructure**: AWS CDK (Infrastructure as Code)

## MCP Tools Architecture

### User Management Tools
```python
# Lambda: lambda/user/handler.py
tools = ["addUser", "updateUser", "getUser"]
table = "healthmate-users"
```

### Health Goal Management Tools
```python
# Lambda: lambda/health_goal/handler.py  
tools = ["addGoal", "updateGoal", "deleteGoal", "getGoals"]
table = "healthmate-goals"
```

### Health Policy Management Tools
```python
# Lambda: lambda/health_policy/handler.py
tools = ["addPolicy", "updatePolicy", "deletePolicy", "getPolicies"]
table = "healthmate-policies"
```

### Activity Management Tools
```python
# Lambda: lambda/activity/handler.py
tools = [
    "addActivities", "updateActivity", "updateActivities", 
    "deleteActivity", "getActivities", "getActivitiesInRange"
]
table = "healthmate-activities"
```

## Lambda Function Patterns

### Standard Handler Structure
```python
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    標準的なLambda関数構造
    - JWT認証
    - 入力検証
    - DynamoDB操作
    - エラーハンドリング
    - MCP形式レスポンス
    """
    try:
        # JWT からユーザーID抽出
        user_id = extract_user_id_from_jwt(event)
        
        # ツール名に基づく処理分岐
        tool_name = event.get("tool")
        parameters = event.get("parameters", {})
        
        # DynamoDB操作
        result = execute_tool(tool_name, user_id, parameters)
        
        return {
            "success": True,
            "data": result,
            "message": "操作が正常に完了しました"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e)
        }
```

### Error Handling Patterns
```python
# 統一エラーハンドリング
def handle_dynamodb_error(error):
    """DynamoDB例外をMCP形式エラーに変換"""
    if error.response['Error']['Code'] == 'ConditionalCheckFailedException':
        return {"error": "RESOURCE_NOT_FOUND", "message": "リソースが見つかりません"}
    elif error.response['Error']['Code'] == 'ValidationException':
        return {"error": "VALIDATION_ERROR", "message": "入力データが無効です"}
    else:
        return {"error": "INTERNAL_ERROR", "message": "内部エラーが発生しました"}
```

## DynamoDB Design Patterns

### Table Structure
```python
# 各ドメインごとに独立したテーブル
tables = {
    "healthmate-users": {
        "PK": "USER#{user_id}",
        "attributes": ["name", "email", "dateOfBirth", "preferences"]
    },
    "healthmate-goals": {
        "PK": "USER#{user_id}",
        "SK": "GOAL#{goal_id}",
        "attributes": ["title", "goalType", "targetValue", "status"]
    },
    "healthmate-policies": {
        "PK": "USER#{user_id}",
        "SK": "POLICY#{policy_id}",
        "attributes": ["title", "policyType", "rules", "isActive"]
    },
    "healthmate-activities": {
        "PK": "USER#{user_id}#DATE#{date}",
        "SK": "TIME#{time}",
        "attributes": ["activityType", "description", "items"]
    }
}
```

### Query Patterns
```python
# ユーザーの全目標取得
def get_user_goals(user_id: str):
    return table.query(
        KeyConditionExpression=Key('PK').eq(f'USER#{user_id}') & 
                              Key('SK').begins_with('GOAL#')
    )

# 日付範囲での活動取得
def get_activities_in_range(user_id: str, start_date: str, end_date: str):
    return table.query(
        KeyConditionExpression=Key('PK').between(
            f'USER#{user_id}#DATE#{start_date}',
            f'USER#{user_id}#DATE#{end_date}'
        )
    )
```

## CDK Infrastructure Patterns

### Stack Organization
```python
# cdk/cdk/healthmanager_stack.py
class HealthManagerStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        
        # DynamoDB Tables
        self.create_dynamodb_tables()
        
        # Lambda Functions  
        self.create_lambda_functions()
        
        # Cognito User Pool
        self.create_cognito_resources()
        
        # AgentCore Gateway
        self.create_agentcore_gateway()
```

### Resource Naming
```python
# 統一的なリソース命名
resource_names = {
    "tables": "healthmate-{domain}",
    "functions": "healthmate-{Domain}Lambda", 
    "user_pool": "healthmate-users",
    "gateway": "healthmate-gateway"
}
```

## Testing Patterns

### Unit Testing
```python
# tests/unit/test_user_lambda.py
@pytest.fixture
def mock_dynamodb():
    with mock_dynamodb():
        yield boto3.resource('dynamodb', region_name='us-west-2')

def test_add_user_success(mock_dynamodb):
    """ユーザー追加の正常系テスト"""
    # Arrange
    event = {"tool": "addUser", "parameters": {...}}
    
    # Act  
    result = lambda_handler(event, None)
    
    # Assert
    assert result["success"] is True
    assert "userId" in result["data"]
```

### Integration Testing
```python
# test_mcp_client.py
async def test_mcp_integration():
    """MCP プロトコル統合テスト"""
    # 実際のAWS環境でのE2Eテスト
    response = await mcp_client.call_tool(
        "user-management", "addUser", test_user_data
    )
    assert response["success"] is True
```

## Deployment Patterns

### Gateway Setup
```bash
# create-gateway-targets.sh
# MCP スキーマファイルからGateway Targetを自動生成
for schema in *-mcp-schema.json; do
    aws agentcore create-gateway-target \
        --gateway-name healthmate-gateway \
        --target-name ${schema%-mcp-schema.json} \
        --schema file://$schema
done
```

### Environment Configuration
```python
# 環境変数による設定管理
import os

config = {
    "region": os.environ.get("AWS_REGION", "us-west-2"),
    "tables": {
        "users": os.environ.get("USERS_TABLE_NAME", "healthmate-users"),
        "goals": os.environ.get("GOALS_TABLE_NAME", "healthmate-goals"),
        "policies": os.environ.get("POLICIES_TABLE_NAME", "healthmate-policies"),
        "activities": os.environ.get("ACTIVITIES_TABLE_NAME", "healthmate-activities")
    }
}
```

## Integration Points

### HealthCoachAI サービス連携
- MCP クライアントとして健康データにアクセス
- JWT トークンによるユーザー識別
- リアルタイムデータ取得

### HealthmateUI サービス連携  
- Web UI経由での直接データ操作
- Cognito認証フローの共有
- RESTful API インターフェース

### External AI Clients連携
- ChatGPT、Claude等の直接MCP連携
- OAuth 2.0による認証
- 標準化されたMCPツールインターフェース