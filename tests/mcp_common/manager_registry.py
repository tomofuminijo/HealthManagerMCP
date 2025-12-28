"""
Manager自動発見・登録システム

プラグイン型アーキテクチャで新しいManagerテストの自動発見と登録を行います。
"""

import importlib
import pkgutil
import inspect
import sys
import os
from typing import List, Type, Dict, Any
from .base_manager_test import BaseManagerTest


class ManagerRegistry:
    """Manager自動発見・登録システム"""
    
    _discovered_managers = None
    _manager_cache = {}
    
    @classmethod
    def discover_manager_tests(cls, force_refresh: bool = False) -> List[Type[BaseManagerTest]]:
        """mcp_managersフォルダから全てのManagerテストクラスを自動発見"""
        if cls._discovered_managers is not None and not force_refresh:
            return cls._discovered_managers
        
        print("🔍 Managerテストクラスを自動発見中...")
        
        manager_tests = []
        
        try:
            # mcp_managersパッケージのパスを取得
            current_dir = os.path.dirname(os.path.abspath(__file__))
            managers_path = os.path.join(os.path.dirname(current_dir), 'mcp_managers')
            
            if not os.path.exists(managers_path):
                print(f"⚠️ mcp_managersディレクトリが見つかりません: {managers_path}")
                return []
            
            # sys.pathにmcp_managersの親ディレクトリを追加
            parent_path = os.path.dirname(managers_path)
            if parent_path not in sys.path:
                sys.path.insert(0, parent_path)
            
            # mcp_managersパッケージをインポート
            try:
                import tests.mcp_managers as managers_package
            except ImportError:
                print("⚠️ tests.mcp_managersパッケージのインポートに失敗")
                return []
            
            # パッケージ内の全モジュールを検索
            for importer, modname, ispkg in pkgutil.iter_modules(managers_package.__path__):
                if modname.startswith('test_') and not ispkg:
                    try:
                        print(f"📦 モジュール検査中: {modname}")
                        
                        # モジュールをインポート
                        module = importlib.import_module(f'tests.mcp_managers.{modname}')
                        
                        # モジュール内のBaseManagerTestのサブクラスを検索
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            
                            if (inspect.isclass(attr) and 
                                issubclass(attr, BaseManagerTest) and 
                                attr != BaseManagerTest and
                                not inspect.isabstract(attr)):
                                
                                manager_tests.append(attr)
                                print(f"✅ Managerテスト発見: {attr.__name__}")
                                
                    except ImportError as e:
                        print(f"⚠️ {modname} のインポートに失敗: {e}")
                    except Exception as e:
                        print(f"⚠️ {modname} の処理中にエラー: {e}")
            
            cls._discovered_managers = manager_tests
            print(f"🎯 発見されたManagerテスト数: {len(manager_tests)}")
            
        except Exception as e:
            print(f"❌ Manager自動発見エラー: {str(e)}")
            cls._discovered_managers = []
        
        return cls._discovered_managers
    
    @classmethod
    def get_manager_test_names(cls) -> List[str]:
        """登録されている全てのManagerテスト名を取得"""
        manager_tests = cls.discover_manager_tests()
        names = []
        
        for test_class in manager_tests:
            try:
                # インスタンスを作成せずにクラス名から推定
                class_name = test_class.__name__
                if class_name.endswith('Test'):
                    manager_name = class_name[:-4]  # 'Test'を除去
                else:
                    manager_name = class_name
                
                names.append(manager_name)
                
            except Exception as e:
                print(f"⚠️ {test_class.__name__} の名前取得エラー: {e}")
        
        return names
    
    @classmethod
    def get_manager_test_by_name(cls, manager_name: str) -> Type[BaseManagerTest]:
        """Manager名でテストクラスを取得"""
        manager_tests = cls.discover_manager_tests()
        
        for test_class in manager_tests:
            try:
                # クラス名から推定
                class_name = test_class.__name__
                if class_name.endswith('Test'):
                    class_manager_name = class_name[:-4]
                else:
                    class_manager_name = class_name
                
                if class_manager_name == manager_name:
                    return test_class
                    
            except Exception as e:
                print(f"⚠️ {test_class.__name__} の名前比較エラー: {e}")
        
        raise ValueError(f"Manager '{manager_name}' のテストクラスが見つかりません")
    
    @classmethod
    def create_manager_test_instance(cls, test_class: Type[BaseManagerTest], mcp_client, test_user_id: str) -> BaseManagerTest:
        """Managerテストのインスタンスを作成"""
        try:
            instance = test_class(mcp_client, test_user_id)
            return instance
        except Exception as e:
            raise RuntimeError(f"{test_class.__name__} のインスタンス作成に失敗: {str(e)}")
    
    @classmethod
    def get_manager_info(cls) -> List[Dict[str, Any]]:
        """全てのManagerテストの情報を取得"""
        manager_tests = cls.discover_manager_tests()
        info_list = []
        
        for test_class in manager_tests:
            try:
                # 一時的なインスタンスを作成して情報を取得
                # 注意: 実際のテストは実行しない
                temp_instance = test_class(None, "temp-user")
                
                info = {
                    "class_name": test_class.__name__,
                    "manager_name": temp_instance.get_manager_name(),
                    "tool_count": len(temp_instance.get_tool_list()),
                    "tools": temp_instance.get_tool_list(),
                    "cleanup_tools": temp_instance.get_cleanup_tools(),
                    "has_cleanup": len(temp_instance.get_cleanup_tools()) > 0,
                    "module": test_class.__module__
                }
                
                info_list.append(info)
                
            except Exception as e:
                print(f"⚠️ {test_class.__name__} の情報取得エラー: {e}")
                info_list.append({
                    "class_name": test_class.__name__,
                    "manager_name": "Unknown",
                    "tool_count": 0,
                    "tools": [],
                    "cleanup_tools": {},
                    "has_cleanup": False,
                    "module": test_class.__module__,
                    "error": str(e)
                })
        
        return info_list
    
    @classmethod
    def validate_manager_tests(cls) -> Dict[str, Any]:
        """全てのManagerテストの妥当性を検証"""
        manager_tests = cls.discover_manager_tests()
        validation_results = {
            "total_managers": len(manager_tests),
            "valid_managers": 0,
            "invalid_managers": 0,
            "validation_errors": [],
            "manager_details": []
        }
        
        for test_class in manager_tests:
            try:
                # 一時的なインスタンスを作成して検証
                temp_instance = test_class(None, "validation-user")
                
                # 必須メソッドの存在確認
                required_methods = ['get_manager_name', 'get_tool_list', 'get_cleanup_tools']
                missing_methods = []
                
                for method_name in required_methods:
                    if not hasattr(temp_instance, method_name):
                        missing_methods.append(method_name)
                
                # ツールリストの妥当性確認
                tools = temp_instance.get_tool_list()
                cleanup_tools = temp_instance.get_cleanup_tools()
                
                validation_detail = {
                    "class_name": test_class.__name__,
                    "manager_name": temp_instance.get_manager_name(),
                    "valid": len(missing_methods) == 0,
                    "missing_methods": missing_methods,
                    "tool_count": len(tools),
                    "cleanup_tool_count": len(cleanup_tools),
                    "tools_valid": all(isinstance(tool, str) and '___' in tool for tool in tools),
                    "cleanup_mapping_valid": all(isinstance(k, str) and isinstance(v, str) for k, v in cleanup_tools.items())
                }
                
                if validation_detail["valid"] and validation_detail["tools_valid"] and validation_detail["cleanup_mapping_valid"]:
                    validation_results["valid_managers"] += 1
                else:
                    validation_results["invalid_managers"] += 1
                    validation_results["validation_errors"].append(validation_detail)
                
                validation_results["manager_details"].append(validation_detail)
                
            except Exception as e:
                validation_results["invalid_managers"] += 1
                error_detail = {
                    "class_name": test_class.__name__,
                    "valid": False,
                    "error": str(e)
                }
                validation_results["validation_errors"].append(error_detail)
                validation_results["manager_details"].append(error_detail)
        
        return validation_results
    
    @classmethod
    def print_discovery_report(cls):
        """発見されたManagerテストのレポートを表示"""
        print("\n" + "="*60)
        print("📊 Manager自動発見レポート")
        print("="*60)
        
        manager_info = cls.get_manager_info()
        
        if not manager_info:
            print("❌ Managerテストが見つかりませんでした")
            return
        
        print(f"発見されたManagerテスト数: {len(manager_info)}")
        print()
        
        for info in manager_info:
            if "error" in info:
                print(f"❌ {info['class_name']}: {info['error']}")
            else:
                cleanup_status = "🗑️" if info['has_cleanup'] else "📝"
                print(f"{cleanup_status} {info['manager_name']} ({info['tool_count']}ツール)")
                
                for tool in info['tools']:
                    print(f"   - {tool}")
                
                if info['cleanup_tools']:
                    print(f"   削除ツール: {len(info['cleanup_tools'])}個")
                
                print()
        
        # 検証結果も表示
        validation = cls.validate_manager_tests()
        print(f"✅ 有効: {validation['valid_managers']}")
        print(f"❌ 無効: {validation['invalid_managers']}")
        
        if validation['validation_errors']:
            print("\n⚠️ 検証エラー:")
            for error in validation['validation_errors']:
                print(f"   - {error.get('class_name', 'Unknown')}: {error.get('error', 'Unknown error')}")
        
        print("="*60)