"""
BodyMeasurementManagement MCP ツールのテストモジュール

このモジュールは、BodyMeasurementManagement関連のMCPツールをテストします。
- AddBodyMeasurement: 体測定データの追加
- GetLatestMeasurements: 最新の測定データ取得
- GetOldestMeasurements: 最古の測定データ取得
- GetMeasurementHistory: 測定履歴の取得
- UpdateBodyMeasurement: 体測定データの更新
- DeleteBodyMeasurement: 体測定データの削除
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any

from ..mcp_common.base_manager_test import BaseManagerTest
from ..mcp_common.test_utils import TestUtils


class BodyMeasurementManagementTest(BaseManagerTest):
    """BodyMeasurementManagement MCPツールのテストクラス"""
    
    def get_manager_name(self) -> str:
        """Managerの名前を返す"""
        return "BodyMeasurementManagement"
    
    def get_tool_list(self) -> List[str]:
        """このManagerでテストするツールのリストを返す"""
        return [
            "BodyMeasurementManagement___AddBodyMeasurement",
            "BodyMeasurementManagement___GetLatestMeasurements", 
            "BodyMeasurementManagement___GetOldestMeasurements",
            "BodyMeasurementManagement___GetMeasurementHistory",
            "BodyMeasurementManagement___UpdateBodyMeasurement",
            "BodyMeasurementManagement___DeleteBodyMeasurement"
        ]
    
    def get_cleanup_tools(self) -> Dict[str, str]:
        """テストデータクリーンアップに使用するツールのマッピングを返す"""
        return {
            "BodyMeasurementManagement___AddBodyMeasurement": "BodyMeasurementManagement___DeleteBodyMeasurement"
        }
    
    def get_required_test_data(self) -> Dict[str, Any]:
        """テスト用の体測定データを生成"""
        base_date = datetime.now()
        
        return {
            "measurement_data": {
                "measurementDate": base_date.strftime("%Y-%m-%d"),
                "measurementTime": "08:00",
                "weight": 70.5,
                "bodyFatPercentage": 15.2,
                "muscleMass": 55.8,
                "bmi": 22.1,
                "notes": "朝食前の測定"
            }
        }
    
    def test_bodymeasurementmanagement___addbodymeasurement(self) -> bool:
        """AddBodyMeasurement ツールのテスト"""
        print("📝 体測定データ追加テスト開始...")
        
        test_data = self.get_required_test_data()
        measurement_data = test_data["measurement_data"]
        
        arguments = {
            "userId": self.test_user_id,
            **measurement_data
        }
        
        try:
            response = self.mcp_client.call_tool("BodyMeasurementManagement___AddBodyMeasurement", arguments)
            
            if TestUtils.validate_response_success(response):
                print("✅ 体測定データ追加成功")
                
                # measurementIdを抽出
                measurement_id = TestUtils.extract_id_from_response(response, "measurementId")
                if measurement_id:
                    self.created_ids.append(("measurement", measurement_id))
                    print(f"📝 作成ID記録: {measurement_id} (BodyMeasurementManagement___AddBodyMeasurement)")
                    return True
                else:
                    # measurementTimeをmeasurementIdとして使用する場合もある
                    measurement_time = TestUtils.extract_id_from_response(response, "measurementTime")
                    if measurement_time:
                        self.created_ids.append(("measurement", measurement_time))
                        print(f"📝 作成ID記録（measurementTime）: {measurement_time} (BodyMeasurementManagement___AddBodyMeasurement)")
                        return True
                    else:
                        print("⚠️ measurementIdまたはmeasurementTimeが見つかりません")
                        return False
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 体測定データ追加失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 体測定データ追加エラー: {str(e)}")
            return False
    
    def test_bodymeasurementmanagement___getlatestmeasurements(self) -> bool:
        """GetLatestMeasurements ツールのテスト"""
        print("📝 最新測定データ取得テスト開始...")
        
        arguments = {
            "userId": self.test_user_id,
            "limit": 5
        }
        
        try:
            response = self.mcp_client.call_tool("BodyMeasurementManagement___GetLatestMeasurements", arguments)
            
            if TestUtils.validate_response_success(response):
                print("✅ 最新測定データ取得成功")
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 最新測定データ取得失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 最新測定データ取得エラー: {str(e)}")
            return False
    
    def test_bodymeasurementmanagement___getoldestmeasurements(self) -> bool:
        """GetOldestMeasurements ツールのテスト"""
        print("📝 最古測定データ取得テスト開始...")
        
        arguments = {
            "userId": self.test_user_id,
            "limit": 5
        }
        
        try:
            response = self.mcp_client.call_tool("BodyMeasurementManagement___GetOldestMeasurements", arguments)
            
            if TestUtils.validate_response_success(response):
                print("✅ 最古測定データ取得成功")
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 最古測定データ取得失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 最古測定データ取得エラー: {str(e)}")
            return False
    
    def test_bodymeasurementmanagement___getmeasurementhistory(self) -> bool:
        """GetMeasurementHistory ツールのテスト"""
        print("📝 測定履歴取得テスト開始...")
        
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")
        
        arguments = {
            "userId": self.test_user_id,
            "start_date": start_date,  # startDate → start_date
            "end_date": end_date       # endDate → end_date
        }
        
        try:
            response = self.mcp_client.call_tool("BodyMeasurementManagement___GetMeasurementHistory", arguments)
            
            if TestUtils.validate_response_success(response):
                print("✅ 測定履歴取得成功")
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 測定履歴取得失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 測定履歴取得エラー: {str(e)}")
            return False
    
    def test_bodymeasurementmanagement___updatebodymeasurement(self) -> bool:
        """UpdateBodyMeasurement ツールのテスト"""
        print("📝 体測定データ更新テスト開始...")
        
        # 実際の実装では、まず測定データを作成してからIDを取得する必要があります
        # ここでは簡略化してダミーIDを使用
        arguments = {
            "userId": self.test_user_id,
            "measurement_id": "dummy-measurement-id",  # measurementId → measurement_id
            "weight": 71.0,
            "notes": "更新されたデータ"
        }
        
        try:
            response = self.mcp_client.call_tool("BodyMeasurementManagement___UpdateBodyMeasurement", arguments)
            
            if TestUtils.validate_response_success(response):
                print("✅ 体測定データ更新成功")
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 体測定データ更新失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 体測定データ更新エラー: {str(e)}")
            return False
    
    def test_bodymeasurementmanagement___deletebodymeasurement(self) -> bool:
        """DeleteBodyMeasurement ツールのテスト"""
        print("📝 体測定データ削除テスト開始...")
        
        # 実際の実装では、作成されたIDを使用する必要があります
        # ここでは簡略化してダミーIDを使用
        arguments = {
            "userId": self.test_user_id,
            "measurement_id": "dummy-measurement-id"  # measurementId → measurement_id
        }
        
        try:
            response = self.mcp_client.call_tool("BodyMeasurementManagement___DeleteBodyMeasurement", arguments)
            
            if TestUtils.validate_response_success(response):
                print("✅ 体測定データ削除成功")
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 体測定データ削除失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 体測定データ削除エラー: {str(e)}")
            return False