"""
ActivityManagement テストモジュール

ActivityManagement関連のMCPツール（6ツール）をテストします：
- AddActivities: 活動追加
- GetActivities: 活動取得
- UpdateActivity: 活動更新
- UpdateActivities: 複数活動更新
- DeleteActivity: 活動削除
- GetActivitiesInRange: 期間指定活動取得
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
from ..mcp_common.base_manager_test import BaseManagerTest
from ..mcp_common.test_utils import TestUtils


class ActivityManagementTest(BaseManagerTest):
    """ActivityManagement テスト (6ツール)"""
    
    def __init__(self, mcp_client, test_user_id: str):
        super().__init__(mcp_client, test_user_id)
        self.test_activity_ids = []  # 作成された活動IDを保存
        self.test_date = datetime.now().strftime("%Y-%m-%d")
        self.test_date_range = [
            self.test_date,
            (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
            (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        ]
    
    def get_manager_name(self) -> str:
        return "ActivityManagement"
    
    def get_tool_list(self) -> List[str]:
        return [
            "ActivityManagement___AddActivities",
            "ActivityManagement___GetActivities",
            "ActivityManagement___UpdateActivity",
            "ActivityManagement___UpdateActivities",
            "ActivityManagement___DeleteActivity",
            "ActivityManagement___GetActivitiesInRange"
        ]
    
    def get_cleanup_tools(self) -> Dict[str, str]:
        return {
            "ActivityManagement___AddActivities": "ActivityManagement___DeleteActivity"
        }
    
    def get_required_test_data(self) -> Dict[str, Any]:
        """テストに必要な活動データを定義"""
        return {
            "initial_activities": [
                {
                    "time": "08:00",
                    "activityType": "exercise",
                    "description": "朝のジョギング",
                    "items": ["ジョギング30分", "ストレッチ10分"]
                },
                {
                    "time": "12:00",
                    "activityType": "meal",
                    "description": "昼食",
                    "items": ["サラダ", "チキン", "玄米"]
                }
            ],
            "additional_activities": [
                {
                    "time": "15:00",
                    "activityType": "work",
                    "description": "仕事",
                    "items": ["会議参加", "資料作成"]
                }
            ],
            "updated_activity": {
                "time": "08:00",
                "activityType": "exercise",
                "description": "朝のジョギング（更新版）",
                "items": ["ジョギング45分", "ストレッチ15分", "筋トレ10分"]
            }
        }
    
    def test_activitymanagement___addactivities(self) -> bool:
        """AddActivities ツールテスト"""
        print("📝 活動追加テスト開始...")
        
        test_data = self.get_required_test_data()
        activities = test_data["initial_activities"]
        
        arguments = {
            "operationType": "append",
            "userId": self.test_user_id,
            "date": self.test_date,
            "activities": activities
        }
        
        try:
            response = self.mcp_client.call_tool("ActivityManagement___AddActivities", arguments)
            
            if TestUtils.validate_response_success(response):
                print(f"✅ 活動追加成功: {len(activities)}個の活動")
                
                # addedActivityIdsを抽出して保存
                activity_ids = TestUtils.extract_ids_from_response(response, "addedActivityIds")
                if activity_ids:
                    self.test_activity_ids.extend(activity_ids)
                    for activity_id in activity_ids:
                        self.record_created_id(activity_id, "ActivityManagement___AddActivities")
                    print(f"📝 活動ID記録: {len(activity_ids)}個")
                else:
                    print("⚠️ addedActivityIdsが見つかりません")
                
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 活動追加失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 活動追加例外: {str(e)}")
            return False
    
    def test_activitymanagement___getactivities(self) -> bool:
        """GetActivities ツールテスト"""
        print("📋 活動取得テスト開始...")
        
        arguments = {
            "userId": self.test_user_id,
            "date": self.test_date
        }
        
        try:
            response = self.mcp_client.call_tool("ActivityManagement___GetActivities", arguments)
            
            if TestUtils.validate_response_success(response):
                print(f"✅ 活動取得成功")
                
                # activitiesの数を確認
                activity_count = TestUtils.extract_data_count_from_response(response, "activities")
                print(f"📊 取得された活動数: {activity_count}件")
                
                # activityIdが未取得の場合、ここで取得
                if not self.test_activity_ids:
                    # JSON-RPC 2.0レスポンスから活動データを抽出
                    data = response.get("data", {})
                    if 'result' in data and 'content' in data['result']:
                        content = data['result']['content']
                        if isinstance(content, list) and len(content) > 0:
                            text_content = content[0].get('text', '')
                            if text_content:
                                try:
                                    import json
                                    parsed_content = json.loads(text_content)
                                    activities = parsed_content.get("activities", [])
                                    
                                    for activity in activities:
                                        if isinstance(activity, dict) and "activityId" in activity:
                                            activity_id = activity["activityId"]
                                            if activity_id not in self.test_activity_ids:
                                                self.test_activity_ids.append(activity_id)
                                                self.record_created_id(activity_id, "ActivityManagement___AddActivities")
                                    
                                    if self.test_activity_ids:
                                        print(f"📝 活動ID取得（GetActivitiesから）: {len(self.test_activity_ids)}個")
                                        
                                except json.JSONDecodeError:
                                    print("⚠️ JSON解析エラー")
                
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 活動取得失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 活動取得例外: {str(e)}")
            return False
    
    def test_activitymanagement___updateactivity(self) -> bool:
        """UpdateActivity ツールテスト"""
        print("📝 活動更新テスト開始...")
        
        if not self.test_activity_ids:
            print("⚠️ 活動更新スキップ: activityIdが取得できませんでした")
            return False
        
        test_data = self.get_required_test_data()
        updated_activity = test_data["updated_activity"]
        
        # 最初の活動を更新
        activity_id = self.test_activity_ids[0]
        
        arguments = {
            "userId": self.test_user_id,
            "date": self.test_date,  # 必須フィールド
            "activityId": activity_id,
            **updated_activity
        }
        
        try:
            response = self.mcp_client.call_tool("ActivityManagement___UpdateActivity", arguments)
            
            if TestUtils.validate_response_success(response):
                print(f"✅ 活動更新成功: {activity_id}")
                
                # レスポンスデータの検証
                data = response.get("data", {})
                if isinstance(data, dict):
                    if data.get("description") == updated_activity["description"]:
                        print(f"✅ 説明更新確認: {data.get('description')}")
                    
                    items = data.get("items", [])
                    expected_items = updated_activity["items"]
                    if len(items) == len(expected_items):
                        print(f"✅ アイテム数更新確認: {len(items)}個")
                
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 活動更新失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 活動更新例外: {str(e)}")
            return False
    
    def test_activitymanagement___updateactivities(self) -> bool:
        """UpdateActivities ツールテスト"""
        print("📝 複数活動更新テスト開始...")
        
        test_data = self.get_required_test_data()
        additional_activities = test_data["additional_activities"]
        
        arguments = {
            "operationType": "append",
            "userId": self.test_user_id,
            "date": self.test_date,
            "activities": additional_activities
        }
        
        try:
            response = self.mcp_client.call_tool("ActivityManagement___UpdateActivities", arguments)
            
            if TestUtils.validate_response_success(response):
                print(f"✅ 複数活動更新成功: {len(additional_activities)}個の活動を追加")
                
                # 新しく追加されたactivityIdを記録
                activity_ids = TestUtils.extract_ids_from_response(response, "activityIds")
                if activity_ids:
                    new_ids = [aid for aid in activity_ids if aid not in self.test_activity_ids]
                    self.test_activity_ids.extend(new_ids)
                    for activity_id in new_ids:
                        self.record_created_id(activity_id, "ActivityManagement___AddActivities")
                    print(f"📝 新規活動ID記録: {len(new_ids)}個")
                else:
                    print("⚠️ activityIdsが見つかりません")
                
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 複数活動更新失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 複数活動更新例外: {str(e)}")
            return False
    
    def test_activitymanagement___getactivitiesinrange(self) -> bool:
        """GetActivitiesInRange ツールテスト"""
        print("📅 期間指定活動取得テスト開始...")
        
        start_date = self.test_date
        end_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        
        arguments = {
            "userId": self.test_user_id,
            "startDate": start_date,
            "endDate": end_date
        }
        
        try:
            response = self.mcp_client.call_tool("ActivityManagement___GetActivitiesInRange", arguments)
            
            if TestUtils.validate_response_success(response):
                print(f"✅ 期間指定活動取得成功: {start_date} - {end_date}")
                
                # レスポンスデータの検証
                data = response.get("data", {})
                if isinstance(data, dict):
                    activities_by_date = data.get("activitiesByDate", {})
                    
                    if isinstance(activities_by_date, dict):
                        print(f"📊 取得された日付数: {len(activities_by_date)}")
                        
                        # 今日の活動が含まれているか確認
                        today_activities = activities_by_date.get(self.test_date, [])
                        if isinstance(today_activities, list) and len(today_activities) > 0:
                            print(f"✅ 今日の活動確認: {len(today_activities)}個")
                        
                        return True
                    else:
                        print(f"⚠️ activitiesByDateフィールドが辞書形式ではありません: {type(activities_by_date)}")
                        return False
                else:
                    print(f"❌ レスポンスデータが辞書形式ではありません: {type(data)}")
                    return False
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 期間指定活動取得失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 期間指定活動取得例外: {str(e)}")
            return False
    
    def test_activitymanagement___deleteactivity(self) -> bool:
        """DeleteActivity ツールテスト"""
        print("🗑️ 活動削除テスト開始...")
        
        if not self.test_activity_ids:
            print("⚠️ 活動削除スキップ: activityIdが取得できませんでした")
            return False
        
        # 最後の活動を削除（テスト用）
        activity_id = self.test_activity_ids[-1]
        
        arguments = {
            "userId": self.test_user_id,
            "date": self.test_date,  # 必須フィールド
            "activityId": activity_id
        }
        
        try:
            response = self.mcp_client.call_tool("ActivityManagement___DeleteActivity", arguments)
            
            if TestUtils.validate_response_success(response):
                print(f"✅ 活動削除成功: {activity_id}")
                
                # 削除されたIDをリストから除去
                if activity_id in self.test_activity_ids:
                    self.test_activity_ids.remove(activity_id)
                
                # 削除後の確認（GetActivitiesで確認）
                get_response = self.mcp_client.call_tool("ActivityManagement___GetActivities", {
                    "userId": self.test_user_id,
                    "date": self.test_date
                })
                
                if TestUtils.validate_response_success(get_response):
                    data = get_response.get("data", {})
                    activities = data.get("activities", [])
                    
                    # 削除された活動が含まれていないことを確認
                    deleted_activity_exists = any(
                        activity.get("activityId") == activity_id 
                        for activity in activities 
                        if isinstance(activity, dict)
                    )
                    
                    if not deleted_activity_exists:
                        print(f"✅ 削除確認: 活動が正常に削除されました")
                    else:
                        print(f"⚠️ 削除未確認: 活動がまだ存在しています")
                
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 活動削除失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 活動削除例外: {str(e)}")
            return False
    
    def _get_created_ids_for_tool(self, tool_name: str) -> List[Dict[str, Any]]:
        """ActivityManagementで作成されたIDリストを取得"""
        if tool_name == "ActivityManagement___AddActivities" and self.test_activity_ids:
            return [{"id": activity_id, "tool": tool_name} for activity_id in self.test_activity_ids]
        return []
    
    def _delete_single_item(self, cleanup_tool: str, id_info: Dict[str, Any]):
        """活動の削除"""
        if cleanup_tool == "ActivityManagement___DeleteActivity":
            delete_params = {
                "userId": self.test_user_id,
                "activityId": id_info["id"]
            }
            
            try:
                response = self.mcp_client.call_tool(cleanup_tool, delete_params)
                
                if TestUtils.validate_response_success(response):
                    print(f"✅ クリーンアップ: 活動 {id_info['id']} を削除")
                else:
                    print(f"⚠️ クリーンアップ失敗: {response.get('message', 'Unknown error')}")
                    
            except Exception as e:
                print(f"⚠️ クリーンアップ例外: {str(e)}")
    
    def custom_setup(self):
        """ActivityManagement固有のセットアップ"""
        print(f"📝 活動テスト用ユーザーID: {self.test_user_id}")
        print(f"📅 テスト日付: {self.test_date}")
        self.test_activity_ids = []
    
    def custom_teardown(self):
        """ActivityManagement固有のクリーンアップ"""
        if self.test_activity_ids:
            print(f"📝 作成された活動ID数: {len(self.test_activity_ids)}")
        else:
            print("ℹ️ 作成された活動IDはありません")