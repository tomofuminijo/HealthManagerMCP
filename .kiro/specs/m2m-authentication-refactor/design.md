# Design Document

## Overview

Healthmate-HealthManagerサービスのAgentCore Gateway認証システムをM2M（Machine-to-Machine）認証に対応させるための設計です。現在のユーザー認証ベースのCognito User Poolを、AgentCore Gatewayに最適化されたM2M認証システムに変更し、Secrets Managerを使用してクライアントシークレットを安全に管理します。

## Architecture

### Current Architecture
```
HealthCoachAI/HealthmateUI → Cognito User Pool (User Auth) → AgentCore Gateway → Lambda Functions
```

### Target Architecture
```
AgentCore Identity → Cognito User Pool (M2M Auth) → AgentCore Gateway → Lambda Functions
                  ↑
            Secrets Manager (Client Secret)
```

### Key Changes
1. **Cognito User Pool**: ユーザー認証からM2M認証専用に変更
2. **App Client**: クライアントクレデンシャルフロー対応
3. **Secrets Manager**: クライアントシークレットの安全な保存
4. **Custom Scope**: AgentCore用のカスタムスコープ定義
5. **CloudFormation Outputs**: AgentCore連携用の出力追加

## Components and Interfaces

### Cognito User Pool (M2M)
```python
gateway_user_pool = cognito.UserPool(
    self, "HealthManagerM2MUserPool",
    user_pool_name="HealthManagerM2MUserPool",
    self_sign_up_enabled=False,  # M2M認証のため無効化
    sign_in_aliases=cognito.SignInAliases(username=True),
    removal_policy=RemovalPolicy.DESTROY
)
```

### App Client (Client Credentials)
```python
gateway_app_client = gateway_user_pool.add_client(
    self, "HealthManagerM2MAppClient",
    user_pool_client_name="AgentCoreGatewayClient",
    generate_secret=True,  # M2Mフローに必須
    auth_flows=cognito.AuthFlow(client_credentials=True),
    o_auth_settings=cognito.OAuthSettings(
        scopes=[cognito.OAuthScope.custom("HealthManager/HealthTarget:invoke")]
    )
)
```

### Secrets Manager Integration
```python
client_secret_arn = secretsmanager.Secret(
    self, "HealthManagerM2MClientSecret",
    secret_name=f"AgentCoreIdentitySecret/HealthManager/{self.stack_name}",
    secret_string_value=SecretValue.unsafe_plain_text(
        gateway_app_client.user_pool_client_secret
    ),
    removal_policy=RemovalPolicy.DESTROY
).secret_full_arn
```

### AgentCore Gateway Configuration
既存のAgentCore Gateway設定は保持し、認証設定のみ更新：
```python
# 既存のGateway設定を維持
authorizer_configuration=bedrockagentcore.CfnGateway.AuthorizerConfigurationProperty(
    custom_jwt_authorizer=bedrockagentcore.CfnGateway.CustomJWTAuthorizerConfigurationProperty(
        discovery_url=f"https://cognito-idp.{self.region}.amazonaws.com/{gateway_user_pool.user_pool_id}/.well-known/openid-configuration",
        allowed_clients=[gateway_app_client.user_pool_client_id]
    )
)
```

## Data Models

### CloudFormation Outputs
```python
outputs = {
    "UserPoolId": gateway_user_pool.user_pool_id,
    "AppClientId": gateway_app_client.user_pool_client_id,
    "IdentitySecretArn": client_secret_arn,
    "DiscoveryUrl": f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration",
    "CustomScope": "HealthManager/HealthTarget:invoke"
}
```

### Secrets Manager Schema
```json
{
  "secret_name": "AgentCoreIdentitySecret/HealthManager/{stack_name}",
  "secret_value": "{client_secret}",
  "description": "Client secret for AgentCore Gateway M2M authentication"
}
```

### Custom OAuth Scope Format
```
HealthManager/HealthTarget:invoke
```
- `HealthManager`: Gateway名
- `HealthTarget`: ターゲット名（汎用）
- `invoke`: アクション

## Error Handling

### CDK Deployment Errors
- **User Pool Creation**: 既存のUser Pool名との競合チェック
- **Client Secret Generation**: シークレット生成失敗時のリトライ機能
- **Secrets Manager**: シークレット保存失敗時のロールバック

### Runtime Errors
- **Authentication Failures**: M2M認証失敗時のログ出力
- **Secret Access**: Secrets Manager アクセス失敗時のエラーハンドリング
- **Token Validation**: JWTトークン検証失敗時の適切なエラーレスポンス

### Migration Errors
- **Backward Compatibility**: 既存設定との競合回避
- **Resource Naming**: リソース名の重複防止
- **Output Conflicts**: CloudFormation出力の競合解決

## Testing Strategy

### Unit Testing
- Cognito User Pool設定の検証
- App Client設定の検証
- Secrets Manager統合の検証
- CloudFormation出力の検証

### Integration Testing
- AgentCore Gateway との認証フロー
- M2M認証トークンの取得と検証
- Lambda関数呼び出しの動作確認
- エラーケースの動作確認

### Property-Based Testing
Property-based testingには**hypothesis**ライブラリを使用し、各プロパティテストは最低100回の反復実行を行います。各テストには設計ドキュメントのプロパティ番号を明示的に参照するコメントを含めます。

**テスト実行設定**: 各property-based testは以下の形式でタグ付けします：
```python
# **Feature: m2m-authentication-refactor, Property {number}: {property_text}**
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Property 1: M2M User Pool Configuration
*For any* M2M Cognito User Pool configuration, the User Pool should have self-signup disabled and support username-based sign-in for M2M authentication
**Validates: Requirements 1.1, 5.1**

Property 2: Client Credentials Flow Configuration
*For any* App Client created for M2M authentication, it should enable client credentials flow, generate a client secret, and include only the necessary authentication flows
**Validates: Requirements 1.2, 5.2**

Property 3: Custom OAuth Scope Format
*For any* custom OAuth scope definition, it should follow the exact format "HealthManager/HealthTarget:invoke" as required by AgentCore naming conventions
**Validates: Requirements 1.3, 5.5**

Property 4: Secrets Manager Integration
*For any* client secret storage operation, the secret should be stored in Secrets Manager with the correct naming format "AgentCoreIdentitySecret/HealthManager/{stack_name}" and proper encryption
**Validates: Requirements 1.4, 2.1, 2.2, 5.3**

Property 5: CloudFormation Outputs Completeness
*For any* stack deployment, all required outputs (UserPoolId, AppClientId, IdentitySecretArn, DiscoveryUrl, CustomScope) should be present and correctly formatted
**Validates: Requirements 1.5, 3.1, 3.2, 3.3, 3.4, 3.5**

Property 6: ARN Format Validation
*For any* Secrets Manager ARN output, it should follow the correct AWS ARN format and be usable by AgentCore Identity
**Validates: Requirements 2.4**

Property 7: Environment-Appropriate Removal Policies
*For any* resource with removal policy configuration, it should be set to DESTROY for development environments and appropriate policies for production
**Validates: Requirements 2.3, 5.4**

Property 8: Backward Compatibility Preservation
*For any* existing resource configuration (DynamoDB tables, Lambda functions, AgentCore Gateway/Targets, CloudFormation outputs), the refactoring should preserve the existing settings where possible
**Validates: Requirements 4.1, 4.2, 4.3, 4.4**