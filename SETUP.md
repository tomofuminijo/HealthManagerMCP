# HealthManagerMCP セットアップガイド

## 概要

HealthManagerMCPは、Healthmateエコシステムの健康情報管理MCPサーバーです。このガイドでは、環境構築からデプロイ、各種AIクライアントとの連携設定まで、すべての手順を説明します。

## 前提条件

### 必要なソフトウェア

- **Python 3.12以上**
- **Node.js 18以上** (AWS CDK用)
- **AWS CLI v2** (設定済み)
- **Git**

### AWS環境

- **AWSアカウント** (適切な権限を持つ)
- **AWS CLI設定** (us-west-2リージョン)
- **CDK Bootstrap** (us-west-2リージョンで実行済み)

```bash
# AWS CLI設定確認
aws configure list
aws sts get-caller-identity

# CDK Bootstrap (初回のみ)
npx aws-cdk bootstrap aws://ACCOUNT-ID/us-west-2
```

## 環境構築

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd healthmanagermcp
```

### 2. Python仮想環境のセットアップ

```bash
# Python仮想環境の作成
python3.12 -m venv .venv

# 仮想環境の有効化
source .venv/bin/activate  # macOS/Linux
# または
.venv\Scripts\activate     # Windows

# 依存関係のインストール
pip install -r requirements.txt
```

### 3. CDK環境のセットアップ

```bash
cd cdk

# Node.js依存関係のインストール
npm install

# CDK設定の確認
cdk --version
cdk list
```

## デプロイ手順

### 1. CDKスタックのデプロイ

```bash
cd cdk

# CDKスタックをデプロイ
cdk deploy --require-approval never
```

デプロイには5-10分程度かかります。完了すると以下のリソースが作成されます：

- **DynamoDBテーブル**: healthmate-users, healthmate-goals, healthmate-policies, healthmate-activities
- **Lambda関数**: UserLambda, HealthGoalLambda, HealthPolicyLambda, ActivityLambda
- **Cognito User Pool**: healthmate-users
- **AgentCore Gateway**: healthmate-gateway

### 2. Gateway Targetsの作成

```bash
cd ..  # プロジェクトルートに戻る

# Gateway Targetsを作成
./create-gateway-targets.sh
```

### 3. デプロイ確認

```bash
# DynamoDBテーブルの確認
aws dynamodb list-tables --region us-west-2

# Lambda関数の確認
aws lambda list-functions --region us-west-2 --query 'Functions[?contains(FunctionName, `healthmate`)].FunctionName'

# Gateway Targetsの確認
aws agentcore list-gateway-targets --gateway-name healthmate-gateway --region us-west-2
```

## テスト実行

### 1. 単体テストの実行

```bash
# 仮想環境が有効化されていることを確認
source .venv/bin/activate

# 単体テストを実行
pytest tests/unit/ -v
```

### 2. 統合テストの実行

```bash
# 統合テストを実行
python test_mcp_client.py
```

## AIクライアント連携設定

### ChatGPT連携

1. **ChatGPT Plus/Pro**にログイン
2. **設定** → **機能** → **Actions**を選択
3. **新しいActionを作成**をクリック
4. 以下の設定を入力：

```yaml
# Action名
HealthManagerMCP

# 説明
健康情報管理システム（ユーザー情報、健康目標、健康ポリシー、活動記録の管理）

# Schema
# 各MCPスキーマファイルの内容をコピー：
# - user-management-mcp-schema.json
# - health-goal-management-mcp-schema.json  
# - health-policy-management-mcp-schema.json
# - activity-management-mcp-schema.json

# Authentication
OAuth 2.0

# Client ID
<Cognito App ClientのClient ID>

# Client Secret  
<Cognito App ClientのClient Secret>

# Authorization URL
https://healthmanagermcp.auth.us-west-2.amazoncognito.com/oauth2/authorize

# Token URL
https://healthmanagermcp.auth.us-west-2.amazoncognito.com/oauth2/token

# Scope
openid profile email phone
```

### Claude連携 (Anthropic Console)

1. **Anthropic Console**にログイン
2. **Integrations**を選択
3. **Add Integration**をクリック
4. **Custom Integration**を選択
5. 上記と同様の設定を入力

### HealthCoachAI連携

HealthCoachAI（同じHealthmateエコシステム内）の場合：

```python
# HealthCoachAI側の設定例
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

# AgentCore Gateway接続設定
gateway_url = "https://<gateway-id>.agentcore.us-west-2.amazonaws.com"
gateway_name = "healthmate-gateway"

# Cognito認証設定
cognito_client = boto3.client('cognito-idp', region_name='us-west-2')
user_pool_id = "<user-pool-id>"
client_id = "<client-id>"
client_secret = "<client-secret>"
```

### HealthmateUI連携

HealthmateUI（Webアプリケーション）の場合：

```javascript
// JavaScript SDK設定例
import { CognitoAuth } from 'amazon-cognito-auth-js';

const authData = {
    ClientId: '<client-id>',
    AppWebDomain: 'healthmanagermcp.auth.us-west-2.amazoncognito.com',
    TokenScopesArray: ['openid', 'profile', 'email', 'phone'],
    RedirectUriSignIn: 'https://your-app.com/callback',
    RedirectUriSignOut: 'https://your-app.com/signout'
};

const auth = new CognitoAuth(authData);
```

## 設定値の取得

デプロイ後、以下のコマンドで必要な設定値を取得できます：

```bash
# Cognito User Pool ID
aws cognito-idp list-user-pools --max-items 10 --region us-west-2 --query 'UserPools[?Name==`healthmate-users`].Id' --output text

# Cognito App Client ID (例: HealthCoachAI用)
aws cognito-idp list-user-pool-clients --user-pool-id <user-pool-id> --region us-west-2 --query 'UserPoolClients[?ClientName==`HealthCoachAI`].ClientId' --output text

# Gateway ID
aws agentcore list-gateways --region us-west-2 --query 'Gateways[?Name==`healthmate-gateway`].Id' --output text
```

## トラブルシューティング

### よくある問題

#### 1. CDKデプロイエラー

```bash
# エラー: "CDK not bootstrapped"
npx aws-cdk bootstrap aws://ACCOUNT-ID/us-west-2

# エラー: "Insufficient permissions"
# IAMユーザーに以下の権限が必要：
# - AdministratorAccess (開発環境)
# - または個別のサービス権限 (本番環境)
```

#### 2. Gateway Targets作成エラー

```bash
# エラー: "Gateway not found"
# CDKデプロイが完了してから実行してください

# エラー: "Schema validation failed"
# MCPスキーマファイルの構文を確認してください
jq . user-management-mcp-schema.json
```

#### 3. 認証エラー

```bash
# エラー: "Invalid JWT token"
# トークンの有効期限を確認してください (1時間)

# エラー: "User not found"
# Cognito User Poolにユーザーが作成されているか確認してください
aws cognito-idp list-users --user-pool-id <user-pool-id> --region us-west-2
```

#### 4. Lambda関数エラー

```bash
# Lambda関数のログを確認
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/healthmate" --region us-west-2

# 特定の関数のログを表示
aws logs tail /aws/lambda/healthmate-UserLambda --region us-west-2 --follow
```

### デバッグ手順

1. **CloudWatch Logsの確認**
   - Lambda関数のログを確認
   - エラーメッセージとスタックトレースを分析

2. **DynamoDBの確認**
   - テーブルが正しく作成されているか確認
   - データが正しく保存されているか確認

3. **Cognito設定の確認**
   - User Poolの設定を確認
   - App Clientの設定を確認

4. **Gateway設定の確認**
   - Gateway Targetsのステータスを確認
   - MCPスキーマの構文を確認

## メンテナンス

### 定期的なタスク

1. **ログの監視**
   - CloudWatch Logsでエラーを監視
   - 異常なアクセスパターンを確認

2. **バックアップの確認**
   - DynamoDBのPoint-in-time recoveryが有効か確認
   - 必要に応じて手動バックアップを作成

3. **セキュリティ更新**
   - 依存関係の更新
   - セキュリティパッチの適用

### アップデート手順

```bash
# 1. コードの更新
git pull origin main

# 2. 依存関係の更新
pip install -r requirements.txt

# 3. CDKスタックの更新
cd cdk
cdk deploy --require-approval never

# 4. Gateway Targetsの再作成（MCPスキーマ変更時）
cd ..
./delete-gateway-targets.sh
sleep 10
./create-gateway-targets.sh
```

## サポート

問題が発生した場合は、以下の情報を含めてサポートに連絡してください：

1. **エラーメッセージ**の全文
2. **実行したコマンド**
3. **CloudWatch Logs**のエラーログ
4. **環境情報**（OS、Python版、AWS CLI版）

---

このセットアップガイドに従って、HealthManagerMCPを正常にデプロイし、各種AIクライアントと連携できます。