"""
HealthGoalManagement テストモジュール

HealthGoalManagement関連のMCPツール（4ツール）をテストします：
- AddGoal: 健康目標追加
- GetGoals: 健康目標取得
- UpdateGoal: 健康目標更新
- DeleteGoal: 健康目標削除
"""

import json
from typing import List, Dict, Any
from ..mcp_common.base_manager_test import BaseManagerTest
from ..mcp_common.test_utils import TestUtils


class HealthGoalManagementTest(BaseManagerTest):
    """HealthGoalManagement テスト (4ツール)"""
    
    def __init__(self, mcp_client, test_user_id: str):
        super().__init__(mcp_client, test_user_id)
        self.test_goal_id = None  # 作成された目標IDを保存
    
    def get_manager_name(self) -> str:
        return "HealthGoalManagement"
    
    def get_tool_list(self) -> List[str]:
        return [
            "HealthGoalManagement___AddGoal",
            "HealthGoalManagement___GetGoals",
            "HealthGoalManagement___UpdateGoal",
            "HealthGoalManagement___DeleteGoal"
        ]
    
    def get_cleanup_tools(self) -> Dict[str, str]:
        return {
            "HealthGoalManagement___AddGoal": "HealthGoalManagement___DeleteGoal"
        }
    
    def get_required_test_data(self) -> Dict[str, Any]:
        """テストに必要な健康目標データを定義"""
        return {
            "initial_goal": {
                "goalType": "fitness",
                "title": "アスリート体型になる",
                "description": "体脂肪率を15%以下にして筋肉量を増やす",
                "targetValue": "体脂肪率15%",
                "targetDate": "2025-12-31",
                "priority": 3
            },
            "updated_goal": {
                "title": "更新されたアスリート体型目標",
                "description": "体脂肪率を12%以下にして筋肉量を大幅に増やす",
                "targetValue": "体脂肪率12%",
                "priority": 4,
                "status": "active"
            }
        }
    
    def test_healthgoalmanagement___addgoal(self) -> bool:
        """AddGoal ツールテスト"""
        print("🎯 健康目標追加テスト開始...")
        
        test_data = self.get_required_test_data()
        goal_data = test_data["initial_goal"]
        
        arguments = {
            "userId": self.test_user_id,
            **goal_data
        }
        
        try:
            response = self.mcp_client.call_tool("HealthGoalManagement___AddGoal", arguments)
            
            if TestUtils.validate_response_success(response):
                print(f"✅ 健康目標追加成功")
                
                # goalIdを抽出して保存
                goal_id = TestUtils.extract_id_from_response(response, "goalId")
                if goal_id:
                    self.test_goal_id = goal_id
                    self.record_created_id(goal_id, "HealthGoalManagement___AddGoal")
                    print(f"📝 目標ID記録: {goal_id}")
                else:
                    # レスポンスから手動でgoalIdを抽出
                    data = response.get("data", {})
                    if isinstance(data, dict):
                        # 複数の可能性を確認
                        possible_ids = [
                            data.get("goalId"),
                            data.get("id"),
                            data.get("goal_id"),
                            data.get("Goal", {}).get("goalId") if isinstance(data.get("Goal"), dict) else None
                        ]
                        
                        for possible_id in possible_ids:
                            if possible_id:
                                self.test_goal_id = possible_id
                                self.record_created_id(self.test_goal_id, "HealthGoalManagement___AddGoal")
                                print(f"📝 目標ID記録（手動抽出）: {self.test_goal_id}")
                                break
                        
                        if not self.test_goal_id:
                            print(f"⚠️ goalIdが見つかりません。レスポンス: {data}")
                            # デバッグ用にレスポンス全体を表示
                            print(f"🔍 完全レスポンス: {response}")
                
                # レスポンスデータの検証
                data = response.get("data", {})
                if isinstance(data, dict):
                    # 必須フィールドの確認
                    required_fields = ["goalId", "title", "goalType"]
                    validation = TestUtils.validate_required_fields(data, required_fields)
                    
                    if validation["valid"]:
                        print(f"✅ 必須フィールド確認: {validation['present_fields']}")
                    else:
                        print(f"⚠️ 必須フィールド不足: {validation['missing_fields']}")
                
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 健康目標追加失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 健康目標追加例外: {str(e)}")
            return False
    
    def test_healthgoalmanagement___getgoals(self) -> bool:
        """GetGoals ツールテスト"""
        print("📋 健康目標取得テスト開始...")
        
        arguments = {
            "userId": self.test_user_id
        }
        
        try:
            response = self.mcp_client.call_tool("HealthGoalManagement___GetGoals", arguments)
            
            if TestUtils.validate_response_success(response):
                print(f"✅ 健康目標取得成功")
                
                # レスポンスデータの検証
                data = response.get("data", {})
                if isinstance(data, dict):
                    goals = data.get("goals", [])
                    
                    if isinstance(goals, list):
                        print(f"📊 取得された目標数: {len(goals)}")
                        
                        # 作成した目標が含まれているか確認
                        if len(goals) > 0:
                            first_goal = goals[0]
                            
                            # goalIdが未取得の場合、ここで取得
                            if not self.test_goal_id and "goalId" in first_goal:
                                self.test_goal_id = first_goal["goalId"]
                                self.record_created_id(self.test_goal_id, "HealthGoalManagement___AddGoal")
                                print(f"📝 目標ID取得（GetGoalsから）: {self.test_goal_id}")
                            
                            # 目標データの詳細確認
                            test_data = self.get_required_test_data()
                            initial_goal = test_data["initial_goal"]
                            
                            if first_goal.get("title") == initial_goal["title"]:
                                print(f"✅ 目標タイトル確認: {first_goal.get('title')}")
                            
                            if first_goal.get("goalType") == initial_goal["goalType"]:
                                print(f"✅ 目標タイプ確認: {first_goal.get('goalType')}")
                            
                            if first_goal.get("priority") == initial_goal["priority"]:
                                print(f"✅ 優先度確認: {first_goal.get('priority')}")
                        
                        return True
                    else:
                        print(f"⚠️ goalsフィールドがリスト形式ではありません: {type(goals)}")
                        return False
                else:
                    print(f"❌ レスポンスデータが辞書形式ではありません: {type(data)}")
                    return False
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 健康目標取得失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 健康目標取得例外: {str(e)}")
            return False
    
    def test_healthgoalmanagement___updategoal(self) -> bool:
        """UpdateGoal ツールテスト"""
        print("📝 健康目標更新テスト開始...")
        
        if not self.test_goal_id:
            print("⚠️ 健康目標更新スキップ: goalIdが取得できませんでした")
            return False
        
        test_data = self.get_required_test_data()
        updated_goal = test_data["updated_goal"]
        
        arguments = {
            "userId": self.test_user_id,
            "goalId": self.test_goal_id,
            **updated_goal
        }
        
        try:
            response = self.mcp_client.call_tool("HealthGoalManagement___UpdateGoal", arguments)
            
            if TestUtils.validate_response_success(response):
                print(f"✅ 健康目標更新成功: {self.test_goal_id}")
                
                # レスポンスデータの検証
                data = response.get("data", {})
                if isinstance(data, dict):
                    # 更新されたフィールドの確認
                    if data.get("title") == updated_goal["title"]:
                        print(f"✅ タイトル更新確認: {data.get('title')}")
                    
                    if data.get("description") == updated_goal["description"]:
                        print(f"✅ 説明更新確認: {data.get('description')}")
                    
                    if data.get("priority") == updated_goal["priority"]:
                        print(f"✅ 優先度更新確認: {data.get('priority')}")
                    
                    if data.get("status") == updated_goal["status"]:
                        print(f"✅ ステータス更新確認: {data.get('status')}")
                
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 健康目標更新失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 健康目標更新例外: {str(e)}")
            return False
    
    def test_healthgoalmanagement___deletegoal(self) -> bool:
        """DeleteGoal ツールテスト"""
        print("🗑️ 健康目標削除テスト開始...")
        
        if not self.test_goal_id:
            print("⚠️ 健康目標削除スキップ: goalIdが取得できませんでした")
            return False
        
        arguments = {
            "userId": self.test_user_id,
            "goalId": self.test_goal_id
        }
        
        try:
            response = self.mcp_client.call_tool("HealthGoalManagement___DeleteGoal", arguments)
            
            if TestUtils.validate_response_success(response):
                print(f"✅ 健康目標削除成功: {self.test_goal_id}")
                
                # 削除後の確認（GetGoalsで確認）
                get_response = self.mcp_client.call_tool("HealthGoalManagement___GetGoals", {
                    "userId": self.test_user_id
                })
                
                if TestUtils.validate_response_success(get_response):
                    data = get_response.get("data", {})
                    goals = data.get("goals", [])
                    
                    # 削除された目標が含まれていないことを確認
                    deleted_goal_exists = any(
                        goal.get("goalId") == self.test_goal_id 
                        for goal in goals 
                        if isinstance(goal, dict)
                    )
                    
                    if not deleted_goal_exists:
                        print(f"✅ 削除確認: 目標が正常に削除されました")
                    else:
                        print(f"⚠️ 削除未確認: 目標がまだ存在しています")
                
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 健康目標削除失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 健康目標削除例外: {str(e)}")
            return False
    
    def _get_created_ids_for_tool(self, tool_name: str) -> List[Dict[str, Any]]:
        """HealthGoalManagementで作成されたIDリストを取得"""
        if tool_name == "HealthGoalManagement___AddGoal" and self.test_goal_id:
            return [{"id": self.test_goal_id, "tool": tool_name}]
        return []
    
    def _delete_single_item(self, cleanup_tool: str, id_info: Dict[str, Any]):
        """健康目標の削除"""
        if cleanup_tool == "HealthGoalManagement___DeleteGoal":
            delete_params = {
                "userId": self.test_user_id,
                "goalId": id_info["id"]
            }
            
            try:
                response = self.mcp_client.call_tool(cleanup_tool, delete_params)
                
                if TestUtils.validate_response_success(response):
                    print(f"✅ クリーンアップ: 目標 {id_info['id']} を削除")
                else:
                    print(f"⚠️ クリーンアップ失敗: {response.get('message', 'Unknown error')}")
                    
            except Exception as e:
                print(f"⚠️ クリーンアップ例外: {str(e)}")
    
    def custom_setup(self):
        """HealthGoalManagement固有のセットアップ"""
        print(f"🎯 健康目標テスト用ユーザーID: {self.test_user_id}")
        self.test_goal_id = None
    
    def custom_teardown(self):
        """HealthGoalManagement固有のクリーンアップ"""
        if self.test_goal_id:
            print(f"📝 作成された目標ID: {self.test_goal_id}")
        else:
            print("ℹ️ 作成された目標IDはありません")
    
    def _get_created_ids_for_tool(self, tool_name: str) -> List[Dict[str, Any]]:
        """HealthGoalManagementで作成されたIDリストを取得"""
        if tool_name == "HealthGoalManagement___AddGoal" and self.test_goal_id:
            return [{"id": self.test_goal_id, "tool": tool_name}]
        return []