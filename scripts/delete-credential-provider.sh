#!/bin/bash

# AgentCore Identity OAuth2 Credential Provider削除スクリプト

STACK_NAME="Healthmate-HealthManagerStack"
REGION="us-west-2"
CREDENTIAL_PROVIDER_NAME="healthmanager-oauth2-provider"

echo "=== AgentCore Identity OAuth2 Credential Provider 削除 ==="

# 既存のCredential Providerの確認
echo "既存のCredential Providerを確認中..."
if aws bedrock-agentcore-control get-oauth2-credential-provider --name "$CREDENTIAL_PROVIDER_NAME" --region "$REGION" >/dev/null 2>&1; then
    echo "Credential Provider '$CREDENTIAL_PROVIDER_NAME' が見つかりました。削除を開始します..."
    
    # Credential Providerの削除
    echo "Credential Providerを削除中..."
    aws bedrock-agentcore-control delete-oauth2-credential-provider \
        --name "$CREDENTIAL_PROVIDER_NAME" \
        --region "$REGION"
    
    if [ $? -eq 0 ]; then
        echo "✅ Credential Provider '$CREDENTIAL_PROVIDER_NAME' の削除が完了しました"
    else
        echo "❌ Credential Provider '$CREDENTIAL_PROVIDER_NAME' の削除に失敗しました"
        exit 1
    fi
else
    echo "⚠️  Credential Provider '$CREDENTIAL_PROVIDER_NAME' が見つかりません（既に削除済みまたは存在しません）"
fi

echo ""
echo "=== 削除完了 ==="
echo "OAuth2 Credential Providerの削除が完了しました！"
echo ""
echo "次のステップ: CDKスタックを削除する場合は以下を実行してください"
echo "cd cdk && cdk destroy"