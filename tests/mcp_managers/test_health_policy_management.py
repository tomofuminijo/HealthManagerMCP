"""
HealthPolicyManagement テストモジュール

HealthPolicyManagement関連のMCPツール（4ツール）をテストします：
- AddPolicy: 健康ポリシー追加
- GetPolicies: 健康ポリシー取得
- UpdatePolicy: 健康ポリシー更新
- DeletePolicy: 健康ポリシー削除
"""

import json
from typing import List, Dict, Any
from ..mcp_common.base_manager_test import BaseManagerTest
from ..mcp_common.test_utils import TestUtils


class HealthPolicyManagementTest(BaseManagerTest):
    """HealthPolicyManagement テスト (4ツール)"""
    
    def __init__(self, mcp_client, test_user_id: str):
        super().__init__(mcp_client, test_user_id)
        self.test_policy_id = None  # 作成されたポリシーIDを保存
    
    def get_manager_name(self) -> str:
        return "HealthPolicyManagement"
    
    def get_tool_list(self) -> List[str]:
        return [
            "HealthPolicyManagement___AddPolicy",
            "HealthPolicyManagement___GetPolicies",
            "HealthPolicyManagement___UpdatePolicy",
            "HealthPolicyManagement___DeletePolicy"
        ]
    
    def get_cleanup_tools(self) -> Dict[str, str]:
        return {
            "HealthPolicyManagement___AddPolicy": "HealthPolicyManagement___DeletePolicy"
        }
    
    def get_required_test_data(self) -> Dict[str, Any]:
        """テストに必要な健康ポリシーデータを定義"""
        return {
            "initial_policy": {
                "policyType": "diet",
                "description": "低糖質ダイエット",
                "parameters": {
                    "maxCarbs": "50g/day",
                    "mealTiming": ["8:00", "12:00", "18:00"]
                }
            },
            "updated_policy": {
                "description": "更新された低糖質ダイエット",
                "parameters": {
                    "maxCarbs": "40g/day",
                    "mealTiming": ["7:30", "12:30", "18:30"],
                    "cheatDay": "Sunday"
                }
            }
        }
    
    def test_healthpolicymanagement___addpolicy(self) -> bool:
        """AddPolicy ツールテスト"""
        print("📋 健康ポリシー追加テスト開始...")
        
        test_data = self.get_required_test_data()
        policy_data = test_data["initial_policy"]
        
        arguments = {
            "userId": self.test_user_id,
            **policy_data
        }
        
        try:
            response = self.mcp_client.call_tool("HealthPolicyManagement___AddPolicy", arguments)
            
            if TestUtils.validate_response_success(response):
                print(f"✅ 健康ポリシー追加成功")
                
                # policyIdを抽出して保存
                policy_id = TestUtils.extract_id_from_response(response, "policyId")
                if policy_id:
                    self.test_policy_id = policy_id
                    self.record_created_id(policy_id, "HealthPolicyManagement___AddPolicy")
                    print(f"📝 ポリシーID記録: {policy_id}")
                else:
                    # レスポンスから手動でpolicyIdを抽出
                    data = response.get("data", {})
                    if isinstance(data, dict):
                        # 複数の可能性を確認
                        possible_ids = [
                            data.get("policyId"),
                            data.get("id"),
                            data.get("policy_id"),
                            data.get("Policy", {}).get("policyId") if isinstance(data.get("Policy"), dict) else None
                        ]
                        
                        for possible_id in possible_ids:
                            if possible_id:
                                self.test_policy_id = possible_id
                                self.record_created_id(self.test_policy_id, "HealthPolicyManagement___AddPolicy")
                                print(f"📝 ポリシーID記録（手動抽出）: {self.test_policy_id}")
                                break
                        
                        if not self.test_policy_id:
                            print(f"⚠️ policyIdが見つかりません。レスポンス: {data}")
                            # デバッグ用にレスポンス全体を表示
                            print(f"🔍 完全レスポンス: {response}")
                
                # レスポンスデータの検証
                data = response.get("data", {})
                if isinstance(data, dict):
                    # 必須フィールドの確認
                    required_fields = ["policyId", "policyType", "description"]
                    validation = TestUtils.validate_required_fields(data, required_fields)
                    
                    if validation["valid"]:
                        print(f"✅ 必須フィールド確認: {validation['present_fields']}")
                    else:
                        print(f"⚠️ 必須フィールド不足: {validation['missing_fields']}")
                    
                    # パラメータの確認
                    parameters = data.get("parameters", {})
                    if isinstance(parameters, dict):
                        expected_params = policy_data["parameters"]
                        if parameters.get("maxCarbs") == expected_params["maxCarbs"]:
                            print(f"✅ 糖質制限パラメータ確認: {parameters.get('maxCarbs')}")
                        
                        meal_timing = parameters.get("mealTiming", [])
                        if len(meal_timing) == len(expected_params["mealTiming"]):
                            print(f"✅ 食事タイミング確認: {len(meal_timing)}回")
                
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 健康ポリシー追加失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 健康ポリシー追加例外: {str(e)}")
            return False
    
    def test_healthpolicymanagement___getpolicies(self) -> bool:
        """GetPolicies ツールテスト"""
        print("📋 健康ポリシー取得テスト開始...")
        
        arguments = {
            "userId": self.test_user_id
        }
        
        try:
            response = self.mcp_client.call_tool("HealthPolicyManagement___GetPolicies", arguments)
            
            if TestUtils.validate_response_success(response):
                print(f"✅ 健康ポリシー取得成功")
                
                # レスポンスデータの検証
                data = response.get("data", {})
                if isinstance(data, dict):
                    policies = data.get("policies", [])
                    
                    if isinstance(policies, list):
                        print(f"📊 取得されたポリシー数: {len(policies)}")
                        
                        # 作成したポリシーが含まれているか確認
                        if len(policies) > 0:
                            first_policy = policies[0]
                            
                            # policyIdが未取得の場合、ここで取得
                            if not self.test_policy_id and "policyId" in first_policy:
                                self.test_policy_id = first_policy["policyId"]
                                self.record_created_id(self.test_policy_id, "HealthPolicyManagement___AddPolicy")
                                print(f"📝 ポリシーID取得（GetPoliciesから）: {self.test_policy_id}")
                            
                            # ポリシーデータの詳細確認
                            test_data = self.get_required_test_data()
                            initial_policy = test_data["initial_policy"]
                            
                            if first_policy.get("policyType") == initial_policy["policyType"]:
                                print(f"✅ ポリシータイプ確認: {first_policy.get('policyType')}")
                            
                            if first_policy.get("description") == initial_policy["description"]:
                                print(f"✅ ポリシー説明確認: {first_policy.get('description')}")
                            
                            # パラメータの確認
                            parameters = first_policy.get("parameters", {})
                            if isinstance(parameters, dict):
                                expected_params = initial_policy["parameters"]
                                if parameters.get("maxCarbs") == expected_params["maxCarbs"]:
                                    print(f"✅ 糖質制限確認: {parameters.get('maxCarbs')}")
                        
                        return True
                    else:
                        print(f"⚠️ policiesフィールドがリスト形式ではありません: {type(policies)}")
                        return False
                else:
                    print(f"❌ レスポンスデータが辞書形式ではありません: {type(data)}")
                    return False
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 健康ポリシー取得失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 健康ポリシー取得例外: {str(e)}")
            return False
    
    def test_healthpolicymanagement___updatepolicy(self) -> bool:
        """UpdatePolicy ツールテスト"""
        print("📝 健康ポリシー更新テスト開始...")
        
        if not self.test_policy_id:
            print("⚠️ 健康ポリシー更新スキップ: policyIdが取得できませんでした")
            return False
        
        test_data = self.get_required_test_data()
        updated_policy = test_data["updated_policy"]
        
        arguments = {
            "userId": self.test_user_id,
            "policyId": self.test_policy_id,
            **updated_policy
        }
        
        try:
            response = self.mcp_client.call_tool("HealthPolicyManagement___UpdatePolicy", arguments)
            
            if TestUtils.validate_response_success(response):
                print(f"✅ 健康ポリシー更新成功: {self.test_policy_id}")
                
                # レスポンスデータの検証
                data = response.get("data", {})
                if isinstance(data, dict):
                    # 更新されたフィールドの確認
                    if data.get("description") == updated_policy["description"]:
                        print(f"✅ 説明更新確認: {data.get('description')}")
                    
                    # パラメータの更新確認
                    parameters = data.get("parameters", {})
                    if isinstance(parameters, dict):
                        expected_params = updated_policy["parameters"]
                        
                        if parameters.get("maxCarbs") == expected_params["maxCarbs"]:
                            print(f"✅ 糖質制限更新確認: {parameters.get('maxCarbs')}")
                        
                        if parameters.get("cheatDay") == expected_params["cheatDay"]:
                            print(f"✅ チートデイ追加確認: {parameters.get('cheatDay')}")
                        
                        meal_timing = parameters.get("mealTiming", [])
                        expected_timing = expected_params["mealTiming"]
                        if len(meal_timing) == len(expected_timing):
                            print(f"✅ 食事タイミング更新確認: {len(meal_timing)}回")
                
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 健康ポリシー更新失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 健康ポリシー更新例外: {str(e)}")
            return False
    
    def test_healthpolicymanagement___deletepolicy(self) -> bool:
        """DeletePolicy ツールテスト"""
        print("🗑️ 健康ポリシー削除テスト開始...")
        
        if not self.test_policy_id:
            print("⚠️ 健康ポリシー削除スキップ: policyIdが取得できませんでした")
            return False
        
        arguments = {
            "userId": self.test_user_id,
            "policyId": self.test_policy_id
        }
        
        try:
            response = self.mcp_client.call_tool("HealthPolicyManagement___DeletePolicy", arguments)
            
            if TestUtils.validate_response_success(response):
                print(f"✅ 健康ポリシー削除成功: {self.test_policy_id}")
                
                # 削除後の確認（GetPoliciesで確認）
                get_response = self.mcp_client.call_tool("HealthPolicyManagement___GetPolicies", {
                    "userId": self.test_user_id
                })
                
                if TestUtils.validate_response_success(get_response):
                    data = get_response.get("data", {})
                    policies = data.get("policies", [])
                    
                    # 削除されたポリシーが含まれていないことを確認
                    deleted_policy_exists = any(
                        policy.get("policyId") == self.test_policy_id 
                        for policy in policies 
                        if isinstance(policy, dict)
                    )
                    
                    if not deleted_policy_exists:
                        print(f"✅ 削除確認: ポリシーが正常に削除されました")
                    else:
                        print(f"⚠️ 削除未確認: ポリシーがまだ存在しています")
                
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 健康ポリシー削除失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 健康ポリシー削除例外: {str(e)}")
            return False
    
    def _get_created_ids_for_tool(self, tool_name: str) -> List[Dict[str, Any]]:
        """HealthPolicyManagementで作成されたIDリストを取得"""
        if tool_name == "HealthPolicyManagement___AddPolicy" and self.test_policy_id:
            return [{"id": self.test_policy_id, "tool": tool_name}]
        return []
    
    def _delete_single_item(self, cleanup_tool: str, id_info: Dict[str, Any]):
        """健康ポリシーの削除"""
        if cleanup_tool == "HealthPolicyManagement___DeletePolicy":
            delete_params = {
                "userId": self.test_user_id,
                "policyId": id_info["id"]
            }
            
            try:
                response = self.mcp_client.call_tool(cleanup_tool, delete_params)
                
                if TestUtils.validate_response_success(response):
                    print(f"✅ クリーンアップ: ポリシー {id_info['id']} を削除")
                else:
                    print(f"⚠️ クリーンアップ失敗: {response.get('message', 'Unknown error')}")
                    
            except Exception as e:
                print(f"⚠️ クリーンアップ例外: {str(e)}")
    
    def custom_setup(self):
        """HealthPolicyManagement固有のセットアップ"""
        print(f"📋 健康ポリシーテスト用ユーザーID: {self.test_user_id}")
        self.test_policy_id = None
    
    def custom_teardown(self):
        """HealthPolicyManagement固有のクリーンアップ"""
        if self.test_policy_id:
            print(f"📝 作成されたポリシーID: {self.test_policy_id}")
        else:
            print("ℹ️ 作成されたポリシーIDはありません")
    
    def _get_created_ids_for_tool(self, tool_name: str) -> List[Dict[str, Any]]:
        """HealthPolicyManagementで作成されたIDリストを取得"""
        if tool_name == "HealthPolicyManagement___AddPolicy" and self.test_policy_id:
            return [{"id": self.test_policy_id, "tool": tool_name}]
        return []