# 要件定義書

## 概要

HealthManagerサービスにJournal Management（日記管理）機能を追加します。ユーザーが毎日の振り返りを記録し、気分スコアとタグを管理できる機能を提供します。AIエージェントとの自然な対話を通じて日記を記録し、メンタルヘルスの傾向分析に活用できるシステムを構築します。

## 用語集

- **JournalManagement**: 日記管理システム
- **Journal_Entry**: 個別の日記エントリー（一日一件）
- **Mood_Score**: 1（悪い）から5（良い）までの5段階気分評価
- **Content_Tags**: AIが自動生成する3-5個の英語タグ（分析用）
- **MCP_Tool**: Model Context Protocol ツール
- **DynamoDB_Table**: 日記データを格納するテーブル
- **Mental_Health_Analysis**: メンタルヘルス傾向分析

## 要件

### 要件 1

**ユーザーストーリー:** ユーザーとして、AIエージェントとの自然な対話を通じて毎日の振り返りを記録したい。継続的な日記習慣を維持し、メンタルヘルスを追跡できるようにするため。

#### 受入基準

1. ユーザーが毎日の振り返りを共有したとき、JournalManagement は指定された日付の新しい日記エントリーを作成する
2. ユーザーが気分スコア（1-5）を提供したとき、JournalManagement はそれを日記エントリーと共に記録する
3. ユーザーが振り返り内容を提供したとき、JournalManagement はその内容からAIが自動的にタグを生成し保存する
4. 指定された日付の日記エントリーが既に存在するとき、JournalManagement は新しいコンテンツを既存のエントリーに追記する
5. 日付が指定されていないとき、JournalManagement はユーザーのタイムゾーンでの現在の日付を使用する

### 要件 2

**ユーザーストーリー:** ユーザーとして、日記エントリーが適切なデータ構造で永続的に保存されることを望む。毎日の振り返りと気分パターンの完全な記録を維持できるようにするため。

#### 受入基準

1. JournalManagement は各日記エントリーをDynamoDBにユーザーIDをパーティションキーとして保存する
2. 日記エントリーを保存するとき、JournalManagement はパーティションキーとしてユーザーIDをそのまま使用する
3. 日記エントリーを保存するとき、JournalManagement はソートキーとして日付（YYYY-MM-DD）をそのまま使用する
4. JournalManagement は日記コンテンツを無制限長のテキストとして保存する
5. JournalManagement は気分スコアを1から5の間の整数として保存する
6. JournalManagement は振り返り内容から自動生成された3-5個の英語タグを文字列の配列として保存する
7. JournalManagement はcreatedAtタイムスタンプをISO 8601形式で記録する
8. JournalManagement はupdatedAtタイムスタンプをISO 8601形式で記録する

### 要件 3

**ユーザーストーリー:** ユーザーとして、特定の日付や日付範囲の日記エントリーを取得したい。過去の振り返りを確認し、メンタルヘルスのパターンを追跡できるようにするため。

#### 受入基準

1. ユーザーが特定の日付の日記エントリーを要求したとき、JournalManagement は存在する場合はそのエントリーを返す
2. ユーザーが日付範囲の日記エントリーを要求したとき、JournalManagement は指定された期間内のすべてのエントリーを返す
3. 要求された日付の日記エントリーが存在しないとき、JournalManagement は適切な「見つかりません」レスポンスを返す
4. JournalManagement は最大365日までの日付範囲クエリをサポートする
5. JournalManagement は日記エントリーを日付順（時系列）でソートして返す

### 要件 4

**ユーザーストーリー:** ユーザーとして、日記エントリーを更新または置換したい。間違いを修正したり、毎日の記録に追加の振り返りを加えたりできるようにするため。

#### 受入基準

1. ユーザーが日記エントリーの更新を要求したとき、JournalManagement は既存のコンテンツを新しいコンテンツで置換する
2. 日記エントリーが更新されたとき、JournalManagement はupdatedAtタイムスタンプを更新する
3. 日記エントリーを更新するとき、JournalManagement は元のcreatedAtタイムスタンプを保持する
4. 日記エントリーを更新するとき、JournalManagement はコンテンツ、気分スコア、自動生成タグの変更を許可する
5. 存在しない日記エントリーを更新するとき、JournalManagement は適切なエラーメッセージを返す

### 要件 5

**ユーザーストーリー:** ユーザーとして、必要に応じて日記エントリーを削除したい。記録に残したくないエントリーを削除できるようにするため。

#### 受入基準

1. ユーザーが日記エントリーの削除を要求したとき、JournalManagement はデータベースからそのエントリーを削除する
2. 日記エントリーを削除するとき、JournalManagement はそのエントリーが認証されたユーザーのものであることを確認する
3. 存在しない日記エントリーを削除しようとしたとき、JournalManagement は適切なエラーメッセージを返す
4. 日記エントリーが正常に削除されたとき、JournalManagement は確認メッセージを返す
5. JournalManagement は削除された日記エントリーの復旧を許可しない

### 要件 6

**ユーザーストーリー:** 開発者として、日記管理のためのMCPツールが欲しい。AIエージェントが標準化されたインターフェースを通じて日記データと相互作用できるようにするため。

#### 受入基準

1. JournalManagement は特定の日付の日記エントリーを取得するための "getJournal" MCP_Tool を提供する
2. JournalManagement は日付範囲内の日記エントリーを取得するための "getJournalsInRange" MCP_Tool を提供する
3. JournalManagement は新しい日記エントリーを作成または既存のものに追記するための "addJournal" MCP_Tool を提供する
4. JournalManagement は既存の日記エントリーを置換するための "updateJournal" MCP_Tool を提供する
5. JournalManagement は日記エントリーを削除するための "deleteJournal" MCP_Tool を提供する
6. MCPツールが呼び出されたとき、JournalManagement はJWTトークンを通じてユーザー認証を検証する
7. MCPツールが呼び出されたとき、JournalManagement はデータ分離のためにJWTトークンからユーザーIDを抽出する
8. addJournalツールは振り返り内容から自動的にタグを生成し、分析に適した形式で保存する

### 要件 7

**ユーザーストーリー:** ユーザーとして、日記データが検証され安全に処理されることを望む。個人的な振り返りのセキュリティと整合性を信頼できるようにするため。

#### 受入基準

1. 無効な気分スコアが提供されたとき、JournalManagement は入力を拒否し、説明的なエラーメッセージを返す
2. JournalManagement は気分スコアが1から5までの整数であることを検証する
3. JournalManagement は日付がYYYY-MM-DD形式であることを検証する
4. JournalManagement は日付が未来でないことを検証する
5. 日記コンテンツが合理的な制限を超えたとき、JournalManagement は入力を切り詰めるか拒否する
6. JournalManagement はセキュリティ脆弱性を防ぐために日記コンテンツをサニタイズする
7. 日記データにアクセスするとき、JournalManagement はデータが認証されたユーザーのものであることを確認する

### 要件 8

**ユーザーストーリー:** システム管理者として、日記システムが既存のHealthManagerインフラストラクチャとシームレスに統合されることを望む。他の健康データ管理機能との一貫性を維持するため。

#### 受入基準

1. JournalManagement は既存のHealthManager MCPツールと同じ認証パターンを使用する
2. JournalManagement は既存のLambda関数と同じエラーハンドリングパターンに従う
3. JournalManagement は "healthmate-" プレフィックスを持つ一貫したDynamoDBテーブル命名規則を使用する
4. JournalManagement は既存のサービスと同じログ記録および監視パターンを実装する
5. JournalManagement は既存のCDKインフラストラクチャスタックを通じてデプロイ可能である
6. JournalManagement は既存のツールと同じMCPスキーマ形式に従う
7. JournalManagement は既存のLambda関数アーキテクチャパターンと統合する

### 要件 9

**ユーザーストーリー:** メンタルヘルス研究者として、日記データが分析とパターン認識をサポートすることを望む。ユーザーが時間の経過に伴うメンタルヘルスの傾向について洞察を得られるようにするため。

#### 受入基準

1. JournalManagement はトレンド分析に適した形式でタグを保存する
2. JournalManagement は一貫したタグ形式（英語、PascalCase、標準化）を維持する
3. 日付範囲で日記エントリーを取得するとき、JournalManagement は分析用のすべてのメタデータを含める
4. JournalManagement は時間の経過に伴う気分スコアパターンの効率的なクエリをサポートする
5. JournalManagement は縦断的分析のための履歴データの整合性を保持する
6. JournalManagement は活動、感情、健康症状、環境に関するタグを自動生成し、分析の集約に適したPascalCase形式で保存する