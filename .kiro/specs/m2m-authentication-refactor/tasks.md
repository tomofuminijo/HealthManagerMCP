# Implementation Plan

- [x] 1. CDKスタックのバックアップと準備
  - 現在のCDKスタック設定をバックアップ
  - 必要なCDKライブラリの依存関係を確認
  - AWS Secrets Manager CDKモジュールのインポート追加
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 2. M2M認証用Cognito User Poolの実装
- [x] 2.1 既存User Pool設定の削除と新規作成
  - 既存のユーザー認証用User Pool設定を削除
  - M2M認証専用のUser Pool設定を実装
  - セルフサインアップ無効化とユーザー名ベース認証の設定
  - _Requirements: 1.1, 5.1_

- [ ]* 2.2 User Pool設定のプロパティテスト実装
  - **Property 1: M2M User Pool Configuration**
  - **Validates: Requirements 1.1, 5.1**

- [x] 2.3 M2M App Clientの実装
  - クライアントクレデンシャルフロー対応のApp Client作成
  - クライアントシークレット生成の有効化
  - 必要最小限の認証フローのみ許可
  - _Requirements: 1.2, 5.2_

- [ ]* 2.4 App Client設定のプロパティテスト実装
  - **Property 2: Client Credentials Flow Configuration**
  - **Validates: Requirements 1.2, 5.2**

- [x] 3. カスタムOAuthスコープの実装
- [x] 3.1 AgentCore用カスタムスコープの定義
  - "HealthManager/HealthTarget:invoke"形式のスコープ実装
  - App ClientのOAuth設定にカスタムスコープを追加
  - _Requirements: 1.3, 5.5_

- [ ]* 3.2 カスタムスコープ形式のプロパティテスト実装
  - **Property 3: Custom OAuth Scope Format**
  - **Validates: Requirements 1.3, 5.5**

- [x] 4. Secrets Manager統合の実装
- [x] 4.1 クライアントシークレットのSecrets Manager保存
  - Secrets Managerリソースの作成
  - 適切な命名規則での保存実装
  - CDK SecretValueメカニズムの使用
  - _Requirements: 1.4, 2.1, 2.2, 5.3_

- [ ]* 4.2 Secrets Manager統合のプロパティテスト実装
  - **Property 4: Secrets Manager Integration**
  - **Validates: Requirements 1.4, 2.1, 2.2, 5.3**

- [x] 4.3 RemovalPolicy設定の実装
  - 開発環境用のDESTROYポリシー設定
  - 環境別設定の実装
  - _Requirements: 2.3, 5.4_

- [ ]* 4.4 RemovalPolicy設定のプロパティテスト実装
  - **Property 7: Environment-Appropriate Removal Policies**
  - **Validates: Requirements 2.3, 5.4**

- [x] 5. CloudFormation出力の実装
- [x] 5.1 AgentCore連携用出力の追加
  - User Pool ID、App Client ID、Secrets Manager ARNの出力
  - OIDC Discovery URLの出力
  - カスタムOAuthスコープの出力
  - _Requirements: 1.5, 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ]* 5.2 CloudFormation出力のプロパティテスト実装
  - **Property 5: CloudFormation Outputs Completeness**
  - **Validates: Requirements 1.5, 3.1, 3.2, 3.3, 3.4, 3.5**

- [x] 5.3 ARN形式検証の実装
  - Secrets Manager ARNの形式検証
  - AgentCore Identity用の適切なARN出力
  - _Requirements: 2.4_

- [ ]* 5.4 ARN形式のプロパティテスト実装
  - **Property 6: ARN Format Validation**
  - **Validates: Requirements 2.4**

- [x] 6. 後方互換性の確保
- [x] 6.1 既存リソース設定の保持
  - DynamoDBテーブル設定の保持確認
  - Lambda関数設定の保持確認
  - AgentCore Gateway/Target設定の保持確認
  - 既存CloudFormation出力名の可能な限りの保持
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ]* 6.2 後方互換性のプロパティテスト実装
  - **Property 8: Backward Compatibility Preservation**
  - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**

- [-] 7. 統合テストとデプロイメント検証
- [ ] 7.1 CDKスタックのデプロイテスト
  - 新しいM2M認証設定でのスタックデプロイ
  - CloudFormation出力の確認
  - Secrets Managerの動作確認
  - _Requirements: 全要件_

- [ ]* 7.2 統合テストの実装
  - M2M認証フローの統合テスト
  - AgentCore Gateway連携テスト
  - エラーケースの動作確認

- [ ] 8. 最終チェックポイント
  - すべてのテストが通ることを確認し、問題があれば質問する