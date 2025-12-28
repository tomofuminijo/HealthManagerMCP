# Requirements Document

## Introduction

Healthmate-HealthManagerサービスの`test_mcp_client.py`ファイルをリファクタリングし、保守性と可読性を向上させる。現在の単一ファイル（2600行以上）を複数の専門化されたテストファイルに分割し、テストシナリオを最適化する。

## Glossary

- **MCP_Test_Framework**: Model Context Protocol テスト用フレームワーク
- **Manager_Test_Module**: 各XXXManager毎の専門化されたテストモジュール
- **Test_Data_Cleanup**: テスト用データの自動削除機能
- **Holistic_Data_Validation**: HolisticUserDataServiceによる包括的データ検証
- **Test_User_ID**: テスト識別可能なユーザーID（test-user-*形式）

## Requirements

### Requirement 1: 既存テストフォルダのクリーンアップとMCP専用構造の作成

**User Story:** 開発者として、既存の未使用テストファイルを削除し、MCPテスト専用のフォルダ構造を作成したい。これにより、テストファイルが整理され、保守性が向上する。

#### Acceptance Criteria

1. WHEN 既存の未使用ファイルを削除する THEN THE System SHALL `tests/unit/` ディレクトリとその中身を削除する
2. WHEN 既存の未使用ファイルを削除する THEN THE System SHALL `tests/integration/` ディレクトリとその中身を削除する
3. WHEN 既存の未使用ファイルを削除する THEN THE System SHALL `tests/__pycache__/` ディレクトリを削除する
4. WHEN MCPテスト用フォルダを作成する THEN THE System SHALL `tests/mcp_common/` ディレクトリを作成する
5. WHEN MCPテスト用フォルダを作成する THEN THE System SHALL `tests/mcp_managers/` ディレクトリを作成する
6. WHEN MCPテスト用フォルダを作成する THEN THE System SHALL `tests/mcp_integration/` ディレクトリを作成する

### Requirement 2: ファイル分割とモジュール化

**User Story:** 開発者として、大きなテストファイルを各Manager毎に分割したい。これにより、特定の機能のテストを独立して実行でき、コードの可読性が向上する。

#### Acceptance Criteria

1. WHEN UserManagementテストを分離する THEN THE System SHALL `tests/mcp_managers/test_user_management.py` ファイルを作成する
2. WHEN HealthGoalManagementテストを分離する THEN THE System SHALL `tests/mcp_managers/test_health_goal_management.py` ファイルを作成する
3. WHEN HealthPolicyManagementテストを分離する THEN THE System SHALL `tests/mcp_managers/test_health_policy_management.py` ファイルを作成する
4. WHEN ActivityManagementテストを分離する THEN THE System SHALL `tests/mcp_managers/test_activity_management.py` ファイルを作成する
5. WHEN BodyMeasurementManagementテストを分離する THEN THE System SHALL `tests/mcp_managers/test_body_measurement_management.py` ファイルを作成する
6. WHEN HealthConcernManagementテストを分離する THEN THE System SHALL `tests/mcp_managers/test_health_concern_management.py` ファイルを作成する
7. WHEN JournalManagementテストを分離する THEN THE System SHALL `tests/mcp_managers/test_journal_management.py` ファイルを作成する
8. WHEN HealthObservationManagementテストを分離する THEN THE System SHALL `tests/mcp_managers/test_health_observation_management.py` ファイルを作成する

### Requirement 3: 共通機能の抽出

**User Story:** 開発者として、重複するコードを共通モジュールに抽出したい。これにより、コードの重複を削減し、保守性を向上させる。

#### Acceptance Criteria

1. WHEN 認証機能を共通化する THEN THE System SHALL `tests/mcp_common/auth_client.py` ファイルを作成する
2. WHEN MCP通信機能を共通化する THEN THE System SHALL `tests/mcp_common/mcp_client.py` ファイルを作成する
3. WHEN テスト用ユーティリティを共通化する THEN THE System SHALL `tests/mcp_common/test_utils.py` ファイルを作成する
4. WHEN 設定管理を共通化する THEN THE System SHALL `tests/mcp_common/config.py` ファイルを作成する

### Requirement 4: テストシナリオの最適化

**User Story:** 開発者として、複雑なテストケースを必要最低限のシナリオに簡素化したい。これにより、テスト実行時間を短縮し、重要な機能に焦点を当てる。

#### Acceptance Criteria

1. WHEN 各Managerのテストを実行する THEN THE System SHALL 基本的なCRUD操作（Create, Read, Update, Delete）をテストする
2. WHEN エラーケースをテストする THEN THE System SHALL 主要なエラーパターンのみをテストする
3. WHEN データ整合性をテストする THEN THE System SHALL 重要なビジネスロジックのみを検証する
4. WHEN パフォーマンステストを実行する THEN THE System SHALL 必要最低限の負荷テストのみを実行する

### Requirement 5: HolisticUserDataServiceによる包括的検証

**User Story:** 開発者として、全てのテストデータがHolisticUserDataServiceで正しく取得できることを確認したい。これにより、データの整合性と完全性を保証する。

#### Acceptance Criteria

1. WHEN 全てのManagerテストが完了した後 THEN THE System SHALL HolisticUserDataService.GetUserHolisticDataを呼び出す
2. WHEN HolisticDataを取得する THEN THE System SHALL 全ての想定する属性が含まれていることを検証する
3. WHEN ユーザープロファイルを検証する THEN THE System SHALL userProfile セクションの必須フィールドを確認する
4. WHEN 健康目標を検証する THEN THE System SHALL goals セクションにテストで作成した目標が含まれることを確認する
5. WHEN 健康ポリシーを検証する THEN THE System SHALL policies セクションにテストで作成したポリシーが含まれることを確認する
6. WHEN 活動履歴を検証する THEN THE System SHALL activities セクションにテストで作成した活動が含まれることを確認する
7. WHEN 身体測定データを検証する THEN THE System SHALL bodyMeasurements セクションにテストで作成した測定データが含まれることを確認する
8. WHEN 健康コンサーンを検証する THEN THE System SHALL concerns セクションにテストで作成したコンサーンが含まれることを確認する
9. WHEN 日記データを検証する THEN THE System SHALL reflection セクションにテストで作成した日記が含まれることを確認する
10. WHEN 経過観測を検証する THEN THE System SHALL observations セクションにテストで作成した観測が含まれることを確認する

### Requirement 6: テストデータの自動削除

**User Story:** 開発者として、テスト実行後にテスト用データを自動削除したい。これにより、テスト環境を清潔に保ち、次回のテスト実行に影響を与えない。

#### Acceptance Criteria

1. WHEN 削除機能があるMCPツールを使用する THEN THE System SHALL テスト完了後に作成したデータを削除する
2. WHEN UserManagementテストが完了する THEN THE System SHALL 作成したユーザーデータを削除しない（削除機能なし）
3. WHEN HealthGoalManagementテストが完了する THEN THE System SHALL DeleteGoalツールを使用して作成した目標を削除する
4. WHEN HealthPolicyManagementテストが完了する THEN THE System SHALL DeletePolicyツールを使用して作成したポリシーを削除する
5. WHEN ActivityManagementテストが完了する THEN THE System SHALL DeleteActivityツールを使用して作成した活動を削除する
6. WHEN BodyMeasurementManagementテストが完了する THEN THE System SHALL DeleteBodyMeasurementツールを使用して作成した測定データを削除する
7. WHEN HealthConcernManagementテストが完了する THEN THE System SHALL DeleteConcernツールを使用して作成したコンサーンを削除する
8. WHEN JournalManagementテストが完了する THEN THE System SHALL DeleteJournalツールを使用して作成した日記を削除する
9. WHEN HealthObservationManagementテストが完了する THEN THE System SHALL DeleteObservationツールを使用して作成した観測を削除する

### Requirement 7: テストユーザーIDの識別可能性

**User Story:** 開発者として、テスト用データかどうかを簡単に識別したい。これにより、本番データとテストデータを区別し、誤った操作を防ぐ。

#### Acceptance Criteria

1. WHEN テストユーザーIDを生成する THEN THE System SHALL `test-user-{8桁のランダム文字列}` 形式を使用する
2. WHEN テストデータを作成する THEN THE System SHALL 全てのデータにテストユーザーIDを関連付ける
3. WHEN テストデータを識別する THEN THE System SHALL userIdの先頭が "test-user-" であることで判別可能にする
4. WHEN ログを出力する THEN THE System SHALL テストユーザーIDを含めてテスト実行を追跡可能にする

### Requirement 8: 統合テストの実装

**User Story:** 開発者として、全てのManagerテストを統合して実行する機能が欲しい。これにより、システム全体の動作を一括で検証できる。

#### Acceptance Criteria

1. WHEN 統合テストを実行する THEN THE System SHALL `tests/mcp_integration/test_all_managers.py` で全てのManagerテストを順次実行する
2. WHEN 個別Managerテストが失敗する THEN THE System SHALL エラーを記録して次のテストに進む
3. WHEN 全てのManagerテストが完了する THEN THE System SHALL HolisticUserDataServiceテストを実行する
4. WHEN テストデータ削除を実行する THEN THE System SHALL 削除可能な全てのテストデータを削除する
5. WHEN テスト結果を報告する THEN THE System SHALL 成功・失敗の詳細なサマリーを表示する

### Requirement 9: エラーハンドリングとログ出力

**User Story:** 開発者として、テスト実行中のエラーを適切にハンドリングし、詳細なログを出力したい。これにより、問題の特定と解決を迅速に行える。

#### Acceptance Criteria

1. WHEN MCPツール呼び出しでエラーが発生する THEN THE System SHALL エラー詳細をログに記録する
2. WHEN ネットワークエラーが発生する THEN THE System SHALL リトライ機能を提供する
3. WHEN 認証エラーが発生する THEN THE System SHALL 明確なエラーメッセージを表示する
4. WHEN テストが完了する THEN THE System SHALL 実行時間と結果サマリーを表示する

### Requirement 10: 設定の外部化

**User Story:** 開発者として、テスト設定を外部ファイルで管理したい。これにより、環境に応じた設定変更を容易にする。

#### Acceptance Criteria

1. WHEN テスト設定を管理する THEN THE System SHALL 環境変数から設定を読み込む
2. WHEN CloudFormation出力を取得する THEN THE System SHALL 動的に設定値を取得する
3. WHEN タイムアウト値を設定する THEN THE System SHALL 設定可能なタイムアウト値を提供する
4. WHEN デバッグモードを有効にする THEN THE System SHALL 詳細なデバッグ情報を出力する