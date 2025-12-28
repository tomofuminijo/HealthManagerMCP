"""
HealthConcernManagement MCP ツールのテストモジュール

このモジュールは、HealthConcernManagement関連のMCPツールをテストします。
- AddConcern: 健康懸念の追加
- GetConcerns: 健康懸念の取得（フィルタリング機能付き）
- UpdateConcern: 健康懸念の更新
- DeleteConcern: 健康懸念の削除
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any

from ..mcp_common.base_manager_test import BaseManagerTest
from ..mcp_common.test_utils import TestUtils


class HealthConcernManagementTest(BaseManagerTest):
    """HealthConcernManagement MCPツールのテストクラス"""
    
    def get_manager_name(self) -> str:
        """Managerの名前を返す"""
        return "HealthConcernManagement"
    
    def get_tool_list(self) -> List[str]:
        """このManagerでテストするツールのリストを返す"""
        return [
            "HealthConcernManagement___AddConcern",
            "HealthConcernManagement___GetConcerns",
            "HealthConcernManagement___UpdateConcern",
            "HealthConcernManagement___DeleteConcern"
        ]
    
    def get_cleanup_tools(self) -> Dict[str, str]:
        """テストデータクリーンアップに使用するツールのマッピングを返す"""
        return {
            "HealthConcernManagement___AddConcern": "HealthConcernManagement___DeleteConcern"
        }
    
    def get_required_test_data(self) -> Dict[str, Any]:
        """テスト用の健康懸念データを生成"""
        return {
            "concern_data": {
                "description": "最近、頭痛が頻繁に起こるようになった。特に午後に多い。",
                "severity": 3,  # 整数形式 (1-5スケール)
                "category": ["PHYSICAL"],  # 配列形式、PHYSICAL/MENTALのみ
                "status": "ACTIVE",  # 大文字形式
                "triggers": "低気圧、寝不足",
                "history": "薬は効かない。ストレッチが有効。"
            }
        }
    
    def test_healthconcernmanagement___addconcern(self) -> bool:
        """HealthConcernManagement___AddConcern ツールのテスト"""
        print("📝 健康懸念追加テスト開始...")
        
        test_data = self.get_required_test_data()
        concern_data = test_data["concern_data"]
        
        arguments = {
            "userId": self.test_user_id,
            **concern_data
        }
        
        try:
            response = self.mcp_client.call_tool("HealthConcernManagement___AddConcern", arguments)
            
            if TestUtils.validate_response_success(response):
                print("✅ 健康懸念追加成功")
                
                # concernIdを抽出
                concern_id = TestUtils.extract_id_from_response(response, "concernId")
                if concern_id:
                    self.created_ids.append(("concern", concern_id))
                    print(f"📝 作成ID記録: {concern_id} (HealthConcernManagement___AddConcern)")
                    return True
                else:
                    print("⚠️ concernIdが見つかりません")
                    return False
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 健康懸念追加失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 健康懸念追加エラー: {str(e)}")
            return False
    
    def test_healthconcernmanagement___getconcerns(self) -> bool:
        """HealthConcernManagement___GetConcerns ツールのテスト"""
        print("📝 健康懸念取得テスト開始...")
        
        arguments = {
            "userId": self.test_user_id
        }
        
        try:
            response = self.mcp_client.call_tool("HealthConcernManagement___GetConcerns", arguments)
            
            if TestUtils.validate_response_success(response):
                print("✅ 健康懸念取得成功")
                
                # データ数を確認
                concern_count = TestUtils.extract_data_count_from_response(response, "concerns")
                print(f"📊 取得された懸念数: {concern_count}件")
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 健康懸念取得失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 健康懸念取得エラー: {str(e)}")
            return False
    
    def test_healthconcernmanagement___updateconcern(self) -> bool:
        """HealthConcernManagement___UpdateConcern ツールのテスト"""
        print("📝 健康懸念更新テスト開始...")
        
        arguments = {
            "userId": self.test_user_id,
            "concernId": "dummy-concern-id",
            "description": "頭痛の頻発（改善中）",
            "status": "IMPROVED"
        }
        
        try:
            response = self.mcp_client.call_tool("HealthConcernManagement___UpdateConcern", arguments)
            
            if TestUtils.validate_response_success(response):
                print("✅ 健康懸念更新成功")
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 健康懸念更新失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 健康懸念更新エラー: {str(e)}")
            return False
    
    def test_healthconcernmanagement___deleteconcern(self) -> bool:
        """HealthConcernManagement___DeleteConcern ツールのテスト"""
        print("📝 健康懸念削除テスト開始...")
        
        arguments = {
            "userId": self.test_user_id,
            "concernId": "dummy-concern-id"
        }
        
        try:
            response = self.mcp_client.call_tool("HealthConcernManagement___DeleteConcern", arguments)
            
            if TestUtils.validate_response_success(response):
                print("✅ 健康懸念削除成功")
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 健康懸念削除失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 健康懸念削除エラー: {str(e)}")
            return False