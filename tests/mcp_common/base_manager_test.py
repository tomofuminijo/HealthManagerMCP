"""
Manager テストの基底クラス

拡張可能な設計でテンプレートメソッドパターンを実装し、
新しいManagerテストの追加を容易にします。
"""

import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from .mcp_client import MCPClient
from .test_utils import TestUtils, TestResult


class BaseManagerTest(ABC):
    """Manager テストの基底クラス（拡張可能設計）"""
    
    def __init__(self, mcp_client: MCPClient, test_user_id: str):
        self.mcp_client = mcp_client
        self.test_user_id = test_user_id
        self.created_ids = []  # 削除対象IDを記録
        self.test_results = {}
        self.execution_times = {}
        self.setup_completed = False
        self.teardown_completed = False
        self.skip_cleanup = False  # クリーンアップをスキップするフラグ
    
    def __del__(self):
        """デストラクタ - 自動的なteardownを制御"""
        # skip_cleanupフラグがTrueの場合は何もしない
        if hasattr(self, 'skip_cleanup') and self.skip_cleanup:
            print(f"🔒 {getattr(self, 'get_manager_name', lambda: 'Unknown')()}: 自動クリーンアップをスキップ（データ保持）")
            return
        
        # 通常のteardownを実行
        if hasattr(self, 'teardown_completed') and not self.teardown_completed:
            try:
                print(f"🧹 {getattr(self, 'get_manager_name', lambda: 'Unknown')()}: 自動クリーンアップ実行")
                self.teardown()
            except Exception as e:
                print(f"⚠️ 自動クリーンアップエラー: {e}")
                pass  # エラーは無視
    
    @abstractmethod
    def get_manager_name(self) -> str:
        """Managerの名前を返す（例: "UserManagement"）"""
        pass
    
    @abstractmethod
    def get_tool_list(self) -> List[str]:
        """テスト対象ツールのリストを返す"""
        pass
    
    @abstractmethod
    def get_cleanup_tools(self) -> Dict[str, str]:
        """削除ツールのマッピングを返す（作成ツール名: 削除ツール名）"""
        pass
    
    def get_required_test_data(self) -> Dict[str, Any]:
        """テストに必要なデータを返す（オーバーライド可能）"""
        return {}
    
    def setup(self):
        """テスト前のセットアップ"""
        if self.setup_completed:
            return
        
        print(f"🔧 {self.get_manager_name()} セットアップ開始...")
        
        # 基本的なセットアップ処理
        self.created_ids.clear()
        self.test_results.clear()
        self.execution_times.clear()
        
        # サブクラス固有のセットアップ
        self.custom_setup()
        
        self.setup_completed = True
        print(f"✅ {self.get_manager_name()} セットアップ完了")
    
    def custom_setup(self):
        """サブクラス固有のセットアップ（オーバーライド可能）"""
        pass
    
    def teardown(self):
        """テスト後のクリーンアップ"""
        if self.teardown_completed:
            print(f"ℹ️ {self.get_manager_name()} teardown既に完了済み")
            return
        
        # skip_cleanupフラグがTrueの場合はクリーンアップをスキップ
        if hasattr(self, 'skip_cleanup') and self.skip_cleanup:
            print(f"🔒 {self.get_manager_name()} クリーンアップをスキップ（データを保持）")
            print(f"📊 保持されるID数: {len(self.created_ids)}")
            return
        
        print(f"🧹 {self.get_manager_name()} クリーンアップ開始...")
        print(f"🔍 デバッグ: skip_cleanup = {getattr(self, 'skip_cleanup', 'NOT_SET')}")
        print(f"📊 削除対象ID数: {len(self.created_ids)}")
        
        # サブクラス固有のクリーンアップ
        self.custom_teardown()
        
        self.teardown_completed = True
        print(f"✅ {self.get_manager_name()} クリーンアップ完了")
    
    def custom_teardown(self):
        """サブクラス固有のクリーンアップ（オーバーライド可能）"""
        pass
    
    def run_tests(self) -> bool:
        """テストを実行（テンプレートメソッドパターン）"""
        try:
            self.setup()
            
            print(f"🚀 {self.get_manager_name()} テスト開始...")
            success = self._execute_tool_tests()
            
            if success:
                print(f"✅ {self.get_manager_name()} 全テスト成功")
            else:
                print(f"❌ {self.get_manager_name()} テストで問題発生")
            
            # テストデータのクリーンアップ
            self.cleanup_test_data()
            
            return success
            
        except Exception as e:
            print(f"❌ {self.get_manager_name()} テスト例外: {str(e)}")
            return False
        finally:
            self.teardown()
    
    def run_creation_and_update_tests(self) -> bool:
        """登録・更新系のテストのみを実行（クリーンアップなし）"""
        try:
            self.skip_cleanup = True  # クリーンアップをスキップ
            print(f"🔒 {self.get_manager_name()}: skip_cleanup = {self.skip_cleanup} に設定")
            self.setup()
            
            print(f"🚀 {self.get_manager_name()} 登録・更新テスト開始...")
            success = self._execute_creation_and_update_tests()
            
            if success:
                print(f"✅ {self.get_manager_name()} 登録・更新テスト成功")
                print(f"📊 作成されたID数: {len(self.created_ids)}")
            else:
                print(f"❌ {self.get_manager_name()} 登録・更新テストで問題発生")
            
            # 重要: ここではクリーンアップしない（データを残す）
            # teardownも呼び出さない
            print(f"🔒 {self.get_manager_name()}: データを保持してテスト終了")
            return success
            
        except Exception as e:
            print(f"❌ {self.get_manager_name()} 登録・更新テスト例外: {str(e)}")
            return False
    
    def run_deletion_tests(self) -> bool:
        """削除系のテストを実行"""
        try:
            self.skip_cleanup = False  # 削除系テストではクリーンアップを有効化
            print(f"🗑️ {self.get_manager_name()} 削除テスト開始...")
            success = self._execute_deletion_tests()
            
            if success:
                print(f"✅ {self.get_manager_name()} 削除テスト成功")
            else:
                print(f"❌ {self.get_manager_name()} 削除テストで問題発生")
            
            return success
            
        except Exception as e:
            print(f"❌ {self.get_manager_name()} 削除テスト例外: {str(e)}")
            return False
        finally:
            self.teardown()
    
    def _execute_creation_and_update_tests(self) -> bool:
        """登録・更新系のツールテストを実行"""
        success = True
        tool_list = self.get_tool_list()
        
        # 削除系ツールを除外
        creation_update_tools = [tool for tool in tool_list if not self._is_deletion_tool(tool)]
        
        print(f"📋 登録・更新テスト対象ツール数: {len(creation_update_tools)}")
        
        for tool_name in creation_update_tools:
            print(f"\n--- {tool_name} テスト ---")
            
            # テストメソッド名を生成
            method_name = self._generate_test_method_name(tool_name)
            
            if hasattr(self, method_name):
                test_method = getattr(self, method_name)
                
                try:
                    start_time = time.time()
                    result = test_method()
                    execution_time = time.time() - start_time
                    
                    self.test_results[tool_name] = result
                    self.execution_times[tool_name] = execution_time
                    
                    if result:
                        print(f"✅ {tool_name} テスト成功 ({execution_time:.2f}秒)")
                    else:
                        print(f"❌ {tool_name} テスト失敗 ({execution_time:.2f}秒)")
                        success = False
                        
                except Exception as e:
                    execution_time = time.time() - start_time
                    error_msg = str(e)
                    
                    self.test_results[tool_name] = False
                    self.execution_times[tool_name] = execution_time
                    
                    print(f"❌ {tool_name} テスト例外: {error_msg} ({execution_time:.2f}秒)")
                    success = False
            else:
                print(f"⚠️ {tool_name} のテストメソッド '{method_name}' が見つかりません")
                self.test_results[tool_name] = False
                success = False
        
        return success
    
    def _execute_deletion_tests(self) -> bool:
        """削除系のツールテストを実行"""
        success = True
        tool_list = self.get_tool_list()
        
        # 削除系ツールのみ
        deletion_tools = [tool for tool in tool_list if self._is_deletion_tool(tool)]
        
        print(f"📋 削除テスト対象ツール数: {len(deletion_tools)}")
        
        for tool_name in deletion_tools:
            print(f"\n--- {tool_name} テスト ---")
            
            # テストメソッド名を生成
            method_name = self._generate_test_method_name(tool_name)
            
            if hasattr(self, method_name):
                test_method = getattr(self, method_name)
                
                try:
                    start_time = time.time()
                    result = test_method()
                    execution_time = time.time() - start_time
                    
                    self.test_results[tool_name] = result
                    self.execution_times[tool_name] = execution_time
                    
                    if result:
                        print(f"✅ {tool_name} テスト成功 ({execution_time:.2f}秒)")
                    else:
                        print(f"❌ {tool_name} テスト失敗 ({execution_time:.2f}秒)")
                        success = False
                        
                except Exception as e:
                    execution_time = time.time() - start_time
                    error_msg = str(e)
                    
                    self.test_results[tool_name] = False
                    self.execution_times[tool_name] = execution_time
                    
                    print(f"❌ {tool_name} テスト例外: {error_msg} ({execution_time:.2f}秒)")
                    success = False
            else:
                print(f"⚠️ {tool_name} のテストメソッド '{method_name}' が見つかりません")
                self.test_results[tool_name] = False
                success = False
        
        return success
    
    def _is_deletion_tool(self, tool_name: str) -> bool:
        """ツールが削除系かどうかを判定"""
        deletion_keywords = ['delete', 'remove', 'clear']
        tool_lower = tool_name.lower()
        return any(keyword in tool_lower for keyword in deletion_keywords)
        """各ツールのテストを実行（自動化）"""
        success = True
        tool_list = self.get_tool_list()
        
        print(f"📋 テスト対象ツール数: {len(tool_list)}")
        
        for tool_name in tool_list:
            print(f"\n--- {tool_name} テスト ---")
            
            # テストメソッド名を生成
            method_name = self._generate_test_method_name(tool_name)
            
            if hasattr(self, method_name):
                test_method = getattr(self, method_name)
                
                try:
                    start_time = time.time()
                    result = test_method()
                    execution_time = time.time() - start_time
                    
                    self.test_results[tool_name] = result
                    self.execution_times[tool_name] = execution_time
                    
                    if result:
                        print(f"✅ {tool_name} テスト成功 ({execution_time:.2f}秒)")
                    else:
                        print(f"❌ {tool_name} テスト失敗 ({execution_time:.2f}秒)")
                        success = False
                        
                except Exception as e:
                    execution_time = time.time() - start_time
                    error_msg = str(e)
                    
                    self.test_results[tool_name] = False
                    self.execution_times[tool_name] = execution_time
                    
                    print(f"❌ {tool_name} テスト例外: {error_msg} ({execution_time:.2f}秒)")
                    success = False
            else:
                print(f"⚠️ {tool_name} のテストメソッド '{method_name}' が見つかりません")
                self.test_results[tool_name] = False
                success = False
        
        return success
    
    def _generate_test_method_name(self, tool_name: str) -> str:
        """ツール名からテストメソッド名を生成"""
        # "ManagerName___ToolName" -> "test_managername___toolname" (3つのアンダースコアを保持)
        method_name = tool_name.lower().replace('-', '_')
        return f"test_{method_name}"
    
    def cleanup_test_data(self):
        """テストデータを削除（自動化）"""
        cleanup_tools = self.get_cleanup_tools()
        
        if not cleanup_tools:
            print(f"ℹ️ {self.get_manager_name()} には削除ツールがありません")
            return
        
        print(f"🗑️ {self.get_manager_name()} テストデータ削除開始...")
        
        # 削除順序を考慮（作成の逆順で削除）
        tools_to_cleanup = []
        for created_tool, cleanup_tool in cleanup_tools.items():
            if cleanup_tool and created_tool in self.test_results and self.test_results[created_tool]:
                tools_to_cleanup.append((created_tool, cleanup_tool))
        
        # 逆順で削除実行
        for created_tool, cleanup_tool in reversed(tools_to_cleanup):
            self._execute_cleanup(created_tool, cleanup_tool)
    
    def _execute_cleanup(self, created_tool: str, cleanup_tool: str):
        """個別のクリーンアップを実行"""
        try:
            # 作成されたIDを取得
            ids_to_delete = self._get_created_ids_for_tool(created_tool)
            
            if not ids_to_delete:
                print(f"ℹ️ {created_tool} で作成されたIDが見つかりません")
                return
            
            # 各IDを削除
            for id_info in ids_to_delete:
                self._delete_single_item(cleanup_tool, id_info)
                
        except Exception as e:
            print(f"⚠️ {created_tool} のクリーンアップエラー: {str(e)}")
    
    def _get_created_ids_for_tool(self, tool_name: str) -> List[Dict[str, Any]]:
        """ツールで作成されたIDリストを取得（サブクラスでオーバーライド）"""
        # デフォルト実装：created_idsから該当するIDを検索
        return [{"id": id_val, "tool": tool_name} for id_val in self.created_ids]
    
    def _delete_single_item(self, cleanup_tool: str, id_info: Dict[str, Any]):
        """単一アイテムを削除（サブクラスでオーバーライド）"""
        # デフォルト実装：基本的な削除パラメータを構築
        delete_params = {
            "userId": self.test_user_id
        }
        
        # IDフィールドを推定
        if "goalId" in cleanup_tool.lower():
            delete_params["goalId"] = id_info["id"]
        elif "policyId" in cleanup_tool.lower():
            delete_params["policyId"] = id_info["id"]
        elif "activityId" in cleanup_tool.lower():
            delete_params["activityId"] = id_info["id"]
            # ActivityManagementの削除には日付が必要
            delete_params["date"] = datetime.now().strftime("%Y-%m-%d")
        elif "measurementId" in cleanup_tool.lower():
            delete_params["measurementId"] = id_info["id"]
            # BodyMeasurementManagementの削除には日付が必要
            if hasattr(self, 'test_date'):
                delete_params["date"] = self.test_date
        elif "concernId" in cleanup_tool.lower():
            delete_params["concernId"] = id_info["id"]
        elif "journalId" in cleanup_tool.lower():
            # JournalManagementは日付ベースの削除（前日の日付を使用）
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            delete_params["date"] = yesterday
        elif "observationId" in cleanup_tool.lower():
            delete_params["observationId"] = id_info["id"]
        
        try:
            response = self.mcp_client.call_tool(cleanup_tool, delete_params)
            
            if TestUtils.validate_response_success(response):
                print(f"✅ {cleanup_tool} で {id_info['id']} を削除")
            else:
                print(f"⚠️ {cleanup_tool} 削除失敗: {response.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"⚠️ {cleanup_tool} 削除例外: {str(e)}")
    
    def record_created_id(self, id_value: str, tool_name: str = None):
        """作成されたIDを記録"""
        if id_value and id_value not in self.created_ids:
            self.created_ids.append(id_value)
            if tool_name:
                print(f"📝 作成ID記録: {id_value} ({tool_name})")
    
    def get_test_summary(self) -> Dict[str, Any]:
        """テスト結果のサマリーを取得"""
        total_tests = len(self.test_results)
        successful_tests = sum(1 for success in self.test_results.values() if success)
        failed_tests = total_tests - successful_tests
        total_time = sum(self.execution_times.values())
        
        return {
            "manager_name": self.get_manager_name(),
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "failed_tests": failed_tests,
            "success_rate": (successful_tests / total_tests * 100) if total_tests > 0 else 0,
            "total_execution_time": total_time,
            "test_results": self.test_results.copy(),
            "execution_times": self.execution_times.copy(),
            "created_ids_count": len(self.created_ids)
        }
    
    def get_test_results_as_objects(self) -> List[TestResult]:
        """テスト結果をTestResultオブジェクトのリストとして取得"""
        results = []
        
        for tool_name, success in self.test_results.items():
            execution_time = self.execution_times.get(tool_name, 0.0)
            error_message = None
            
            if not success:
                error_message = f"{tool_name} テストが失敗しました"
            
            result = TestResult(
                manager_name=self.get_manager_name(),
                tool_name=tool_name,
                success=success,
                execution_time=execution_time,
                error_message=error_message,
                created_ids=self.created_ids.copy()
            )
            
            results.append(result)
        
        return results