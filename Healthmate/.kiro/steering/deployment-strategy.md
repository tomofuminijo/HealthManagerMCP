# Healthmate デプロイ戦略

## Deployment Philosophy

Healthmate プロダクトは、**Infrastructure as Code**と**サービス独立デプロイ**を基本方針とし、各サービスが独立してデプロイ・運用できる設計を採用しています。

## Deployment Order

### 必須デプロイ順序
```
1. HealthManagerMCP サービス（基盤インフラ）
   ├── AWS CDK スタックデプロイ
   ├── DynamoDB テーブル作成
   ├── Lambda 関数デプロイ
   ├── Cognito User Pool 設定
   └── MCP Gateway 設定

2. HealthCoachAI サービス（AI エージェント）
   ├── カスタム IAM ロール作成
   ├── AgentCore Runtime デプロイ
   └── MCP クライアント設定

3. HealthmateUI サービス（フロントエンド）
   ├── 静的アセットビルド
   ├── 認証設定
   └── API エンドポイント設定
```

### 依存関係の理由
- **HealthCoachAI** は **HealthManagerMCP** の MCP Gateway が必要
- **HealthmateUI** は両サービスのエンドポイントが必要
- **Cognito** は全サービスで共有される認証基盤

## Service-Specific Deployment

### HealthManagerMCP サービス

#### Prerequisites
```bash
# AWS CLI 設定
aws configure
aws sts get-caller-identity

# CDK Bootstrap（初回のみ）
npx aws-cdk bootstrap aws://ACCOUNT-ID/us-west-2
```

#### Deployment Commands
```bash
# 環境セットアップ
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# CDK インフラデプロイ
cd cdk
npm install
cdk deploy --require-approval never

# MCP Gateway 設定
cd ..
./create-gateway-targets.sh
```

#### Verification
```bash
# DynamoDB テーブル確認
aws dynamodb list-tables --region us-west-2

# Lambda 関数確認  
aws lambda list-functions --region us-west-2 --query 'Functions[?contains(FunctionName, `healthmate`)].FunctionName'

# Gateway 確認
aws agentcore list-gateway-targets --gateway-name healthmate-gateway --region us-west-2
```

### HealthCoachAI サービス

#### Prerequisites
```bash
# HealthManagerMCP サービスのデプロイ完了確認
# CloudFormation スタック出力の確認
aws cloudformation describe-stacks --stack-name Healthmate-HealthManagerStack --region us-west-2
```

#### Deployment Commands
```bash
# 環境セットアップ
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# ワンコマンドデプロイ
./deploy_to_aws.sh
```

#### Verification
```bash
# デプロイ状態確認
python check_deployment_status.py

# エージェント動作確認
python manual_test_deployed_agent.py
```

### HealthmateUI サービス

#### Prerequisites
```bash
# 両バックエンドサービスの稼働確認
# API エンドポイントの取得
```

#### Deployment Commands
```bash
# 依存関係インストール
npm install

# 環境設定
cp .env.example .env.production
# API エンドポイント、Cognito 設定を記入

# ビルド & デプロイ
npm run build
npm run deploy
```

## Environment Management

### Development Environment
```bash
# 各サービスでローカル開発環境
# HealthManagerMCP: CDK + LocalStack
# HealthCoachAI: agentcore invoke --dev
# HealthmateUI: npm run dev
```

### Staging Environment
```bash
# 本番同等環境での統合テスト
# 全サービスを AWS にデプロイ
# E2E テスト実行
```

### Production Environment
```bash
# 本番環境への段階的デプロイ
# Blue-Green デプロイメント
# カナリアリリース
```

## Configuration Management

### Environment Variables

#### HealthManagerMCP サービス
```bash
export AWS_REGION="us-west-2"
export USERS_TABLE_NAME="healthmate-users"
export GOALS_TABLE_NAME="healthmate-goals"
export POLICIES_TABLE_NAME="healthmate-policies"
export ACTIVITIES_TABLE_NAME="healthmate-activities"
```

#### HealthCoachAI サービス
```bash
export HEALTHMANAGER_GATEWAY_ID="gateway-id-from-cloudformation"
export AWS_REGION="us-west-2"
export HEALTH_STACK_NAME="Healthmate-HealthManagerStack"
```

#### HealthmateUI サービス
```bash
export REACT_APP_MCP_GATEWAY_URL="https://gateway-id.agentcore.us-west-2.amazonaws.com"
export REACT_APP_COGNITO_CLIENT_ID="cognito-client-id"
export REACT_APP_COGNITO_DOMAIN="healthmate.auth.us-west-2.amazoncognito.com"
```

### CloudFormation Outputs
```yaml
# HealthManagerMCP スタックが出力する設定値
Outputs:
  GatewayId:
    Description: "MCP Gateway ID"
    Value: !Ref HealthmateGateway
    Export:
      Name: !Sub "${AWS::StackName}-GatewayId"
      
  UserPoolId:
    Description: "Cognito User Pool ID"
    Value: !Ref UserPool
    Export:
      Name: !Sub "${AWS::StackName}-UserPoolId"
      
  UserPoolClientId:
    Description: "Cognito Client ID"  
    Value: !Ref UserPoolClient
    Export:
      Name: !Sub "${AWS::StackName}-UserPoolClientId"
```

## Testing Strategy

### Unit Testing
```bash
# 各サービスで独立実行
# HealthManagerMCP: pytest tests/unit/ -v
# HealthCoachAI: pytest tests/ -v  
# HealthmateUI: npm test
```

### Integration Testing
```bash
# サービス間連携テスト
# HealthManagerMCP: python test_mcp_client.py
# HealthCoachAI: python manual_test_agent.py
# HealthmateUI: npm run test:integration
```

### End-to-End Testing
```bash
# 全サービス統合テスト
# Cypress/Playwright による UI テスト
# API 連携の完全フローテスト
```

## Rollback Strategy

### Service-Level Rollback
```bash
# HealthManagerMCP: CDK スタック前バージョンに戻す
cdk deploy --previous-version

# HealthCoachAI: 前バージョンのコンテナイメージにロールバック
agentcore rollback --version previous

# HealthmateUI: 前バージョンの静的アセットに切り替え
aws s3 sync s3://backup-bucket/v1.0.0/ s3://production-bucket/
```

### Database Migration Rollback
```bash
# DynamoDB スキーマ変更のロールバック
# Point-in-time recovery の活用
# バックアップからの復元
```

## Monitoring & Alerting

### Deployment Monitoring
```bash
# デプロイ成功/失敗の監視
# CloudWatch Alarms
# Slack/Email 通知
```

### Health Checks
```bash
# 各サービスのヘルスチェック
# API エンドポイントの死活監視
# レスポンス時間監視
```

## Security Considerations

### Deployment Security
- **IAM Roles**: 最小権限の原則
- **Secrets Management**: AWS Secrets Manager/Parameter Store
- **Network Security**: VPC、セキュリティグループ設定

### Runtime Security
- **JWT Validation**: 全 API で JWT 検証
- **HTTPS Enforcement**: 全通信の暗号化
- **Audit Logging**: 全操作のログ記録

## Disaster Recovery

### Backup Strategy
- **DynamoDB**: Point-in-time recovery 有効化
- **Code**: Git リポジトリの複数拠点バックアップ
- **Configuration**: Infrastructure as Code による再現性

### Recovery Procedures
```bash
# 完全復旧手順
1. AWS アカウント復旧
2. CDK による基盤再構築
3. データベース復元
4. サービス再デプロイ
5. 動作確認
```