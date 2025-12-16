# Lambda関数ツール名取得リファクタリング要件

## 概要

Healthmate-HealthManagerサービスの全Lambda関数において、現在のパラメータベースのツール名推測処理を、context.client_context.customから直接ツール名を取得する新しい仕組みに置き換えます。

## 用語集

- **Lambda関数**: AWS Lambda上で動作するHealthmate-HealthManagerのハンドラー関数
- **ツール名**: MCPプロトコルで呼び出される具体的な操作名（例：AddUser、GetGoals）
- **context**: Lambda関数の第二引数として渡される実行コンテキスト
- **client_context**: contextオブジェクト内のクライアント情報を含むプロパティ
- **bedrockAgentCoreToolName**: AgentCore Gatewayから渡されるツール名識別子

## 要件

### 要件1

**ユーザーストーリー:** 開発者として、Lambda関数のツール名取得処理を簡素化したい。現在の複雑なパラメータ推測ロジックを削除し、contextから直接ツール名を取得できるようにしたい。

#### 受け入れ基準

1. WHEN Lambda関数が呼び出されるとき、THE システムはcontext.client_context.custom['bedrockAgentCoreToolName']からツール名を取得する
2. WHEN ツール名に'__'が含まれているとき、THE システムは'__'で分割して最後の部分をツール名として使用する
3. WHEN ツール名が'_GetPolicy'のような形式のとき、THE システムは先頭の'_'を除去してツール名として使用する
4. WHEN 取得したツール名が有効でないとき、THE システムは適切なエラーメッセージを返す

### 要件2

**ユーザーストーリー:** 開発者として、UserLambda関数の既存のツール名推測処理を新しい仕組みに置き換えたい。

#### 受け入れ基準

1. WHEN UserLambda関数が呼び出されるとき、THE システムは既存のパラメータベースの推測処理を削除する
2. WHEN ツール名が'AddUser'のとき、THE システムはadd_user関数を呼び出す
3. WHEN ツール名が'UpdateUser'のとき、THE システムはupdate_user関数を呼び出す
4. WHEN ツール名が'GetUser'のとき、THE システムはget_user関数を呼び出す

### 要件3

**ユーザーストーリー:** 開発者として、HealthGoalLambda関数の既存のツール名推測処理を新しい仕組みに置き換えたい。

#### 受け入れ基準

1. WHEN HealthGoalLambda関数が呼び出されるとき、THE システムは既存のパラメータベースの推測処理を削除する
2. WHEN ツール名が'AddGoal'のとき、THE システムはadd_goal関数を呼び出す
3. WHEN ツール名が'UpdateGoal'のとき、THE システムはupdate_goal関数を呼び出す
4. WHEN ツール名が'DeleteGoal'のとき、THE システムはdelete_goal関数を呼び出す
5. WHEN ツール名が'GetGoals'のとき、THE システムはget_goals関数を呼び出す

### 要件4

**ユーザーストーリー:** 開発者として、HealthPolicyLambda関数の既存のツール名推測処理を新しい仕組みに置き換えたい。

#### 受け入れ基準

1. WHEN HealthPolicyLambda関数が呼び出されるとき、THE システムは既存のパラメータベースの推測処理を削除する
2. WHEN ツール名が'AddPolicy'のとき、THE システムはadd_policy関数を呼び出す
3. WHEN ツール名が'UpdatePolicy'のとき、THE システムはupdate_policy関数を呼び出す
4. WHEN ツール名が'DeletePolicy'のとき、THE システムはdelete_policy関数を呼び出す
5. WHEN ツール名が'GetPolicies'のとき、THE システムはget_policies関数を呼び出す

### 要件5

**ユーザーストーリー:** 開発者として、ActivityLambda関数の既存のツール名推測処理を新しい仕組みに置き換えたい。

#### 受け入れ基準

1. WHEN ActivityLambda関数が呼び出されるとき、THE システムは既存のパラメータベースの推測処理を削除する
2. WHEN ツール名が'AddActivities'のとき、THE システムはadd_activities関数を呼び出す
3. WHEN ツール名が'UpdateActivity'のとき、THE システムはupdate_activity関数を呼び出す
4. WHEN ツール名が'UpdateActivities'のとき、THE システムはupdate_activities関数を呼び出す
5. WHEN ツール名が'DeleteActivity'のとき、THE システムはdelete_activity関数を呼び出す
6. WHEN ツール名が'GetActivities'のとき、THE システムはget_activities関数を呼び出す
7. WHEN ツール名が'GetActivitiesInRange'のとき、THE システムはget_activities_in_range関数を呼び出す

### 要件6

**ユーザーストーリー:** 開発者として、リファクタリング後も既存の機能が正常に動作することを確認したい。

#### 受け入れ基準

1. WHEN リファクタリングが完了したとき、THE システムは既存のすべてのMCPツール機能を維持する
2. WHEN 各Lambda関数が呼び出されたとき、THE システムは同じレスポンス形式を返す
3. WHEN エラーが発生したとき、THE システムは適切なエラーハンドリングを行う
4. WHEN ログが出力されるとき、THE システムは新しいツール名取得方式を反映したログメッセージを出力する