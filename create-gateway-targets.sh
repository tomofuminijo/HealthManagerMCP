#!/bin/bash

# HealthManagerMCP AgentCore GatewayにGatewayTargetを作成するスクリプト

set -e

REGION="us-west-2"

# AWS CLIのページャーを無効化
export AWS_PAGER=""

echo "=== HealthManagerMCP AgentCore Gateway Target セットアップ ==="
echo ""

# 1. Gateway IDの取得
echo "1. Gateway IDを取得中..."
GATEWAY_ID=$(aws bedrock-agentcore-control list-gateways --region $REGION \
  --query "items[?name=='healthmate-gateway'].gatewayId" \
  --output text)

if [ -z "$GATEWAY_ID" ]; then
  echo "エラー: healthmate-gateway が見つかりません"
  exit 1
fi

echo "   Gateway ID: $GATEWAY_ID"
echo ""

# 2. Lambda ARNの取得
echo "2. Lambda ARNを取得中..."
USER_LAMBDA_ARN=$(aws lambda get-function --function-name healthmanagermcp-user \
  --region $REGION --query 'Configuration.FunctionArn' --output text)

HEALTH_GOAL_LAMBDA_ARN=$(aws lambda get-function --function-name healthmanagermcp-health-goal \
  --region $REGION --query 'Configuration.FunctionArn' --output text)

HEALTH_POLICY_LAMBDA_ARN=$(aws lambda get-function --function-name healthmanagermcp-health-policy \
  --region $REGION --query 'Configuration.FunctionArn' --output text)

ACTIVITY_LAMBDA_ARN=$(aws lambda get-function --function-name healthmanagermcp-activity \
  --region $REGION --query 'Configuration.FunctionArn' --output text)

echo "   User Lambda ARN: $USER_LAMBDA_ARN"
echo "   Health Goal Lambda ARN: $HEALTH_GOAL_LAMBDA_ARN"
echo "   Health Policy Lambda ARN: $HEALTH_POLICY_LAMBDA_ARN"
echo "   Activity Lambda ARN: $ACTIVITY_LAMBDA_ARN"
echo ""

# 3. GatewayTargetの作成

# 3.1 UserManagement
echo "3. GatewayTargetを作成中..."
echo "   3.1 UserManagement..."

# MCPスキーマを読み込んでJSON文字列に変換
USER_MCP_SCHEMA=$(cat mcp-schema/user-management-mcp-schema.json | jq -c .)

# TargetConfigurationのJSONを作成
cat > /tmp/gateway-target-user.json <<EOF
{
  "mcp": {
    "lambda": {
      "lambdaArn": "$USER_LAMBDA_ARN",
      "toolSchema": {
        "inlinePayload": $USER_MCP_SCHEMA
      }
    }
  }
}
EOF

aws bedrock-agentcore-control create-gateway-target \
  --region $REGION \
  --gateway-identifier "$GATEWAY_ID" \
  --name "UserManagement" \
  --description "ユーザー情報を管理する" \
  --credential-provider-configurations '[{"credentialProviderType":"GATEWAY_IAM_ROLE"}]' \
  --target-configuration file:///tmp/gateway-target-user.json

echo "      ✓ UserManagement 作成完了"

# 3.2 HealthGoalManagement
echo "   3.2 HealthGoalManagement..."

HEALTH_GOAL_MCP_SCHEMA=$(cat mcp-schema/health-goal-management-mcp-schema.json | jq -c .)

cat > /tmp/gateway-target-health-goal.json <<EOF
{
  "mcp": {
    "lambda": {
      "lambdaArn": "$HEALTH_GOAL_LAMBDA_ARN",
      "toolSchema": {
        "inlinePayload": $HEALTH_GOAL_MCP_SCHEMA
      }
    }
  }
}
EOF

aws bedrock-agentcore-control create-gateway-target \
  --region $REGION \
  --gateway-identifier "$GATEWAY_ID" \
  --name "HealthGoalManagement" \
  --description "ユーザーの健康目標（長期的な理想状態）を管理する" \
  --credential-provider-configurations '[{"credentialProviderType":"GATEWAY_IAM_ROLE"}]' \
  --target-configuration file:///tmp/gateway-target-health-goal.json

echo "      ✓ HealthGoalManagement 作成完了"

# 3.3 HealthPolicyManagement
echo "   3.3 HealthPolicyManagement..."

HEALTH_POLICY_MCP_SCHEMA=$(cat mcp-schema/health-policy-management-mcp-schema.json | jq -c .)

cat > /tmp/gateway-target-health-policy.json <<EOF
{
  "mcp": {
    "lambda": {
      "lambdaArn": "$HEALTH_POLICY_LAMBDA_ARN",
      "toolSchema": {
        "inlinePayload": $HEALTH_POLICY_MCP_SCHEMA
      }
    }
  }
}
EOF

aws bedrock-agentcore-control create-gateway-target \
  --region $REGION \
  --gateway-identifier "$GATEWAY_ID" \
  --name "HealthPolicyManagement" \
  --description "ユーザーの健康ポリシー（具体的な行動ルール）を管理する" \
  --credential-provider-configurations '[{"credentialProviderType":"GATEWAY_IAM_ROLE"}]' \
  --target-configuration file:///tmp/gateway-target-health-policy.json

echo "      ✓ HealthPolicyManagement 作成完了"

# 3.4 ActivityManagement
echo "   3.4 ActivityManagement..."

ACTIVITY_MCP_SCHEMA=$(cat mcp-schema/activity-management-mcp-schema.json | jq -c .)

cat > /tmp/gateway-target-activity.json <<EOF
{
  "mcp": {
    "lambda": {
      "lambdaArn": "$ACTIVITY_LAMBDA_ARN",
      "toolSchema": {
        "inlinePayload": $ACTIVITY_MCP_SCHEMA
      }
    }
  }
}
EOF

aws bedrock-agentcore-control create-gateway-target \
  --region $REGION \
  --gateway-identifier "$GATEWAY_ID" \
  --name "ActivityManagement" \
  --description "ユーザーの日々の健康活動を記録・取得する" \
  --credential-provider-configurations '[{"credentialProviderType":"GATEWAY_IAM_ROLE"}]' \
  --target-configuration file:///tmp/gateway-target-activity.json

echo "      ✓ ActivityManagement 作成完了"
echo ""

# 4. 作成確認
echo "4. 作成されたGatewayTargetを確認中..."
aws bedrock-agentcore-control list-gateway-targets \
  --region $REGION \
  --gateway-identifier "$GATEWAY_ID" \
  --query 'gatewayTargets[].{Name:name,Description:description}' \
  --output table

echo ""
echo "=== セットアップ完了 ==="
