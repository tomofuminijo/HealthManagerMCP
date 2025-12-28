# Implementation Plan: MCP Test Refactoring

## Overview

Healthmate-HealthManagerサービスの`test_mcp_client.py`ファイル（2600行以上）を、保守性と拡張性を向上させるために複数の専門化されたモジュールにリファクタリングする。実際のユーザー使用パターンに基づくテストシナリオを実装し、新しいManagerテストの追加を容易にする拡張可能な設計を採用する。

## Tasks

- [x] 1. 既存テストフォルダのクリーンアップ
  - 未使用の`tests/unit/`ディレクトリとその中身を削除
  - 未使用の`tests/integration/`ディレクトリとその中身を削除  
  - `tests/__pycache__/`ディレクトリを削除
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. MCPテスト専用フォルダ構造の作成
  - `tests/mcp_common/`ディレクトリを作成
  - `tests/mcp_managers/`ディレクトリを作成
  - `tests/mcp_integration/`ディレクトリを作成
  - 各ディレクトリに`__init__.py`ファイルを作成
  - _Requirements: 1.4, 1.5, 1.6_

- [x] 3. 共通機能モジュールの実装
  - [x] 3.1 設定管理モジュールの作成
    - `tests/mcp_common/config.py`を作成
    - CloudFormation出力の動的取得機能を実装
    - 環境変数からの設定読み込み機能を実装
    - _Requirements: 3.4, 10.1, 10.2_

  - [x] 3.2 認証クライアントモジュールの作成
    - `tests/mcp_common/auth_client.py`を作成
    - Cognito M2M認証（Client Credentials Flow）を実装
    - JWTトークンの自動管理機能を実装
    - _Requirements: 3.1_

  - [x] 3.3 MCP通信クライアントモジュールの作成
    - `tests/mcp_common/mcp_client.py`を作成
    - MCPプロトコル通信機能を実装
    - エラーハンドリングとリトライ機能を実装
    - _Requirements: 3.2, 9.1, 9.2_

  - [x] 3.4 テスト用ユーティリティモジュールの作成
    - `tests/mcp_common/test_utils.py`を作成
    - テストユーザーID生成機能（test-user-{8桁}形式）を実装
    - MCPレスポンス解析機能を実装
    - _Requirements: 3.3, 7.1, 7.2_

- [x] 4. 拡張可能な基底クラスの実装
  - [x] 4.1 BaseManagerTestクラスの作成
    - `tests/mcp_common/base_manager_test.py`を作成
    - 抽象基底クラスとしてインターフェースを定義
    - テンプレートメソッドパターンで共通実行フローを実装
    - 自動テスト実行機能を実装
    - _Requirements: 2.1-2.8, 4.1_

  - [x] 4.2 Manager自動発見システムの作成
    - `tests/mcp_common/manager_registry.py`を作成
    - 動的なManagerテストクラス発見機能を実装
    - プラグイン型アーキテクチャのサポート機能を実装
    - _Requirements: 8.1_

- [x] 5. 各Manager専用テストモジュールの実装
  - [x] 5.1 UserManagementテストの作成
    - `tests/mcp_managers/test_user_management.py`を作成
    - AddUser, UpdateUser, GetUserツールのテストを実装
    - BaseManagerTestを継承した実装
    - _Requirements: 2.1_

  - [x] 5.2 HealthGoalManagementテストの作成
    - `tests/mcp_managers/test_health_goal_management.py`を作成
    - AddGoal, GetGoals, UpdateGoal, DeleteGoalツールのテストを実装
    - 削除機能付きテストデータ管理を実装
    - _Requirements: 2.2, 6.3_

  - [x] 5.3 HealthPolicyManagementテストの作成
    - `tests/mcp_managers/test_health_policy_management.py`を作成
    - AddPolicy, GetPolicies, UpdatePolicy, DeletePolicyツールのテストを実装
    - 削除機能付きテストデータ管理を実装
    - _Requirements: 2.3, 6.4_

  - [x] 5.4 ActivityManagementテストの作成
    - `tests/mcp_managers/test_activity_management.py`を作成
    - AddActivities, GetActivities, UpdateActivity, UpdateActivities, DeleteActivity, GetActivitiesInRangeツールのテストを実装
    - 複数日活動データのテストシナリオを実装
    - _Requirements: 2.4, 6.5_

  - [x] 5.5 BodyMeasurementManagementテストの作成
    - `tests/mcp_managers/test_body_measurement_management.py`を作成
    - AddBodyMeasurement, GetLatestMeasurements, GetOldestMeasurements, GetMeasurementHistory, UpdateBodyMeasurement, DeleteBodyMeasurementツールのテストを実装
    - Latest/Oldest検証機能を含む複数日測定データのテストシナリオを実装
    - _Requirements: 2.5, 6.6_

  - [x] 5.6 HealthConcernManagementテストの作成
    - `tests/mcp_managers/test_health_concern_management.py`を作成
    - AddConcern, GetConcerns, UpdateConcern, DeleteConcernツールのテストを実装
    - フィルタリング機能のテストを実装
    - _Requirements: 2.6, 6.7_

  - [x] 5.7 JournalManagementテストの作成
    - `tests/mcp_managers/test_journal_management.py`を作成
    - AddJournal, GetJournal, GetJournalsInRange, UpdateJournal, DeleteJournalツールのテストを実装
    - 日記の追記・更新機能のテストを実装
    - _Requirements: 2.7, 6.8_

  - [x] 5.8 HealthObservationManagementテストの作成
    - `tests/mcp_managers/test_health_observation_management.py`を作成
    - AddObservation, GetObservation, GetObservations, UpdateObservation, CompleteObservation, CancelObservationツールのテストを実装
    - 複数観測の完了・キャンセルシナリオを実装
    - _Requirements: 2.8, 6.9_

- [x] 6. 統合テストモジュールの実装
  - [x] 6.1 統合テストメインファイルの作成
    - `tests/mcp_integration/test_all_managers.py`を作成
    - Manager自動発見機能を使用した統合テスト実行を実装
    - 実際のユーザー使用パターンに基づくテストシナリオを実装
    - _Requirements: 8.1, 8.2_

  - [x] 6.2 HolisticUserDataServiceテストの実装
    - HolisticUserDataService.GetUserHolisticDataツールのテストを実装
    - 全ての想定属性の包括的検証機能を実装
    - タイムライン検証（latest/oldest）機能を実装
    - _Requirements: 5.1-5.10_

  - [x] 6.3 テストデータ自動削除機能の実装
    - 削除機能があるツールでの自動クリーンアップを実装
    - 削除順序の管理（依存関係を考慮した逆順実行）を実装
    - 削除機能がないツールのデータ保持確認を実装
    - _Requirements: 6.1, 6.2, 8.4_

- [x] 7. エラーハンドリングとログ機能の実装
  - [x] 7.1 統一エラーハンドリングの実装
    - `tests/mcp_common/error_handler.py`を作成
    - MCPエラー、認証エラー、ネットワークエラーの統一処理を実装
    - エラーログの詳細記録機能を実装
    - _Requirements: 9.1, 9.3_

- [ ]* 7.2 テスト結果レポート機能の実装
    - 拡張可能なテスト結果サマリー生成機能を実装
    - 実行時間とパフォーマンス情報の表示機能を実装
    - テストユーザーIDを含むログ出力機能を実装
    - _Requirements: 8.5, 9.4, 7.4_

- [ ]* 8. 互換性維持とマイグレーション
  - [ ]* 8.1 既存test_mcp_client.pyの更新
    - 新しいテストフレームワークを使用するように更新
    - 既存の実行方法との互換性を維持
    - 段階的移行のサポート機能を実装

  - [ ]* 8.2 実行スクリプトの作成
    - 個別Managerテスト実行スクリプトを作成
    - 統合テスト実行スクリプトを作成
    - CI/CD対応のテスト実行設定を作成

- [x] 9. テスト実行と検証
  - [x] 9.1 個別Managerテストの実行確認
    - 各Managerテストが独立して正常実行されることを確認
    - テストデータの作成・更新・削除が正常動作することを確認
    - エラーハンドリングが適切に動作することを確認

  - [x] 9.2 統合テストの実行確認
    - 全Managerテストの自動発見・実行が正常動作することを確認
    - HolisticUserDataServiceでの包括的検証が正常動作することを確認
    - テストデータの自動削除が正常動作することを確認

  - [ ]* 9.3 拡張性の検証
    - 新しいManagerテストの追加手順を検証
    - 自動発見システムが新しいテストを正しく認識することを確認
    - 既存テストに影響を与えずに新機能が追加できることを確認

- [ ]* 10. ドキュメント作成
  - [ ]* 10.1 使用方法ドキュメントの作成
    - 新しいテストフレームワークの使用方法を文書化
    - 新しいManagerテストの追加手順を文書化
    - トラブルシューティングガイドを作成

  - [ ]* 10.2 移行ガイドの作成
    - 既存のtest_mcp_client.pyからの移行手順を文書化
    - 新旧テストフレームワークの比較表を作成
    - 段階的移行のベストプラクティスを文書化

## Notes

- 各Managerテストは独立して実行可能で、他のテストに依存しない設計
- BaseManagerTestの抽象メソッドを実装することで、新しいManagerテストの追加が容易
- Manager自動発見システムにより、新しいテストファイルを追加するだけで統合テストに自動組み込み
- 実際のユーザー使用パターンに基づくテストシナリオで、より実用的なテストを実現
- HolisticUserDataServiceによる包括的検証で、全データの整合性を保証
- 削除機能があるツールでの自動クリーンアップにより、テスト環境を清潔に保持