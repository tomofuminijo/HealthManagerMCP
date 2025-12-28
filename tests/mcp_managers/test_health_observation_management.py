"""
HealthObservationManagement MCP ツールのテストモジュール

このモジュールは、HealthObservationManagement関連のMCPツールをテストします。
- AddObservation: 健康観測の追加
- GetObservation: 特定の健康観測の取得
- GetObservations: 健康観測の一覧取得
- UpdateObservation: 健康観測の更新
- CompleteObservation: 健康観測の完了
- CancelObservation: 健康観測のキャンセル
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any

from ..mcp_common.base_manager_test import BaseManagerTest
from ..mcp_common.test_utils import TestUtils


class HealthObservationManagementTest(BaseManagerTest):
    """HealthObservationManagement MCPツールのテストクラス"""
    
    def get_manager_name(self) -> str:
        """Managerの名前を返す"""
        return "HealthObservationManagement"
    
    def get_tool_list(self) -> List[str]:
        """このManagerでテストするツールのリストを返す"""
        return [
            "HealthObservationManagement___AddObservation",
            "HealthObservationManagement___GetObservation",
            "HealthObservationManagement___GetObservationsInRange",  # 正しいツール名
            "HealthObservationManagement___UpdateObservation",
            "HealthObservationManagement___CompleteObservation",
            "HealthObservationManagement___CancelObservation"
        ]
    
    def get_cleanup_tools(self) -> Dict[str, str]:
        """テストデータクリーンアップに使用するツールのマッピングを返す"""
        # CompleteObservation と CancelObservation は削除ではなく状態変更なので、
        # 実際の削除ツールがあれば使用する。ここでは空の辞書を返す。
        return {}
    
    def get_required_test_data(self) -> Dict[str, Any]:
        """テスト用の健康観測データを生成"""
        base_date = datetime.now()
        
        return {
            "observation_data": {
                "title": "血圧測定",
                "description": "毎朝の血圧測定を記録",
                "priority": 3,  # 必須フィールド (1-5)
                "startDatetime": base_date.isoformat() + "Z",  # ISO 8601形式
                "targetDatetime": (base_date + timedelta(days=30)).isoformat() + "Z",  # ISO 8601形式
                "frequency": "P1D",  # ISO 8601 Duration形式（1日）
                "checkItems": ["血圧測定", "脈拍測定", "体調記録"]  # 必須フィールド
            }
        }
    
    def test_healthobservationmanagement___addobservation(self) -> bool:
        """HealthObservationManagement___AddObservation ツールのテスト"""
        print("📝 健康観測追加テスト開始...")
        
        test_data = self.get_required_test_data()
        observation_data = test_data["observation_data"]
        
        arguments = {
            "userId": self.test_user_id,
            **observation_data
        }
        
        try:
            response = self.mcp_client.call_tool("HealthObservationManagement___AddObservation", arguments)
            
            if TestUtils.validate_response_success(response):
                print("✅ 健康観測追加成功")
                
                # observationIdを抽出
                observation_id = TestUtils.extract_id_from_response(response, "observationId")
                if observation_id:
                    self.created_ids.append(("observation", observation_id))
                    print(f"📝 作成ID記録: {observation_id} (HealthObservationManagement___AddObservation)")
                    return True
                else:
                    print("⚠️ observationIdが見つかりません")
                    return False
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 健康観測追加失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 健康観測追加エラー: {str(e)}")
            return False
    
    def test_healthobservationmanagement___getobservation(self) -> bool:
        """HealthObservationManagement___GetObservation ツールのテスト"""
        print("📝 健康観測取得テスト開始...")
        
        arguments = {
            "userId": self.test_user_id,
            "observationId": "dummy-observation-id"
        }
        
        try:
            response = self.mcp_client.call_tool("HealthObservationManagement___GetObservation", arguments)
            
            if TestUtils.validate_response_success(response):
                print("✅ 健康観測取得成功")
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 健康観測取得失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 健康観測取得エラー: {str(e)}")
            return False
    
    def test_healthobservationmanagement___getobservationsinrange(self) -> bool:
        """HealthObservationManagement___GetObservationsInRange ツールのテスト"""
        print("📝 健康観測期間取得テスト開始...")
        
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")
        
        arguments = {
            "userId": self.test_user_id,
            "startDate": start_date,
            "endDate": end_date
        }
        
        try:
            response = self.mcp_client.call_tool("HealthObservationManagement___GetObservationsInRange", arguments)
            
            if TestUtils.validate_response_success(response):
                print("✅ 健康観測期間取得成功")
                
                # データ数を確認
                observation_count = TestUtils.extract_data_count_from_response(response, "observations")
                print(f"📊 取得された観測数: {observation_count}件")
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 健康観測期間取得失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 健康観測期間取得エラー: {str(e)}")
            return False
    
    def test_healthobservationmanagement___updateobservation(self) -> bool:
        """HealthObservationManagement___UpdateObservation ツールのテスト"""
        print("📝 健康観測更新テスト開始...")
        
        arguments = {
            "userId": self.test_user_id,
            "observationId": "dummy-observation-id",
            "title": "血圧測定（改良版）",
            "priority": 4
        }
        
        try:
            response = self.mcp_client.call_tool("HealthObservationManagement___UpdateObservation", arguments)
            
            if TestUtils.validate_response_success(response):
                print("✅ 健康観測更新成功")
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 健康観測更新失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 健康観測更新エラー: {str(e)}")
            return False
    
    def test_healthobservationmanagement___completeobservation(self) -> bool:
        """HealthObservationManagement___CompleteObservation ツールのテスト"""
        print("📝 健康観測完了テスト開始...")
        
        arguments = {
            "userId": self.test_user_id,
            "observationId": "dummy-observation-id",
            "conclusion": "目標達成により観測完了"
        }
        
        try:
            response = self.mcp_client.call_tool("HealthObservationManagement___CompleteObservation", arguments)
            
            if TestUtils.validate_response_success(response):
                print("✅ 健康観測完了成功")
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 健康観測完了失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 健康観測完了エラー: {str(e)}")
            return False
    
    def test_healthobservationmanagement___cancelobservation(self) -> bool:
        """HealthObservationManagement___CancelObservation ツールのテスト"""
        print("📝 健康観測キャンセルテスト開始...")
        
        arguments = {
            "userId": self.test_user_id,
            "observationId": "dummy-observation-id",
            "conclusion": "測定機器の不具合により中止"
        }
        
        try:
            response = self.mcp_client.call_tool("HealthObservationManagement___CancelObservation", arguments)
            
            if TestUtils.validate_response_success(response):
                print("✅ 健康観測キャンセル成功")
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 健康観測キャンセル失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 健康観測キャンセルエラー: {str(e)}")
            return False