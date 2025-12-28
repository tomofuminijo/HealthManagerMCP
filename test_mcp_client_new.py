#!/usr/bin/env python3
"""
HealthManagerMCP 新テストフレームワーク実行スクリプト

リファクタリングされた新しいテストフレームワークを使用して
HealthManagerMCPシステムの包括的なテストを実行します。

特徴:
- Manager自動発見システム
- 拡張可能なプラグイン型アーキテクチャ
- HolisticUserDataServiceでの包括的検証
- 自動テストデータクリーンアップ
- 詳細なテスト結果レポート

使用方法:
    # 統合テスト実行
    python test_mcp_client_new.py
    
    # デバッグモード
    MCP_DEBUG_MODE=true python test_mcp_client_new.py
    
    # 特定の環境
    HEALTHMATE_ENV=stage python test_mcp_client_new.py
"""

import sys
import os

# テストパッケージをPythonパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tests.mcp_integration.test_all_managers import main

if __name__ == "__main__":
    print("🚀 HealthManager MCP新テストフレームワーク")
    print("="*60)
    print("📋 新機能:")
    print("  ✅ Manager自動発見システム")
    print("  ✅ 拡張可能なプラグイン型アーキテクチャ")
    print("  ✅ HolisticUserDataService包括検証")
    print("  ✅ 自動テストデータクリーンアップ")
    print("  ✅ 詳細なテスト結果レポート")
    print("="*60)
    
    # 環境情報表示
    environment = os.environ.get('HEALTHMATE_ENV', 'dev')
    debug_mode = os.environ.get('MCP_DEBUG_MODE', 'false').lower() == 'true'
    
    print(f"🌍 実行環境: {environment}")
    print(f"🔍 デバッグモード: {'有効' if debug_mode else '無効'}")
    print()
    
    # メイン実行
    exit_code = main()
    
    print(f"\n🏁 テスト完了 (終了コード: {exit_code})")
    sys.exit(exit_code)