# 実装タスクリスト

## 概要

このドキュメントは、HealthManagerMCP（Healthmateエコシステムの健康情報管理MCPサーバー）の実装タスクをフェーズごとに整理したものです。各タスクは要件定義書（requirements.md）の要件番号と紐付けられています。

## 実装タスク

### フェーズ1: 環境セットアップとCDK基盤

- [x] **タスク1.1**: Python仮想環境のセットアップ
  - Python 3.12の仮想環境を作成
  - 基本的な依存関係をインストール（aws-cdk-lib, boto3, pytest, hypothesis）
  - requirements.txtを作成
  - **関連要件**: なし（環境セットアップ）

- [x] **タスク1.2**: プロジェクト構造とCDKセットアップ
  - プロジェクトディレクトリ構造を作成（lambda/, cdk/, tests/）
  - CDK（Python）の初期化と依存関係のセットアップ
  - 基本的なCDKスタック定義を作成（cdk/cdk/cdk_stack.py）
  - **関連要件**: なし（環境セットアップ）

### フェーズ2: バックエンド基盤（DynamoDB + Lambda）

- [x] **タスク2.1**: DynamoDBテーブルの作成
  - ユーザーテーブルをCDKで定義（PK: userId）
  - 健康目標テーブルをCDKで定義（PK: userId, SK: goalId, GSI: goalType-index, status-index）
  - 健康ポリシーテーブルをCDKで定義（PK: userId, SK: policyId, GSI: policyType-index, isActive-index）
  - 活動記録テーブルをCDKで定義（PK: userId, SK: date, GSI: date-index）
  - すべてのテーブルでPay-per-requestモードとPoint-in-time recoveryを有効化
  - **関連要件**: 要件11（データ永続化）

- [x] **タスク2.2**: UserLambda関数の実装
  - Lambda関数の基本構造を作成（Python 3.12）
  - addUser関数を実装
  - updateUser関数を実装
  - getUser関数を実装
  - DynamoDBとの統合（boto3、指数バックオフ付き再試行）
  - エラーハンドリングと再試行ロジックを実装
  - CloudWatch Logsロググループを作成（1週間保持）
  - MCP形式に対応
  - **関連要件**: 要件2（ユーザー情報管理）、要件10（データ永続化）、要件11（エラーハンドリング）、要件12（ロギング）

- [x] **タスク2.3**: HealthGoalLambda関数の実装
  - Lambda関数の基本構造を作成（Python 3.12）
  - addGoal関数を実装（UUIDでgoalId生成）
  - updateGoal関数を実装
  - deleteGoal関数を実装
  - getGoals関数を実装
  - DynamoDBとの統合（boto3、指数バックオフ付き再試行）
  - エラーハンドリングと再試行ロジックを実装
  - CloudWatch Logsロググループを作成（1週間保持）
  - MCP形式に対応
  - **関連要件**: 要件3（健康目標管理）、要件11（データ永続化）、要件12（エラーハンドリング）、要件13（ロギング）

- [x] **タスク2.4**: HealthPolicyLambda関数の実装
  - Lambda関数の基本構造を作成（Python 3.12）
  - addPolicy関数を実装（UUIDでpolicyId生成）
  - updatePolicy関数を実装
  - deletePolicy関数を実装
  - getPolicies関数を実装
  - DynamoDBとの統合（boto3、指数バックオフ付き再試行）
  - エラーハンドリングと再試行ロジックを実装
  - CloudWatch Logsロググループを作成（1週間保持）
  - MCP形式に対応
  - **関連要件**: 要件4（健康ポリシー管理）、要件11（データ永続化）、要件12（エラーハンドリング）、要件13（ロギング）

- [x] **タスク2.5**: ActivityLambda関数の実装
  - Lambda関数の基本構造を作成（Python 3.12）
  - addActivities関数を実装（複数活動の追加）
  - updateActivity関数を実装（特定時刻の活動更新）
  - updateActivities関数を実装（全活動の置き換え）
  - deleteActivity関数を実装
  - getActivities関数を実装
  - getActivitiesInRange関数を実装（最大365日）
  - DynamoDBとの統合（boto3、指数バックオフ付き再試行）
  - エラーハンドリングと再試行ロジックを実装
  - CloudWatch Logsロググループを作成（1週間保持）
  - MCP形式に対応
  - **関連要件**: 要件5-8（活動記録管理）、要件11（データ永続化）、要件12（エラーハンドリング）、要件13（ロギング）

### フェーズ3: 認証設定

- [x] **タスク3.1**: Cognito User Poolの作成
  - Cognito User PoolをCDKで作成（healthmate-users）
  - OAuth 2.0設定（Authorization Code Grant with Client Secret）
  - スコープ設定（OPENID, PROFILE, EMAIL, PHONE）
  - トークン有効期限設定（アクセストークン: 1時間、リフレッシュトークン: 30日、IDトークン: 1時間）
  - 複数のApp Clientの作成（HealthCoachAI、HealthmateUI、ChatGPT、Claude、Gemini等のクライアント用）
  - コールバックURL設定（各クライアントのリダイレクトURL）
  - User Pool Domainの作成（healthmanagermcp）
  - **関連要件**: 要件1（ユーザー認証とアクセス制御）

### フェーズ4: MCP Gateway設定

- [x] **タスク4.1**: AgentCore Gatewayの設定
  - AgentCore GatewayをCDKで作成（healthmate-gateway）
  - HTTPSエンドポイントを有効化
  - MCPプロトコル対応を設定
  - Custom JWT Authorizerを設定（Cognito Discovery URL使用）
  - Gateway用のIAMロールを作成（Lambda呼び出し権限、Gateway取得権限）
  - **関連要件**: 要件8（MCP Gateway）

- [x] **タスク4.2**: Gateway Targetsの設定
  - UserManagement Gateway Targetを作成（CLIスクリプト）
  - HealthGoalManagement Gateway Targetを作成（CLIスクリプト）
  - HealthPolicyManagement Gateway Targetを作成（CLIスクリプト）
  - ActivityManagement Gateway Targetを作成（CLIスクリプト）
  - MCPスキーマファイルを作成（user-management-mcp-schema.json, health-goal-management-mcp-schema.json, health-policy-management-mcp-schema.json, activity-management-mcp-schema.json）
  - create-gateway-targets.shスクリプトを作成
  - delete-gateway-targets.shスクリプトを作成
  - **関連要件**: 要件9（MCP Gateway）、要件10（MCP Tools）、要件15（MCPツール選択ガイダンス）
  - **注**: Gateway TargetsはCDKでは不安定なため、CLIスクリプトで管理

### フェーズ5: デプロイと動作確認

- [x] **タスク5.1**: 初回デプロイ
  - CDKスタック全体をデプロイ（cdk deploy --require-approval never）
  - Gateway Targetsを作成（./create-gateway-targets.sh）
  - **関連要件**: すべて

- [x] **タスク5.2**: 基本動作確認
  - デプロイされたシステムの基本動作を確認
  - 各Lambda関数が正常に動作することを確認
  - DynamoDBテーブルへの読み書きが正常に動作することを確認
  - **関連要件**: すべて

### フェーズ6: テスト実装

- [x] **タスク6.1**: 単体テストの作成
  - pytest環境をセットアップ
  - UserLambdaの単体テストを作成
  - HealthGoalLambdaの単体テストを作成
  - HealthPolicyLambdaの単体テストを作成
  - ActivityLambdaの単体テストを作成
  - すべてのテストが通過することを確認
  - **関連要件**: 要件2-8（各Lambda関数の機能）

- [x] **タスク6.2**: 統合テストの作成
  - テスト用のPythonスクリプトを作成（test_mcp_client.py）
  - Cognito User Poolにテストユーザーを作成
  - OAuth 2.0フローをテスト（ユーザー認証 → JWTトークン取得）
  - JWTトークンを使用してAgentCore Gatewayに接続
  - 各Gateway Targetの動作確認：
    - UserManagement: addUser, updateUser, getUser
    - HealthGoalManagement: addGoal, updateGoal, deleteGoal, getGoals
    - HealthPolicyManagement: addPolicy, updatePolicy, deletePolicy, getPolicies
    - ActivityManagement: addActivities, updateActivity, updateActivities, deleteActivity, getActivities, getActivitiesInRange
  - MCPスキーマ準拠のテストデータ検証：
    - 全ActivityType（wakeUp, sleep, exercise, meal, snack, weight, bodyFat, mood, medication, bowelMovement, urination, symptoms, other）のテスト
    - 必須フィールドとオプションフィールドの検証
    - operationType（append, replace）の正しい使用
  - クライアント側でJWTのsubからuserIdを抽出してMCPツール呼び出しに含めることを確認
  - UpdateActivityとUpdateActivitiesの使い分けを確認
  - エラーハンドリングの動作確認（無効なJWT、存在しないリソースなど）
  - 外部AIクライアント（ChatGPT）からのMCP接続テスト
  - **関連要件**: 要件8（MCP Gateway）、すべて

### フェーズ7: ドキュメント整備

- [x] **タスク7.1**: セットアップガイドの作成
  - 環境構築手順を記載
  - デプロイ手順を記載
  - HealthCoachAI、HealthmateUIのConnector設定手順を記載
  - 外部AIクライアント（ChatGPT、Claude、Gemini等）のConnector設定手順を記載
  - トラブルシューティングを記載
  - **関連要件**: なし（ドキュメント整備）

- [x] **タスク7.2**: MCP API仕様書の作成
  - 各MCPツールのAPI仕様を記載
  - リクエスト/レスポンス形式を記載
  - エラーコードとメッセージを記載
  - HealthCoachAI向けの使用例を記載
  - 外部AIクライアント向けの使用例を記載
  - **関連要件**: なし（ドキュメント整備）

### フェーズ8: 本番環境への移行

- [ ] **タスク8.1**: 本番環境用の設定
  - DynamoDBのRemovalPolicyをRETAINに変更
  - Cognito User PoolのRemovalPolicyをRETAINに変更
  - CloudWatch Alarmsの設定
  - SNS通知の設定
  - **関連要件**: 要件12（ロギングとモニタリング）

- [ ] **タスク8.2**: セキュリティ強化
  - IAMロールの最小権限化
  - DynamoDBの行レベルアクセス制御
  - レート制限の設定
  - **関連要件**: 要件13（セキュリティとアクセス制御）

- [ ] **タスク8.3**: 本番環境へのデプロイ
  - 本番環境用のCDKスタックをデプロイ
  - 本番環境用のGateway Targetsを作成
  - 本番環境での動作確認
  - **関連要件**: すべて

## デプロイ手順

1. **CDKデプロイ**:
   ```bash
   cd cdk
   cdk deploy --require-approval never
   ```

2. **Gateway Targets削除**（既存の場合）:
   ```bash
   ./delete-gateway-targets.sh
   sleep 10  # 10秒待機
   ```

3. **Gateway Targets作成**:
   ```bash
   ./create-gateway-targets.sh
   ```

4. **動作確認**:
   - HealthCoachAIからMCP経由でアクセス
   - 外部AIクライアントからMCP経由でアクセス
   - 各MCPツールの動作を確認

## 注意事項

- Gateway TargetsはCDKでの作成が不安定なため、CLIスクリプトで管理します
- デプロイ後は必ずGateway Targetsを再作成してください
- MCPスキーマファイルを更新した場合も、Gateway Targetsの再作成が必要です
