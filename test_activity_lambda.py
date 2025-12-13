"""
Activity Lambda 単体テスト

改良されたActivity Lambda関数の動作を検証します。
"""

import json
import sys
import os

# Lambda関数をインポート
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lambda'))
from activity.handler import (
    add_activities,
    update_activities,
    delete_activity,
    get_activities,
    get_activities_in_range,
    lambda_handler
)

# テスト用のモック
class MockTable:
    def __init__(self):
        self.data = {}
    
    def get_item(self, Key):
        key = f"{Key['userId']}#{Key['date']}"
        if key in self.data:
            return {"Item": self.data[key]}
        return {}
    
    def put_item(self, Item):
        key = f"{Item['userId']}#{Item['date']}"
        self.data[key] = Item
    
    def update_item(self, Key, UpdateExpression, ExpressionAttributeValues):
        key = f"{Key['userId']}#{Key['date']}"
        if key in self.data:
            self.data[key]['activities'] = ExpressionAttributeValues[':activities']
            self.data[key]['updatedAt'] = ExpressionAttributeValues[':updatedAt']
    
    def delete_item(self, Key):
        key = f"{Key['userId']}#{Key['date']}"
        if key in self.data:
            del self.data[key]
    
    def query(self, KeyConditionExpression, ExpressionAttributeNames, ExpressionAttributeValues):
        user_id = ExpressionAttributeValues[':userId']
        start_date = ExpressionAttributeValues[':startDate']
        end_date = ExpressionAttributeValues[':endDate']
        
        items = []
        for key, item in self.data.items():
            if item['userId'] == user_id and start_date <= item['date'] <= end_date:
                items.append(item)
        
        return {"Items": items}

# モックテーブルをセット
import activity.handler as handler
mock_table = MockTable()
handler.table = mock_table

def test_add_activities():
    """AddActivities のテスト"""
    print("\n=== Test: AddActivities ===")
    
    # テスト1: 新規作成（複数の活動）
    print("\n[Test 1] 新規作成 - 複数の活動")
    result = add_activities({
        "userId": "test_user_1",
        "date": "2024-12-09",
        "activities": [
            {
                "time": "07:00",
                "activityType": "wakeUp",
                "description": "起床"
            },
            {
                "time": "08:00",
                "activityType": "meal",
                "description": "朝食",
                "items": ["納豆", "ご飯", "味噌汁"]
            }
        ]
    })
    assert result["success"] == True
    assert result["addedCount"] == 2
    print(f"✓ 結果: {result['message']}")
    
    # テスト2: 既存データに追加
    print("\n[Test 2] 既存データに追加")
    result = add_activities({
        "userId": "test_user_1",
        "date": "2024-12-09",
        "activities": [
            {
                "time": "12:00",
                "activityType": "meal",
                "description": "昼食",
                "items": ["サラダ", "チキン"]
            }
        ]
    })
    assert result["success"] == True
    assert result["addedCount"] == 1
    print(f"✓ 結果: {result['message']}")
    
    # 確認: 3件になっているか
    get_result = get_activities({
        "userId": "test_user_1",
        "date": "2024-12-09"
    })
    assert get_result["count"] == 3
    print(f"✓ 確認: 合計{get_result['count']}件の活動")

def test_update_activities():
    """UpdateActivities のテスト"""
    print("\n=== Test: UpdateActivities ===")
    
    # テスト1: 既存データを上書き
    print("\n[Test 1] 既存データを上書き")
    result = update_activities({
        "userId": "test_user_1",
        "date": "2024-12-09",
        "activities": [
            {
                "time": "07:30",
                "activityType": "wakeUp",
                "description": "起床（修正）"
            },
            {
                "time": "08:30",
                "activityType": "meal",
                "description": "朝食（修正）",
                "items": ["パン", "コーヒー"]
            }
        ]
    })
    assert result["success"] == True
    assert result["updatedCount"] == 2
    print(f"✓ 結果: {result['message']}")
    
    # 確認: 2件に減っているか
    get_result = get_activities({
        "userId": "test_user_1",
        "date": "2024-12-09"
    })
    assert get_result["count"] == 2
    assert get_result["activities"][0]["time"] == "07:30"
    assert get_result["activities"][1]["time"] == "08:30"
    print(f"✓ 確認: {get_result['count']}件に更新され、内容も変更されている")
    
    # テスト2: 新規データとして作成
    print("\n[Test 2] 新規データとして作成")
    result = update_activities({
        "userId": "test_user_2",
        "date": "2024-12-10",
        "activities": [
            {
                "time": "09:00",
                "activityType": "exercise",
                "description": "ジョギング"
            }
        ]
    })
    assert result["success"] == True
    assert result["updatedCount"] == 1
    print(f"✓ 結果: {result['message']}")

def test_delete_activity():
    """DeleteActivity のテスト"""
    print("\n=== Test: DeleteActivity ===")
    
    # 準備: テストデータを作成
    add_activities({
        "userId": "test_user_3",
        "date": "2024-12-11",
        "activities": [
            {"time": "07:00", "activityType": "wakeUp", "description": "起床"},
            {"time": "08:00", "activityType": "meal", "description": "朝食"},
            {"time": "12:00", "activityType": "meal", "description": "昼食"}
        ]
    })
    
    # テスト1: 特定の活動を削除
    print("\n[Test 1] 特定の活動を削除")
    result = delete_activity({
        "userId": "test_user_3",
        "date": "2024-12-11",
        "time": "08:00"
    })
    assert result["success"] == True
    print(f"✓ 結果: {result['message']}")
    
    # 確認: 2件に減っているか
    get_result = get_activities({
        "userId": "test_user_3",
        "date": "2024-12-11"
    })
    assert get_result["count"] == 2
    times = [a["time"] for a in get_result["activities"]]
    assert "08:00" not in times
    print(f"✓ 確認: {get_result['count']}件に減り、08:00の活動が削除されている")
    
    # テスト2: 最後の活動を削除（レコード自体が削除される）
    print("\n[Test 2] 残りの活動を全て削除")
    delete_activity({
        "userId": "test_user_3",
        "date": "2024-12-11",
        "time": "07:00"
    })
    delete_activity({
        "userId": "test_user_3",
        "date": "2024-12-11",
        "time": "12:00"
    })
    
    # 確認: レコードが削除されているか
    get_result = get_activities({
        "userId": "test_user_3",
        "date": "2024-12-11"
    })
    assert get_result["count"] == 0
    print(f"✓ 確認: レコードが削除され、活動が0件")

def test_get_activities_in_range():
    """GetActivitiesInRange のテスト"""
    print("\n=== Test: GetActivitiesInRange ===")
    
    # 準備: 複数日のデータを作成
    for day in range(1, 6):
        date = f"2024-12-{day:02d}"
        add_activities({
            "userId": "test_user_4",
            "date": date,
            "activities": [
                {"time": "07:00", "activityType": "wakeUp", "description": f"{day}日目の起床"}
            ]
        })
    
    # テスト: 期間指定で取得
    print("\n[Test 1] 期間指定で取得")
    result = get_activities_in_range({
        "userId": "test_user_4",
        "startDate": "2024-12-02",
        "endDate": "2024-12-04"
    })
    assert result["success"] == True
    assert result["totalDays"] == 3
    print(f"✓ 結果: {result['totalDays']}日分のデータを取得")
    print(f"  日付: {[d['date'] for d in result['dailyActivities']]}")

def test_mcp_format():
    """MCP形式のイベントテスト"""
    print("\n=== Test: MCP Format ===")
    
    # テスト: MCP形式でAddActivities
    print("\n[Test 1] MCP形式 - AddActivities")
    event = {
        "userId": "test_user_5",
        "date": "2024-12-12",
        "activities": [
            {"time": "10:00", "activityType": "exercise", "description": "ヨガ"}
        ]
    }
    result = lambda_handler(event, None)
    assert result["success"] == True
    print(f"✓ 結果: {result['message']}")
    
    # テスト: MCP形式でGetActivities
    print("\n[Test 2] MCP形式 - GetActivities")
    event = {
        "userId": "test_user_5",
        "date": "2024-12-12"
    }
    result = lambda_handler(event, None)
    assert result["success"] == True
    assert result["count"] == 1
    print(f"✓ 結果: {result['count']}件の活動を取得")

def test_bedrock_agent_format():
    """Bedrock Agent形式のイベントテスト"""
    print("\n=== Test: Bedrock Agent Format ===")
    
    # テスト: Bedrock Agent形式でAddActivities
    print("\n[Test 1] Bedrock Agent形式 - AddActivities")
    event = {
        "actionGroup": "ActivityManagement",
        "apiPath": "/addActivities",
        "httpMethod": "POST",
        "parameters": {
            "userId": "test_user_6",
            "date": "2024-12-13",
            "activities": [
                {"time": "11:00", "activityType": "meal", "description": "ランチ"}
            ]
        }
    }
    result = lambda_handler(event, None)
    assert result["messageVersion"] == "1.0"
    assert result["response"]["httpStatusCode"] == 200
    body = json.loads(result["response"]["responseBody"]["application/json"]["body"])
    assert body["success"] == True
    print(f"✓ 結果: {body['message']}")

def run_all_tests():
    """全テストを実行"""
    print("=" * 60)
    print("Activity Lambda 単体テスト開始")
    print("=" * 60)
    
    try:
        test_add_activities()
        test_update_activities()
        test_delete_activity()
        test_get_activities_in_range()
        test_mcp_format()
        test_bedrock_agent_format()
        
        print("\n" + "=" * 60)
        print("✓ 全てのテストが成功しました！")
        print("=" * 60)
        return True
    except AssertionError as e:
        print(f"\n✗ テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n✗ エラー発生: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
