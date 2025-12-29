"""
全Manager統合テストモジュール

Manager自動発見機能を使用して全てのManagerテストを実行し、
HolisticUserDataServiceでの包括的検証を行います。
"""

import time
from typing import List, Dict, Any, Optional
from ..mcp_common.config import Config
from ..mcp_common.auth_client import AuthClient
from ..mcp_common.mcp_client import MCPClient
from ..mcp_common.test_utils import TestUtils, TestResult
from ..mcp_common.manager_registry import ManagerRegistry
from ..mcp_common.base_manager_test import BaseManagerTest


class AllManagersTest:
    """全Manager統合テスト（拡張可能設計）"""
    
    def __init__(self):
        print("🚀 HealthManager MCP統合テスト初期化中...")
        
        # 設定とクライアントの初期化
        self.config = Config()
        self.auth_client = AuthClient(self.config)
        self.mcp_client = MCPClient(self.auth_client, self.config)
        
        # テスト用ユーザーIDを生成
        self.test_user_id = TestUtils.generate_test_user_id()
        
        # テスト結果の保存
        self.manager_tests = []
        self.test_results = {}
        self.holistic_data_result = None
        self.start_time = None
        self.end_time = None
        
        print(f"👤 テストユーザーID: {self.test_user_id}")
    
    def setup(self) -> bool:
        """統合テスト前のセットアップ"""
        print("\n🔧 統合テストセットアップ開始...")
        
        try:
            # 認証テスト
            if not self.auth_client.authenticate_m2m():
                print("❌ M2M認証に失敗しました")
                return False
            
            # MCP接続テスト
            if not self.mcp_client.test_connection():
                print("❌ MCP接続テストに失敗しました")
                return False
            
            # Managerテストの自動発見と初期化
            self.setup_manager_tests()
            
            print("✅ 統合テストセットアップ完了")
            return True
            
        except Exception as e:
            print(f"❌ 統合テストセットアップエラー: {str(e)}")
            return False
    
    def setup_manager_tests(self):
        """各Managerテストを自動発見・初期化"""
        print("🔍 Managerテストを自動発見中...")
        
        manager_test_classes = ManagerRegistry.discover_manager_tests()
        
        if not manager_test_classes:
            print("⚠️ Managerテストが見つかりませんでした")
            return
        
        for test_class in manager_test_classes:
            try:
                manager_test = ManagerRegistry.create_manager_test_instance(
                    test_class, self.mcp_client, self.test_user_id
                )
                # 重要: 登録・更新系テストではクリーンアップをスキップ
                manager_test.skip_cleanup = True
                print(f"🔒 {manager_test.get_manager_name()}: skip_cleanup = True に設定")
                
                self.manager_tests.append(manager_test)
                print(f"✅ {manager_test.get_manager_name()} テストを登録")
                
            except Exception as e:
                print(f"⚠️ {test_class.__name__} の初期化に失敗: {e}")
        
        print(f"🎯 登録されたManagerテスト数: {len(self.manager_tests)}")
        print(f"🔒 全Managerテストでskip_cleanup = True に設定済み")
    
    def run_creation_and_update_tests(self) -> bool:
        """登録・更新系のテストのみを実行"""
        print(f"\n🚀 登録・更新系テスト開始...")
        print(f"📊 実行予定Managerテスト数: {len(self.manager_tests)}")
        
        # 全Managerテストのskip_cleanupフラグを確認・設定
        for manager_test in self.manager_tests:
            manager_test.skip_cleanup = True
            print(f"🔒 {manager_test.get_manager_name()}: skip_cleanup = {manager_test.skip_cleanup}")
        
        self.start_time = time.time()
        overall_success = True
        
        # 各Managerテストの登録・更新系のみ実行
        for i, manager_test in enumerate(self.manager_tests, 1):
            manager_name = manager_test.get_manager_name()
            print(f"\n{'='*60}")
            print(f"📋 [{i}/{len(self.manager_tests)}] {manager_name} 登録・更新テスト開始")
            print(f"🔒 skip_cleanup状態: {manager_test.skip_cleanup}")
            print(f"{'='*60}")
            
            try:
                test_start_time = time.time()
                success = manager_test.run_creation_and_update_tests()
                test_execution_time = time.time() - test_start_time
                
                # テスト結果を保存
                self.test_results[manager_name] = {
                    'success': success,
                    'execution_time': test_execution_time,
                    'tool_results': manager_test.test_results.copy(),
                    'created_ids_count': len(manager_test.created_ids),
                    'summary': manager_test.get_test_summary()
                }
                
                if success:
                    print(f"✅ {manager_name} 登録・更新テスト完了 ({test_execution_time:.2f}秒)")
                    print(f"📝 作成されたID数: {len(manager_test.created_ids)}")
                else:
                    print(f"❌ {manager_name} 登録・更新テストで問題発生 ({test_execution_time:.2f}秒)")
                    overall_success = False
                    
            except Exception as e:
                test_execution_time = time.time() - test_start_time if 'test_start_time' in locals() else 0
                print(f"❌ {manager_name} 登録・更新テスト例外: {str(e)} ({test_execution_time:.2f}秒)")
                
                self.test_results[manager_name] = {
                    'success': False,
                    'execution_time': test_execution_time,
                    'error': str(e),
                    'tool_results': {},
                    'created_ids_count': 0
                }
                overall_success = False
        
        print(f"\n{'='*60}")
        if overall_success:
            print("✅ 全Manager登録・更新テスト完了")
            # 作成されたデータの総数を表示
            total_created_ids = sum(len(manager_test.created_ids) for manager_test in self.manager_tests)
            print(f"📊 総作成ID数: {total_created_ids}")
        else:
            print("❌ 一部のManager登録・更新テストで問題が発生しました")
        print(f"{'='*60}")
        
        return overall_success
    
    def run_deletion_tests(self) -> bool:
        """削除系のテストを実行"""
        print(f"\n🗑️ 削除系テスト開始...")
        
        deletion_success = True
        
        # 各Managerテストの削除系を実行
        for i, manager_test in enumerate(self.manager_tests, 1):
            manager_name = manager_test.get_manager_name()
            print(f"\n--- [{i}/{len(self.manager_tests)}] {manager_name} 削除テスト ---")
            
            try:
                # 削除系テストではクリーンアップを有効化
                manager_test.skip_cleanup = False
                
                test_start_time = time.time()
                success = manager_test.run_deletion_tests()
                test_execution_time = time.time() - test_start_time
                
                if success:
                    print(f"✅ {manager_name} 削除テスト完了 ({test_execution_time:.2f}秒)")
                else:
                    print(f"❌ {manager_name} 削除テストで問題発生 ({test_execution_time:.2f}秒)")
                    deletion_success = False
                    
            except Exception as e:
                test_execution_time = time.time() - test_start_time if 'test_start_time' in locals() else 0
                print(f"❌ {manager_name} 削除テスト例外: {str(e)} ({test_execution_time:.2f}秒)")
                deletion_success = False
        
        print(f"\n{'='*60}")
        if deletion_success:
            print("✅ 全Manager削除テスト完了")
        else:
            print("❌ 一部のManager削除テストで問題が発生しました")
        print(f"{'='*60}")
        
        return deletion_success
        """全てのManagerテストを自動実行"""
        print(f"\n🚀 全Manager統合テスト開始...")
        print(f"📊 実行予定Managerテスト数: {len(self.manager_tests)}")
        
        self.start_time = time.time()
        overall_success = True
        
        # 各Managerテストを順次実行
        for i, manager_test in enumerate(self.manager_tests, 1):
            manager_name = manager_test.get_manager_name()
            print(f"\n{'='*60}")
            print(f"📋 [{i}/{len(self.manager_tests)}] {manager_name} テスト開始")
            print(f"{'='*60}")
            
            try:
                test_start_time = time.time()
                success = manager_test.run_tests()
                test_execution_time = time.time() - test_start_time
                
                # テスト結果を保存
                self.test_results[manager_name] = {
                    'success': success,
                    'execution_time': test_execution_time,
                    'tool_results': manager_test.test_results.copy(),
                    'created_ids_count': len(manager_test.created_ids),
                    'summary': manager_test.get_test_summary()
                }
                
                if success:
                    print(f"✅ {manager_name} テスト完了 ({test_execution_time:.2f}秒)")
                else:
                    print(f"❌ {manager_name} テストで問題発生 ({test_execution_time:.2f}秒)")
                    overall_success = False
                    
            except Exception as e:
                test_execution_time = time.time() - test_start_time if 'test_start_time' in locals() else 0
                print(f"❌ {manager_name} テスト例外: {str(e)} ({test_execution_time:.2f}秒)")
                
                self.test_results[manager_name] = {
                    'success': False,
                    'execution_time': test_execution_time,
                    'error': str(e),
                    'tool_results': {},
                    'created_ids_count': 0
                }
                overall_success = False
        
        self.end_time = time.time()
        
        print(f"\n{'='*60}")
        if overall_success:
            print("✅ 全Managerテスト完了")
        else:
            print("❌ 一部のManagerテストで問題が発生しました")
        print(f"{'='*60}")
        
        return overall_success
    
    def test_holistic_user_data(self) -> bool:
        """HolisticUserDataService テスト"""
        print(f"\n🔍 HolisticUserDataService包括検証開始...")
        print(f"👤 検証対象ユーザーID: {self.test_user_id}")
        
        try:
            arguments = {
                "userId": self.test_user_id
            }
            
            print(f"📡 HolisticUserDataService呼び出し中...")
            response = self.mcp_client.call_tool(
                "HolisticUserDataService___GetUserHolisticData", 
                arguments,
                timeout=60  # 大量データ処理のため長めのタイムアウト
            )
            
            if TestUtils.validate_response_success(response):
                print("✅ HolisticUserDataService呼び出し成功")
                
                # MCPレスポンスの構造を詳細に解析
                print(f"🔍 レスポンス構造解析開始...")
                raw_response = response.get("data", {})
                print(f"📊 生レスポンスキー: {list(raw_response.keys()) if isinstance(raw_response, dict) else type(raw_response)}")
                
                # JSON-RPC 2.0レスポンスの場合
                actual_data = None
                if 'result' in raw_response:
                    result = raw_response['result']
                    print(f"🔍 result構造: {list(result.keys()) if isinstance(result, dict) else type(result)}")
                    
                    if 'content' in result and isinstance(result['content'], list) and len(result['content']) > 0:
                        content_item = result['content'][0]
                        if 'text' in content_item:
                            # JSON文字列をパース
                            import json
                            try:
                                text_data = json.loads(content_item['text'])
                                print(f"🔍 パース後のテキストデータ: {list(text_data.keys()) if isinstance(text_data, dict) else type(text_data)}")
                                
                                if 'data' in text_data:
                                    actual_data = text_data['data']
                                    print(f"✅ 実際のデータを抽出: {list(actual_data.keys()) if isinstance(actual_data, dict) else type(actual_data)}")
                                else:
                                    actual_data = text_data
                                    print(f"✅ テキストデータをそのまま使用: {list(actual_data.keys()) if isinstance(actual_data, dict) else type(actual_data)}")
                                    
                            except json.JSONDecodeError as e:
                                print(f"❌ JSONパースエラー: {e}")
                                print(f"🔍 パース対象テキスト: {content_item['text'][:500]}...")
                                return False
                        else:
                            print(f"⚠️ content[0]にtextフィールドがありません: {content_item}")
                            return False
                    else:
                        print(f"⚠️ resultにcontentがないか空です: {result}")
                        return False
                else:
                    print(f"⚠️ レスポンスにresultがありません")
                    actual_data = raw_response
                
                if actual_data is None:
                    print(f"❌ 実際のデータを抽出できませんでした")
                    return False
                
                print(f"📊 取得データセクション数: {len(actual_data) if isinstance(actual_data, dict) else 'N/A'}")
                
                # 各セクションのデータ数を表示
                if isinstance(actual_data, dict):
                    for section, section_data in actual_data.items():
                        if isinstance(section_data, list):
                            count = len(section_data)
                            print(f"   - {section}: {count}個")
                            if count > 0:
                                print(f"     サンプル: {str(section_data[0])[:100]}...")
                        elif isinstance(section_data, dict):
                            if section == 'userProfile':
                                count = 1 if section_data else 0
                                print(f"   - {section}: {count}個")
                                if section_data:
                                    print(f"     サンプル: {str(section_data)[:100]}...")
                            elif section == 'bodyMeasurements':
                                # bodyMeasurementsは特殊構造
                                total_measurements = 0
                                if 'history' in section_data:
                                    total_measurements = len(section_data['history'])
                                print(f"   - {section}: {total_measurements}個（履歴）")
                                if total_measurements > 0:
                                    print(f"     サンプル: {str(section_data['history'][0])[:100]}...")
                            else:
                                count = len(section_data)
                                print(f"   - {section}: {count}個（辞書形式）")
                                if count > 0:
                                    sample_key = list(section_data.keys())[0]
                                    print(f"     サンプル: {sample_key}: {str(section_data[sample_key])[:100]}...")
                        else:
                            print(f"   - {section}: {type(section_data).__name__}型")
                            print(f"     値: {str(section_data)[:100]}...")
                else:
                    print(f"⚠️ 予期しないデータ構造: {type(actual_data)}")
                    print(f"🔍 生データ: {str(actual_data)[:500]}...")
                
                validation_result = self._validate_holistic_data(actual_data)
                
                self.holistic_data_result = {
                    'success': True,
                    'validation': validation_result,
                    'data_summary': self._create_data_summary(actual_data)
                }
                
                # データ数の合計を計算
                total_items = sum(validation_result.get('data_counts', {}).values())
                print(f"📊 総データ数: {total_items}個")
                
                if validation_result['overall_valid']:
                    if total_items > 0:
                        print("✅ HolisticUserDataService包括検証成功（データ存在確認）")
                        return True
                    else:
                        print("⚠️ HolisticUserDataService包括検証: データが0個です")
                        print("💡 登録・更新系テストが正常に実行されていない可能性があります")
                        return False
                else:
                    print("⚠️ HolisticUserDataService包括検証で一部問題を検出")
                    return False
                
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ HolisticUserDataService呼び出し失敗: {error_msg}")
                
                self.holistic_data_result = {
                    'success': False,
                    'error': error_msg
                }
                return False
                
        except Exception as e:
            print(f"❌ HolisticUserDataService例外: {str(e)}")
            import traceback
            print(f"🔍 スタックトレース: {traceback.format_exc()}")
            self.holistic_data_result = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def _validate_holistic_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """包括データの詳細検証"""
        validation = {
            'overall_valid': True,
            'sections': {},
            'missing_sections': [],
            'data_counts': {}
        }
        
        # 期待されるセクション（実際のHolisticUserDataServiceのレスポンス構造に合わせる）
        expected_sections = [
            'userProfile', 'goals', 'policies', 'activities', 
            'bodyMeasurements', 'concerns', 'journals', 'observations'
        ]
        
        for section in expected_sections:
            if section in data:
                section_data = data[section]
                section_valid = self._validate_section_data(section, section_data)
                validation['sections'][section] = section_valid
                
                # データ数をカウント
                if isinstance(section_data, list):
                    validation['data_counts'][section] = len(section_data)
                elif isinstance(section_data, dict):
                    if section == 'userProfile':
                        validation['data_counts'][section] = 1 if section_data else 0
                    elif section == 'journals':
                        # journalsセクションは前日の日記があるかどうかで判定
                        validation['data_counts'][section] = 1 if section_data.get('previousDay') else 0
                    else:
                        validation['data_counts'][section] = len(section_data)
                else:
                    validation['data_counts'][section] = 1 if section_data else 0
                
                if not section_valid['valid']:
                    validation['overall_valid'] = False
                    
            else:
                validation['missing_sections'].append(section)
                validation['sections'][section] = {'valid': False, 'reason': 'Section not found'}
                validation['data_counts'][section] = 0
                validation['overall_valid'] = False
        
        return validation
    
    def _validate_section_data(self, section: str, data: Any) -> Dict[str, Any]:
        """個別セクションデータの検証"""
        if section == 'userProfile':
            if isinstance(data, dict) and data:
                required_fields = ['userId', 'username', 'email']
                field_validation = TestUtils.validate_required_fields(data, required_fields)
                return {
                    'valid': field_validation['valid'],
                    'details': field_validation
                }
            else:
                return {'valid': False, 'reason': 'User profile is empty or invalid format'}
        
        elif section in ['goals', 'policies', 'activities', 'concerns', 'observations']:
            if isinstance(data, list):
                return {
                    'valid': True,
                    'count': len(data),
                    'details': f"{len(data)} items found"
                }
            else:
                return {'valid': False, 'reason': f'{section} is not a list'}
        
        elif section == 'journals':
            if isinstance(data, dict):
                # journalsは辞書形式で前日の日記データを含む
                has_previous_day = 'previousDay' in data
                return {
                    'valid': has_previous_day,
                    'details': f"Previous day journal: {'found' if has_previous_day else 'not found'}"
                }
            else:
                return {'valid': False, 'reason': 'journal is not a dict'}
        
        elif section == 'bodyMeasurements':
            if isinstance(data, dict):
                # bodyMeasurementsは特殊な構造（latest, oldest, history）
                has_structure = any(key in data for key in ['latest', 'oldest', 'history'])
                return {
                    'valid': has_structure,
                    'details': f"Structure keys: {list(data.keys())}"
                }
            else:
                return {'valid': False, 'reason': 'Body measurements is not a dict'}
        
        else:
            return {'valid': True, 'details': 'Unknown section, assuming valid'}
    
    def _create_data_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """データサマリーを作成"""
        summary = {}
        
        for section, section_data in data.items():
            if isinstance(section_data, list):
                summary[section] = {
                    'type': 'list',
                    'count': len(section_data),
                    'sample': section_data[:2] if section_data else []
                }
            elif isinstance(section_data, dict):
                summary[section] = {
                    'type': 'dict',
                    'keys': list(section_data.keys()),
                    'sample': {k: v for k, v in list(section_data.items())[:2]}
                }
            else:
                summary[section] = {
                    'type': type(section_data).__name__,
                    'value': str(section_data)[:100]
                }
        
        return summary
    
    def cleanup_all_test_data(self):
        """全てのテストデータを自動削除"""
        print(f"\n🧹 全テストデータクリーンアップ開始...")
        
        cleanup_count = 0
        
        for manager_test in self.manager_tests:
            try:
                manager_name = manager_test.get_manager_name()
                print(f"🗑️ {manager_name} データクリーンアップ中...")
                
                manager_test.cleanup_test_data()
                cleanup_count += 1
                
            except Exception as e:
                print(f"⚠️ {manager_test.get_manager_name()} のクリーンアップ失敗: {e}")
        
        print(f"✅ クリーンアップ完了: {cleanup_count}/{len(self.manager_tests)} Manager")
    
    def generate_comprehensive_report(self):
        """包括的なテスト結果レポートを生成"""
        print("\n" + "="*80)
        print("📊 HealthManager MCP統合テスト結果レポート")
        print("="*80)
        
        # 実行時間情報
        total_time = self.end_time - self.start_time if self.end_time and self.start_time else 0
        print(f"⏱️ 総実行時間: {total_time:.2f}秒")
        print(f"👤 テストユーザーID: {self.test_user_id}")
        
        # Manager別結果
        total_managers = len(self.test_results)
        successful_managers = sum(1 for result in self.test_results.values() if result.get('success', False))
        
        print(f"\n📋 Managerテスト結果:")
        print(f"   総Manager数: {total_managers}")
        print(f"   成功: {successful_managers}")
        print(f"   失敗: {total_managers - successful_managers}")
        print(f"   成功率: {(successful_managers / total_managers * 100):.1f}%" if total_managers > 0 else "   成功率: 0%")
        
        # 各Managerの詳細
        print(f"\n📊 Manager別詳細結果:")
        for manager_name, result in self.test_results.items():
            status = "✅" if result.get('success', False) else "❌"
            execution_time = result.get('execution_time', 0)
            created_ids = result.get('created_ids_count', 0)
            
            print(f"{status} {manager_name} ({execution_time:.2f}秒, {created_ids}個のID作成)")
            
            # ツール別結果
            tool_results = result.get('tool_results', {})
            for tool_name, tool_success in tool_results.items():
                tool_status = "  ✅" if tool_success else "  ❌"
                print(f"{tool_status} {tool_name}")
        
        # HolisticUserDataService結果
        print(f"\n🔍 HolisticUserDataService結果:")
        if self.holistic_data_result:
            if self.holistic_data_result.get('success', False):
                validation = self.holistic_data_result.get('validation', {})
                data_counts = validation.get('data_counts', {})
                
                print("✅ HolisticUserDataService検証成功")
                print("📊 データ数サマリー:")
                for section, count in data_counts.items():
                    print(f"   - {section}: {count}個")
                
                # データが存在することを確認
                total_items = sum(data_counts.values())
                if total_items > 0:
                    print(f"✅ 合計 {total_items}個のデータが正常に取得されました")
                else:
                    print("⚠️ データが0個です - 登録・更新テストが正常に実行されていない可能性があります")
                
                missing_sections = validation.get('missing_sections', [])
                if missing_sections:
                    print(f"⚠️ 不足セクション: {', '.join(missing_sections)}")
                
            else:
                error = self.holistic_data_result.get('error', 'Unknown error')
                print(f"❌ HolisticUserDataService検証失敗: {error}")
        else:
            print("⚠️ HolisticUserDataService未実行")
        
        # 推奨事項
        print(f"\n💡 推奨事項:")
        if total_managers - successful_managers > 0:
            print("   - 失敗したManagerテストのエラーログを確認してください")
        
        if self.holistic_data_result and not self.holistic_data_result.get('success', False):
            print("   - HolisticUserDataServiceの設定を確認してください")
        
        print("   - テストデータが正常にクリーンアップされたか確認してください")
        
        print("="*80)
    
    def run_complete_test_suite(self) -> bool:
        """完全なテストスイートを実行（正しい順序で）"""
        try:
            # セットアップ
            if not self.setup():
                return False
            
            print(f"\n🎯 テスト実行順序:")
            print(f"   1. 登録・更新系テスト（データ作成）")
            print(f"   2. HolisticUserDataService検証（データ存在確認）")
            print(f"   3. 削除系テスト（データクリーンアップ）")
            
            # 1. 登録・更新系のテスト実行（削除系は除外、クリーンアップもスキップ）
            print(f"\n{'='*60}")
            print(f"🚀 フェーズ1: 登録・更新系テスト実行")
            print(f"{'='*60}")
            managers_success = self.run_creation_and_update_tests()
            
            if not managers_success:
                print("❌ 登録・更新系テストが失敗したため、後続テストをスキップします")
                return False
            
            # 2. HolisticUserDataService検証（データが存在する状態で）
            print(f"\n{'='*60}")
            print(f"🔍 フェーズ2: データ存在状態でのHolisticUserDataService検証")
            print(f"{'='*60}")
            holistic_success = self.test_holistic_user_data()
            
            # 3. 削除系のテスト実行
            print(f"\n{'='*60}")
            print(f"🗑️ フェーズ3: 削除系テスト実行")
            print(f"{'='*60}")
            deletion_success = self.run_deletion_tests()
            
            # 4. 最終クリーンアップ（念のため）
            print(f"\n🧹 最終クリーンアップ...")
            self.cleanup_all_test_data()
            
            # 結果レポート生成
            self.generate_comprehensive_report()
            
            # 総合結果
            overall_success = managers_success and holistic_success and deletion_success
            
            print(f"\n🎯 統合テスト総合結果: {'✅ 成功' if overall_success else '❌ 失敗'}")
            print(f"   - 登録・更新系: {'✅' if managers_success else '❌'}")
            print(f"   - HolisticUserDataService: {'✅' if holistic_success else '❌'}")
            print(f"   - 削除系: {'✅' if deletion_success else '❌'}")
            
            return overall_success
            
        except Exception as e:
            print(f"❌ 統合テスト実行エラー: {str(e)}")
            return False


def main():
    """メイン実行関数"""
    print("🚀 HealthManager MCP統合テスト開始")
    
    # Manager自動発見レポートを表示
    ManagerRegistry.print_discovery_report()
    
    # 統合テスト実行
    test_suite = AllManagersTest()
    success = test_suite.run_complete_test_suite()
    
    # 終了コード
    exit_code = 0 if success else 1
    print(f"\n🏁 統合テスト終了 (終了コード: {exit_code})")
    
    return exit_code


if __name__ == "__main__":
    exit(main())