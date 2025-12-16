# ロールバック手順書

## 概要

Healthmate-HealthManager への名前変更で問題が発生した場合の緊急復旧手順です。

## 緊急度別対応

### 🚨 緊急度: 高（本番環境に影響）

#### 1. GitHubリポジトリ名を即座に戻す

```bash
# GitHubで手動操作
# 1. https://github.com/tomofuminijo/Healthmate-HealthManager にアクセス
# 2. Settings → Repository name → "HealthManagerMCP" に変更
# 3. "I understand, rename this repository" をクリック
```

#### 2. ローカルリモートURLを復元

```bash
git remote set-url origin https://github.com/tomofuminijo/HealthManagerMCP.git
git fetch origin
```

#### 3. 他のサービスの緊急復旧

```bash
# HealthCoachAI
cd ../HealthCoachAI
# manual_test_agent.py の stack_name を 'HealthManagerMCPStack' に戻す
# test_config_helper.py の default を 'HealthManagerMCPStack' に戻す
# deploy_to_aws.sh の STACK_NAME を "HealthManagerMCPStack" に戻す

# HealthmateUI  
cd ../HealthmateUI
# run_dev.py の default を "HealthManagerMCPStack" に戻す
# test_e2e_healthcoach.py の default を "HealthManagerMCPStack" に戻す
```

### ⚠️ 緊急度: 中（開発環境のみ影響）

#### Git履歴を使用した段階的ロールバック

```bash
# 現在のコミット履歴を確認
git log --oneline -10

# Phase 2の変更をロールバック
git revert HEAD  # "Phase 2: Update cross-service references..."

# Phase 1の変更をロールバック  
git revert HEAD~1  # "Phase 1: Update CDK stack name..."

# 変更をプッシュ
git push origin main
```

### 📝 緊急度: 低（計画的ロールバック）

#### 完全なファイル復元

```bash
# 特定のコミットに戻る（バックアップポイント）
git reset --hard <backup-commit-hash>

# 強制プッシュ（注意：他の開発者と調整必要）
git push --force-with-lease origin main
```

## ファイル別ロールバック手順

### CDK設定ファイル

```bash
# cdk/app.py
# Line 6: from cdk.cdk_stack import HealthManagerMCPStack
# Line 11: HealthManagerMCPStack(
# Line 13: "HealthManagerMCPStack",
# Line 19: description="HealthManagerMCP - Health Information..."

# cdk/cdk/cdk_stack.py  
# Line 21: class HealthManagerMCPStack(Stack):
# Line 23: Main CDK Stack for HealthManagerMCP Application
# All export_name values: "HealthManagerMCP-*"
```

### ドキュメントファイル

```bash
# README.md
# Title: # HealthManagerMCP
# Description: **HealthManagerMCP**は、Healthmate...
# Diagram: HealthManagerMCP<br/>MCP Server
# Project name: **HealthManagerMCP**（このプロジェクト）
# Tools description: HealthManagerMCPは以下のMCPツールを...
# Clone command: git clone https://github.com/tomofuminijo/HealthManagerMCP.git
# Directory: cd HealthManagerMCP
# Spec links: .kiro/specs/healthmanagermcp/
# Action name: "HealthManagerMCP"
# Footer: **HealthManagerMCP** - Empowering...

# SETUP.md
# Title: # HealthManagerMCP セットアップガイド
# Description: HealthManagerMCPは、Healthmate...
# Directory: cd healthmanagermcp
# Action name: HealthManagerMCP
# Final note: HealthManagerMCPを正常にデプロイし...

# MCP_API_SPECIFICATION.md
# Title: # HealthManagerMCP API仕様書
# Description: HealthManagerMCPは、Model Context Protocol...
```

### Steering ファイル

```bash
# .kiro/steering/product.md
# Title: # HealthManagerMCP サービス - MCP Backend
# Description: HealthManagerMCP サービスは、Healthmate...

# .kiro/steering/product-overview.md
# Service name: ### HealthManagerMCP サービス（このサービス）
# Service list: - **サービス**: 個別サービス（HealthManagerMCP、...
# Data flow: HealthManagerMCP サービス
# Deployment order: 1. HealthManagerMCP サービス（基盤インフラ）

# .kiro/steering/structure.md
# Directory structure: HealthManagerMCP/          # MCP server backend
# Section title: ## HealthManagerMCP Structure
# Directory example: HealthManagerMCP/
# Service list: - **HealthManagerMCP**: Backend MCP server
# Deployment order: 1. **HealthManagerMCP**: Deploy CDK stack first

# .kiro/steering/tech.md
# Backend section: ### Backend (HealthManagerMCP)
# Commands section: ### HealthManagerMCP
```

## 検証手順

ロールバック後、以下を確認：

### 1. CDK設定の確認

```bash
cd cdk
cdk synth --quiet
# エラーがないことを確認
```

### 2. 他のサービスとの連携確認

```bash
# HealthCoachAI
cd ../HealthCoachAI
python -m py_compile manual_test_agent.py
python -m py_compile test_config_helper.py

# HealthmateUI
cd ../HealthmateUI  
python -m py_compile run_dev.py
python -m py_compile test_e2e_healthcoach.py
```

### 3. Git状態の確認

```bash
git status
git remote -v
# origin が正しいURLを指していることを確認
```

## 連絡先・エスカレーション

問題が解決しない場合：

1. **技術的問題**: 開発チームリーダーに連絡
2. **AWS環境問題**: インフラチームに連絡  
3. **GitHub問題**: リポジトリ管理者に連絡

## 事後対応

ロールバック完了後：

1. **根本原因分析**: 何が問題だったかを特定
2. **改善計画**: 再実行時の対策を検討
3. **ドキュメント更新**: 学んだ教訓を手順書に反映
4. **チーム共有**: 問題と対策をチームに共有

## 注意事項

- **データ損失リスク**: `git reset --hard` や `--force-with-lease` は慎重に使用
- **チーム調整**: 他の開発者への事前通知が重要
- **本番環境**: 本番環境への影響がある場合は即座に対応
- **バックアップ**: 重要な変更前は必ずバックアップを作成