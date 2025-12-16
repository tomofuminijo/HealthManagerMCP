# Requirements Document

## Introduction

HealthManagerMCPサービスの名前を「Healthmate-HealthManager」に変更し、アプリ名-サービス名の命名規則に統一する。この変更により、Healthmateエコシステム内での一貫性を保ち、サービスの役割を明確にする。

## Glossary

- **HealthManagerMCP**: 現在のサービス名（変更前）
- **Healthmate-HealthManager**: 新しいサービス名（変更後）
- **CDK Stack**: AWS CloudFormationスタック
- **MCP Server**: Model Context Protocol サーバー
- **Service Reference**: 他のサービスからの参照

## Requirements

### Requirement 1

**User Story:** 開発者として、サービス名を統一された命名規則に変更したい。そうすることで、Healthmateエコシステム内での一貫性を保てる。

#### Acceptance Criteria

1. WHEN フォルダ名を変更する THEN システムは新しい名前「Healthmate-HealthManager」を使用する
2. WHEN CDKスタック名を変更する THEN システムは「Healthmate-HealthManagerStack」という名前を使用する
3. WHEN クラス名を変更する THEN システムは「HealthmateHealthManagerStack」というクラス名を使用する
4. WHEN ドキュメントを更新する THEN システムは全ての参照を新しい名前に変更する
5. WHEN 他のサービスの設定を更新する THEN システムは新しいスタック名を参照する

### Requirement 2

**User Story:** 開発者として、既存のAWSリソースを保持したい。そうすることで、データの損失やサービスの中断を避けられる。

#### Acceptance Criteria

1. WHEN CDKスタックを更新する THEN システムは既存のAWSリソースを保持する
2. WHEN DynamoDBテーブルを確認する THEN システムは既存のデータを保持する
3. WHEN Lambda関数を確認する THEN システムは既存の設定を保持する
4. WHEN Cognito User Poolを確認する THEN システムは既存のユーザーを保持する
5. WHEN Gateway設定を確認する THEN システムは既存の接続を保持する

### Requirement 3

**User Story:** 開発者として、他のサービスとの連携を維持したい。そうすることで、エコシステム全体の機能を継続できる。

#### Acceptance Criteria

1. WHEN HealthCoachAIサービスを更新する THEN システムは新しいスタック名を参照する
2. WHEN HealthmateUIサービスを更新する THEN システムは新しいスタック名を参照する
3. WHEN 環境変数を更新する THEN システムは新しい設定値を使用する
4. WHEN デプロイスクリプトを更新する THEN システムは新しいスタック名でデプロイする
5. WHEN テストスクリプトを更新する THEN システムは新しい設定でテストを実行する

### Requirement 4

**User Story:** 開発者として、GitHubリポジトリ名を変更したい。そうすることで、プロジェクト全体の一貫性を保てる。

#### Acceptance Criteria

1. WHEN GitHubリポジトリ名を変更する THEN システムは新しい名前「Healthmate-HealthManager」を使用する
2. WHEN リモートURLを更新する THEN システムは新しいリポジトリURLを参照する
3. WHEN クローンコマンドを更新する THEN システムは新しいリポジトリ名を使用する
4. WHEN ドキュメント内のリンクを更新する THEN システムは新しいリポジトリURLを参照する
5. WHEN CI/CD設定を更新する THEN システムは新しいリポジトリ名を使用する

### Requirement 5

**User Story:** 開発者として、変更手順を段階的に実行したい。そうすることで、リスクを最小化し、問題が発生した場合に対処できる。

#### Acceptance Criteria

1. WHEN 変更計画を作成する THEN システムは段階的な手順を提供する
2. WHEN 各段階を実行する THEN システムは変更の影響を最小化する
3. WHEN 問題が発生する THEN システムはロールバック手順を提供する
4. WHEN 変更を検証する THEN システムは全ての機能が正常に動作することを確認する
5. WHEN 変更を完了する THEN システムは全ての参照が更新されていることを確認する