#!/bin/bash

# HealthManagerMCP AgentCore GatewayからGatewayTargetを削除するスクリプト

set -e

REGION="us-west-2"

# AWS CLIのページャーを無効化
export AWS_PAGER=""

echo "=== HealthManagerMCP AgentCore Gateway Target 削除 ==="
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

# 2. 既存のGatewayTargetを取得
echo "2. 既存のGatewayTargetを取得中..."
TARGETS=$(aws bedrock-agentcore-control list-gateway-targets \
  --region $REGION \
  --gateway-identifier "$GATEWAY_ID" \
  --query 'items[].{Name:name,Id:targetId}' \
  --output json)

echo "$TARGETS" | jq -r '.[] | "   - \(.Name) (ID: \(.Id))"'
echo ""

# 3. GatewayTargetの削除
echo "3. GatewayTargetを削除中..."

# UserManagementの削除
USER_TARGET_ID=$(echo "$TARGETS" | jq -r '.[] | select(.Name=="UserManagement") | .Id')
if [ -n "$USER_TARGET_ID" ] && [ "$USER_TARGET_ID" != "null" ]; then
  echo "   3.1 UserManagementを削除中..."
  aws bedrock-agentcore-control delete-gateway-target \
    --region $REGION \
    --gateway-id "$GATEWAY_ID" \
    --target-id "$USER_TARGET_ID"
  echo "      ✓ UserManagement 削除完了"
else
  echo "   3.1 UserManagement が見つかりません（スキップ）"
fi

# HealthGoalManagementの削除
HEALTH_GOAL_TARGET_ID=$(echo "$TARGETS" | jq -r '.[] | select(.Name=="HealthGoalManagement") | .Id')
if [ -n "$HEALTH_GOAL_TARGET_ID" ] && [ "$HEALTH_GOAL_TARGET_ID" != "null" ]; then
  echo "   3.2 HealthGoalManagementを削除中..."
  aws bedrock-agentcore-control delete-gateway-target \
    --region $REGION \
    --gateway-id "$GATEWAY_ID" \
    --target-id "$HEALTH_GOAL_TARGET_ID"
  echo "      ✓ HealthGoalManagement 削除完了"
else
  echo "   3.2 HealthGoalManagement が見つかりません（スキップ）"
fi

# HealthPolicyManagementの削除
HEALTH_POLICY_TARGET_ID=$(echo "$TARGETS" | jq -r '.[] | select(.Name=="HealthPolicyManagement") | .Id')
if [ -n "$HEALTH_POLICY_TARGET_ID" ] && [ "$HEALTH_POLICY_TARGET_ID" != "null" ]; then
  echo "   3.3 HealthPolicyManagementを削除中..."
  aws bedrock-agentcore-control delete-gateway-target \
    --region $REGION \
    --gateway-id "$GATEWAY_ID" \
    --target-id "$HEALTH_POLICY_TARGET_ID"
  echo "      ✓ HealthPolicyManagement 削除完了"
else
  echo "   3.3 HealthPolicyManagement が見つかりません（スキップ）"
fi

# ActivityManagementの削除
ACTIVITY_TARGET_ID=$(echo "$TARGETS" | jq -r '.[] | select(.Name=="ActivityManagement") | .Id')
if [ -n "$ACTIVITY_TARGET_ID" ] && [ "$ACTIVITY_TARGET_ID" != "null" ]; then
  echo "   3.4 ActivityManagementを削除中..."
  aws bedrock-agentcore-control delete-gateway-target \
    --region $REGION \
    --gateway-id "$GATEWAY_ID" \
    --target-id "$ACTIVITY_TARGET_ID"
  echo "      ✓ ActivityManagement 削除完了"
else
  echo "   3.4 ActivityManagement が見つかりません（スキップ）"
fi

echo ""

# 4. 削除確認
echo "4. 残っているGatewayTargetを確認中..."
REMAINING=$(aws bedrock-agentcore-control list-gateway-targets \
  --region $REGION \
  --gateway-identifier "$GATEWAY_ID" \
  --query 'items[].{Name:name,Description:description}' \
  --output table)

if [ -z "$REMAINING" ] || echo "$REMAINING" | grep -q "None"; then
  echo "   すべてのGatewayTargetが削除されました"
else
  echo "$REMAINING"
fi

echo ""
echo "=== 削除完了 ==="
