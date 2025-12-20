#!/bin/bash

# Healthmate-HealthManager 完全削除スクリプト
# AgentCore Identity削除 -> CDK削除の一連の流れ

set -e  # エラー時に停止

STACK_NAME="Healthmate-HealthManagerStack"
REGION="us-west-2"

echo "=== Healthmate-HealthManager 完全削除開始 ==="
echo "Stack Name: $STACK_NAME"
echo "Region: $REGION"
echo ""

# Step 1: AgentCore Identity (OAuth2 Credential Provider) の削除
echo "Step 1: AgentCore Identity (OAuth2 Credential Provider) を削除中..."
./scripts/delete-credential-provider.sh

if [ $? -ne 0 ]; then
    echo "⚠️  AgentCore Identity削除でエラーが発生しましたが、続行します"
fi

echo "✅ AgentCore Identity削除が完了しました"
echo ""

# Step 2: CDKスタックの削除
echo "Step 2: CDKスタックを削除中..."
cd cdk
cdk destroy --force

if [ $? -ne 0 ]; then
    echo "❌ CDK削除に失敗しました"
    exit 1
fi

echo "✅ CDK削除が完了しました"
echo ""

# Step 3: 削除完了の確認
echo "=== 削除完了 ==="
echo "以下のリソースが削除されました："
echo "- OAuth2 Credential Provider: healthmanager-oauth2-provider"
echo "- CDKスタック: $STACK_NAME"
echo "- 全てのAWSリソース（DynamoDB、Lambda、Cognito、AgentCore Gateway等）"
echo ""

echo "🎉 Healthmate-HealthManager の完全削除が完了しました！"