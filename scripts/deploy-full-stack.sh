#!/bin/bash

# Healthmate-HealthManager 完全デプロイスクリプト
# CDK デプロイ -> AgentCore Identity作成の一連の流れ

set -e  # エラー時に停止

STACK_NAME="Healthmate-HealthManagerStack"
REGION="us-west-2"

echo "=== Healthmate-HealthManager 完全デプロイ開始 ==="
echo "Stack Name: $STACK_NAME"
echo "Region: $REGION"
echo ""

# Step 1: CDKスタックのデプロイ
echo "Step 1: CDKスタックをデプロイ中..."
cd cdk
cdk deploy --require-approval never

if [ $? -ne 0 ]; then
    echo "❌ CDKデプロイに失敗しました"
    exit 1
fi

echo "✅ CDKデプロイが完了しました"
echo ""

# Step 2: AgentCore Identity (OAuth2 Credential Provider) の作成
echo "Step 2: AgentCore Identity (OAuth2 Credential Provider) を作成中..."
cd ..
./scripts/create-credential-provider.sh

if [ $? -ne 0 ]; then
    echo "❌ AgentCore Identity作成に失敗しました"
    exit 1
fi

echo "✅ AgentCore Identity作成が完了しました"
echo ""

# Step 3: デプロイ完了の確認
echo "=== デプロイ完了 ==="
echo "以下のリソースが正常にデプロイされました："
echo "- CDKスタック: $STACK_NAME"
echo "- AgentCore Gateway"
echo "- OAuth2 Credential Provider: healthmanager-oauth2-provider"
echo "- Workload Identity: healthmanager-agentcore-identity"
echo ""

# CloudFormation出力の表示
echo "=== CloudFormation出力 ==="
aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" --query "Stacks[0].Outputs[?OutputKey=='GatewayId' || OutputKey=='WorkloadIdentityName' || OutputKey=='UserPoolId' || OutputKey=='UserPoolClientId'].[OutputKey,OutputValue]" --output table

echo ""
echo "🎉 Healthmate-HealthManager の完全デプロイが完了しました！"