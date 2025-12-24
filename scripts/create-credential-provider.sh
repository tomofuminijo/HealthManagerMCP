#!/bin/bash

# 簡単版のCredential Provider作成スクリプト

# 環境設定
HEALTHMATE_ENV=${HEALTHMATE_ENV:-dev}
REGION="us-west-2"

# 環境別リソース名の生成
if [ "$HEALTHMATE_ENV" = "prod" ]; then
    STACK_NAME="Healthmate-HealthManagerStack"
    CREDENTIAL_PROVIDER_NAME="healthmanager-oauth2-provider"
else
    STACK_NAME="Healthmate-HealthManagerStack-${HEALTHMATE_ENV}"
    CREDENTIAL_PROVIDER_NAME="healthmanager-oauth2-provider-${HEALTHMATE_ENV}"
fi

echo "=== AgentCore Identity OAuth2 Credential Provider 作成 ==="
echo "Environment: $HEALTHMATE_ENV"
echo "Stack Name: $STACK_NAME"
echo "Credential Provider Name: $CREDENTIAL_PROVIDER_NAME"
echo ""

# CloudFormation出力の取得
echo "CloudFormation出力を取得中..."
USER_POOL_ID=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" --output text)
CLIENT_ID=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" --query "Stacks[0].Outputs[?OutputKey=='UserPoolClientId'].OutputValue" --output text)
DISCOVERY_URL=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" --query "Stacks[0].Outputs[?OutputKey=='DiscoveryUrl'].OutputValue" --output text)

echo "User Pool ID: $USER_POOL_ID"
echo "Client ID: $CLIENT_ID"
echo "Discovery URL: $DISCOVERY_URL"

# Cognito Client Secretの取得
echo "Cognito Client Secretを取得中..."
CLIENT_SECRET=$(aws cognito-idp describe-user-pool-client --user-pool-id "$USER_POOL_ID" --client-id "$CLIENT_ID" --region "$REGION" --query "UserPoolClient.ClientSecret" --output text)

echo "Client Secret: ${CLIENT_SECRET:0:10}..."

# 既存のCredential Providerを削除（存在する場合）
echo "既存のCredential Providerを確認中..."
if aws bedrock-agentcore-control get-oauth2-credential-provider --name "$CREDENTIAL_PROVIDER_NAME" --region "$REGION" >/dev/null 2>&1; then
    echo "既存のCredential Providerを削除中..."
    aws bedrock-agentcore-control delete-oauth2-credential-provider --name "$CREDENTIAL_PROVIDER_NAME" --region "$REGION"
    sleep 5
fi

# 新しいCredential Providerの作成
echo "新しいCredential Providerを作成中..."
RESULT=$(aws bedrock-agentcore-control create-oauth2-credential-provider \
    --name "$CREDENTIAL_PROVIDER_NAME" \
    --credential-provider-vendor "CustomOauth2" \
    --oauth2-provider-config-input "{
        \"customOauth2ProviderConfig\": {
            \"oauthDiscovery\": {
                \"discoveryUrl\": \"$DISCOVERY_URL\"
            },
            \"clientId\": \"$CLIENT_ID\",
            \"clientSecret\": \"$CLIENT_SECRET\"
        }
    }" \
    --region "$REGION")

echo "=== 作成完了 ==="
echo "$RESULT" | jq '.'

# 重要な情報の表示
CREDENTIAL_PROVIDER_ARN=$(echo "$RESULT" | jq -r '.credentialProviderArn')
WORKLOAD_IDENTITY_NAME=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" --query "Stacks[0].Outputs[?OutputKey=='WorkloadIdentityName'].OutputValue" --output text)

echo ""
echo "=== AgentCore Runtime設定情報 ==="
echo "Workload Identity Name: $WORKLOAD_IDENTITY_NAME"
echo "Credential Provider ARN: $CREDENTIAL_PROVIDER_ARN"
echo ""
echo "OAuth2 Credential Providerの作成が完了しました！"