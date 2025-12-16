# GitHubリポジトリ名変更手順書

## 概要

HealthManagerMCP リポジトリを「Healthmate-HealthManager」に名前変更するための手順書です。

## 前提条件

- GitHubリポジトリへの管理者権限
- ローカルでの変更が完了していること
- 全ての変更がコミット・プッシュされていること

## 手順

### 1. GitHubでのリポジトリ名変更

1. **GitHubリポジトリページにアクセス**
   ```
   https://github.com/tomofuminijo/HealthManagerMCP
   ```

2. **Settings タブをクリック**

3. **Repository name セクションを見つける**
   - ページを下にスクロールして「Repository name」セクションを探す

4. **新しい名前を入力**
   ```
   Healthmate-HealthManager
   ```

5. **「Rename」ボタンをクリック**
   - 確認ダイアログが表示されるので、リポジトリ名を再入力
   - 「I understand, rename this repository」をクリック

### 2. ローカルリポジトリのリモートURL更新

リポジトリ名変更後、ローカルリポジトリのリモートURLを更新する必要があります：

```bash
# 現在のリモートURLを確認
git remote -v

# 新しいリモートURLに更新
git remote set-url origin https://github.com/tomofuminijo/Healthmate-HealthManager.git

# 更新を確認
git remote -v

# 接続テスト
git fetch origin
```

### 3. 他の開発者への通知

チーム内の他の開発者に以下の情報を共有：

```bash
# 既存のクローンがある場合のリモートURL更新コマンド
git remote set-url origin https://github.com/tomofuminijo/Healthmate-HealthManager.git

# 新しいクローンコマンド
git clone https://github.com/tomofuminijo/Healthmate-HealthManager.git
```

### 4. CI/CD設定の確認

GitHub Actionsやその他のCI/CDサービスで以下を確認：

- **GitHub Actions**: 自動的に新しいリポジトリ名で動作
- **外部CI/CD**: Webhook URLやリポジトリ参照を手動更新が必要な場合あり
- **デプロイメント設定**: リポジトリURLを参照している設定があれば更新

### 5. ドキュメント・リンクの更新

以下のドキュメント内のリンクを更新：

- README.md（既に更新済み）
- SETUP.md（既に更新済み）
- 外部ドキュメントやWikiページ
- 他のプロジェクトからの参照

## 注意事項

### リダイレクト

- GitHubは古いURL（HealthManagerMCP）から新しいURL（Healthmate-HealthManager）への自動リダイレクトを提供
- リダイレクトは永続的ですが、新しいURLの使用を推奨

### 影響範囲

- **Git操作**: clone, fetch, push は新しいURLで実行
- **Issues/PRs**: 既存のIssuesやPull Requestsは自動的に新しいリポジトリに移行
- **Stars/Forks**: スター数やフォーク数は保持される
- **Webhooks**: 既存のWebhookは新しいURLで継続動作

### ロールバック

万が一問題が発生した場合：

1. **GitHubで再度名前変更**
   - 同じ手順で元の名前「HealthManagerMCP」に戻す

2. **ローカルリモートURL復元**
   ```bash
   git remote set-url origin https://github.com/tomofuminijo/HealthManagerMCP.git
   ```

## 確認事項

リポジトリ名変更後、以下を確認：

- [ ] 新しいURLでリポジトリにアクセス可能
- [ ] ローカルからのgit push/pull が正常動作
- [ ] CI/CDパイプラインが正常動作
- [ ] 外部サービスとの連携が正常動作
- [ ] チームメンバーがアクセス可能

## 完了

全ての手順が完了したら、この手順書は削除またはアーカイブしてください。