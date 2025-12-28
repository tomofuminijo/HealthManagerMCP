"""
JournalManagement MCP ツールのテストモジュール

このモジュールは、JournalManagement関連のMCPツールをテストします。
- AddJournal: 日記エントリの追加
- GetJournal: 特定の日記エントリの取得
- GetJournalsInRange: 期間内の日記エントリの取得
- UpdateJournal: 日記エントリの更新（追記・更新機能）
- DeleteJournal: 日記エントリの削除
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any

from ..mcp_common.base_manager_test import BaseManagerTest
from ..mcp_common.test_utils import TestUtils


class JournalManagementTest(BaseManagerTest):
    """JournalManagement MCPツールのテストクラス"""
    
    def get_manager_name(self) -> str:
        """Managerの名前を返す"""
        return "JournalManagement"
    
    def get_tool_list(self) -> List[str]:
        """このManagerでテストするツールのリストを返す"""
        return [
            "JournalManagement___AddJournal",
            "JournalManagement___GetJournal",
            "JournalManagement___GetJournalsInRange",
            "JournalManagement___UpdateJournal",
            "JournalManagement___DeleteJournal"
        ]
    
    def get_cleanup_tools(self) -> Dict[str, str]:
        """テストデータクリーンアップに使用するツールのマッピングを返す"""
        return {
            "JournalManagement___AddJournal": "JournalManagement___DeleteJournal"
        }
    
    def get_required_test_data(self) -> Dict[str, Any]:
        """テスト用の日記データを生成"""
        return {
            "journal_data": {
                "date": datetime.now().strftime("%Y-%m-%d"),  # 必須フィールド
                "content": "今日は早起きして、朝のジョギングを30分行った。朝食は野菜たっぷりのサラダとヨーグルト。",
                "moodScore": 4,
                "tags": ["Exercise", "Healthy", "Morning", "Productive"]  # PascalCase英語形式
            }
        }
    
    def test_journalmanagement___addjournal(self) -> bool:
        """JournalManagement___AddJournal ツールのテスト"""
        print("📝 日記エントリ追加テスト開始...")
        
        test_data = self.get_required_test_data()
        journal_data = test_data["journal_data"]
        
        arguments = {
            "userId": self.test_user_id,
            **journal_data
        }
        
        try:
            response = self.mcp_client.call_tool("JournalManagement___AddJournal", arguments)
            
            if TestUtils.validate_response_success(response):
                print("✅ 日記エントリ追加成功")
                
                # JournalManagementは日付ベースなのでjournalIdではなく日付を記録
                date = journal_data.get("date")
                if date:
                    self.created_ids.append(("journal", date))
                    print(f"📝 作成日付記録: {date} (JournalManagement___AddJournal)")
                    return True
                else:
                    print("⚠️ 日付が見つかりません")
                    return False
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 日記エントリ追加失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 日記エントリ追加エラー: {str(e)}")
            return False
    
    def test_journalmanagement___getjournal(self) -> bool:
        """JournalManagement___GetJournal ツールのテスト"""
        print("📝 日記エントリ取得テスト開始...")
        
        arguments = {
            "userId": self.test_user_id,
            "date": datetime.now().strftime("%Y-%m-%d")  # 必須フィールド
        }
        
        try:
            response = self.mcp_client.call_tool("JournalManagement___GetJournal", arguments)
            
            if TestUtils.validate_response_success(response):
                print("✅ 日記エントリ取得成功")
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 日記エントリ取得失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 日記エントリ取得エラー: {str(e)}")
            return False
    
    def test_journalmanagement___getjournalsinrange(self) -> bool:
        """JournalManagement___GetJournalsInRange ツールのテスト"""
        print("📝 期間内日記エントリ取得テスト開始...")
        
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")
        
        arguments = {
            "userId": self.test_user_id,
            "startDate": start_date,
            "endDate": end_date
        }
        
        try:
            response = self.mcp_client.call_tool("JournalManagement___GetJournalsInRange", arguments)
            
            if TestUtils.validate_response_success(response):
                print("✅ 期間内日記エントリ取得成功")
                
                # データ数を確認
                journal_count = TestUtils.extract_data_count_from_response(response, "journals")
                print(f"📊 取得された日記数: {journal_count}件")
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 期間内日記エントリ取得失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 期間内日記エントリ取得エラー: {str(e)}")
            return False
    
    def test_journalmanagement___updatejournal(self) -> bool:
        """JournalManagement___UpdateJournal ツールのテスト"""
        print("📝 日記エントリ更新テスト開始...")
        
        arguments = {
            "userId": self.test_user_id,
            "date": datetime.now().strftime("%Y-%m-%d"),  # 必須フィールド
            "content": "健康的な一日（更新版）- 夕方にもウォーキングを追加した。",
            "moodScore": 5
        }
        
        try:
            response = self.mcp_client.call_tool("JournalManagement___UpdateJournal", arguments)
            
            if TestUtils.validate_response_success(response):
                print("✅ 日記エントリ更新成功")
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 日記エントリ更新失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 日記エントリ更新エラー: {str(e)}")
            return False
    
    def test_journalmanagement___deletejournal(self) -> bool:
        """JournalManagement___DeleteJournal ツールのテスト"""
        print("📝 日記エントリ削除テスト開始...")
        
        arguments = {
            "userId": self.test_user_id,
            "date": datetime.now().strftime("%Y-%m-%d")  # 必須フィールド
        }
        
        try:
            response = self.mcp_client.call_tool("JournalManagement___DeleteJournal", arguments)
            
            if TestUtils.validate_response_success(response):
                print("✅ 日記エントリ削除成功")
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"❌ 日記エントリ削除失敗: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 日記エントリ削除エラー: {str(e)}")
            return False