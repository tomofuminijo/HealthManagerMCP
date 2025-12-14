#!/bin/bash

# HealthManagerMCP - Cognito Client Secret更新スクリプト
# 
# このスクリプトは、CDKデプロイ後にCognito User Pool Client Secretを取得し、
# Secrets Managerに保存します。

set -e

# 設定
REGION="us-west-2"
SECRET_NAME="healthmate/cognito/client-secret"

echo "🔐 Cognito Client Secret更新開始..."

# CloudFormation StackからUser Pool IDとClient IDを取得
echo "📋 CloudFormation Stackから情報を取得中..."
USER_POOL_ID=$(aws cloudformation describe-stacks \
    --stack-name HealthManagerMCPStack \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
    --output text)

CLIENT_ID=$(aws cloudformation describe-stacks \
    --stack-name HealthManagerMCPStack \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolClientId`].OutputValue' \
    --output text)

if [ -z "$USER_POOL_ID" ] || [ -z "$CLIENT_ID" ]; then
    echo "❌ User Pool IDまたはClient IDが取得できませんでした"
    echo "   User Pool ID: $USER_POOL_ID"
    echo "   Client ID: $CLIENT_ID"
    exit 1
fi

echo "✅ 取得完了:"
echo "   User Pool ID: $USER_POOL_ID"
echo "   Client ID: $CLIENT_ID"

# Cognito User Pool ClientからClient Secretを取得
echo "🔍 Cognito Client Secretを取得中..."
CLIENT_SECRET=$(aws cognito-idp describe-user-pool-client \
    --user-pool-id $USER_POOL_ID \
    --client-id $CLIENT_ID \
    --region $REGION \
    --query 'UserPoolClient.ClientSecret' \
    --output text)

if [ -z "$CLIENT_SECRET" ] || [ "$CLIENT_SECRET" = "None" ]; then
    echo "❌ Client Secretが取得できませんでした"
    echo "   Client Secretが生成されていない可能性があります"
    exit 1
fi

echo "✅ Client Secret取得完了"

# Secrets Managerのシークレット値を更新
echo "💾 Secrets Managerを更新中..."
SECRET_VALUE=$(cat <<EOF
{
    "client_id": "$CLIENT_ID",
    "user_pool_id": "$USER_POOL_ID", 
    "client_secret": "$CLIENT_SECRET"
}
EOF
)

aws secretsmanager update-secret \
    --secret-id $SECRET_NAME \
    --secret-string "$SECRET_VALUE" \
    --region $REGION

echo "✅ Secrets Manager更新完了"

# 検証
echo "🔍 更新内容を検証中..."
STORED_SECRET=$(aws secretsmanager get-secret-value \
    --secret-id $SECRET_NAME \
    --region $REGION \
    --query 'SecretString' \
    --output text)

STORED_CLIENT_ID=$(echo $STORED_SECRET | jq -r '.client_id')
STORED_USER_POOL_ID=$(echo $STORED_SECRET | jq -r '.user_pool_id')

if [ "$STORED_CLIENT_ID" = "$CLIENT_ID" ] && [ "$STORED_USER_POOL_ID" = "$USER_POOL_ID" ]; then
    echo "✅ 検証成功: Secrets Managerに正しく保存されました"
else
    echo "❌ 検証失敗: 保存された値が一致しません"
    exit 1
fi

echo ""
echo "🎉 Cognito Client Secret更新完了!"
echo ""
echo "📋 他のプロダクトからの参照方法:"
echo "   Secret ARN: $(aws secretsmanager describe-secret --secret-id $SECRET_NAME --region $REGION --query 'ARN' --output text)"
echo "   Secret Name: $SECRET_NAME"
echo ""
echo "📖 使用例 (Python):"
echo "   import boto3, json"
echo "   client = boto3.client('secretsmanager', region_name='$REGION')"
echo "   response = client.get_secret_value(SecretId='$SECRET_NAME')"
echo "   secret = json.loads(response['SecretString'])"
echo "   client_secret = secret['client_secret']"