"""
ActivityLambda関数のプロパティベーステスト

Feature: healthspan100
"""

import json
import os
import sys
from unittest.mock import patch
from hypothesis import given, strategies as st, settings

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))

from activity.handler import add_activity, get_activities


# カスタム戦略
activity_types = st.sampled_from([
    "wakeUp", "sleep", "exercise", "meal", "snack",
    "weight", "bodyFat", "mood", "medication", "other"
])
user_ids = st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_characters="\x00"))
dates = st.dates().map(lambda d: d.strftime("%Y-%m-%d"))
times = st.times().map(lambda t: t.strftime("%H:%M"))
descriptions = st.text(max_size=200)
items_list = st.lists(st.text(max_size=50), max_size=5)


@settings(max_examples=100)
@given(
    user_id=user_ids,
    date=dates,
    time=times,
    activity_type=activity_types,
    description=descriptions,
    items=items_list,
)
def test_property_8_activity_storage_and_association(
    user_id, date, time, activity_type, description, items
):
    """
    Feature: healthspan100, Property 8: 活動記録の保存と関連付け
    検証対象: 要件3.2, 3.3

    任意の活動データに対して、保存されたレコードは正しい日付キーと
    認証されたユーザーIDを持つべきである
    """
    with patch("activity.handler.table") as mock_table:
        # 新規レコード作成のモック
        mock_table.get_item.return_value = {}
        mock_table.put_item.return_value = {}

        # 活動を追加
        add_result = add_activity({
            "userId": user_id,
            "date": date,
            "time": time,
            "activityType": activity_type,
            "description": description,
            "items": items,
        })

        assert add_result["success"] is True

        # put_itemが呼ばれたことを確認
        assert mock_table.put_item.called

        # 保存されたアイテムを取得
        call_args = mock_table.put_item.call_args
        saved_item = call_args[1]["Item"]

        # 正しいuserIdとdateが設定されていることを確認
        assert saved_item["userId"] == user_id
        assert saved_item["date"] == date
        assert "activities" in saved_item
        assert len(saved_item["activities"]) == 1
        assert saved_item["activities"][0]["time"] == time
        assert saved_item["activities"][0]["activityType"] == activity_type


@settings(max_examples=100)
@given(
    user_id=user_ids,
    date=dates,
    num_activities=st.integers(min_value=1, max_value=10),
)
def test_property_9_multiple_activities_individual_records(user_id, date, num_activities):
    """
    Feature: healthspan100, Property 9: 複数活動の個別記録
    検証対象: 要件3.4

    任意のN個の活動報告に対して、システムは1つのDailyActivityレコード内に
    N個の個別ActivityEntryを保存すべきである
    """
    with patch("activity.handler.table") as mock_table:
        # 既存のレコードをシミュレート
        existing_activities = []

        for i in range(num_activities):
            # 各活動を追加
            if i == 0:
                # 最初の活動：新規レコード作成
                mock_table.get_item.return_value = {}
                mock_table.put_item.return_value = {}
            else:
                # 2番目以降：既存レコードに追加
                mock_table.get_item.return_value = {
                    "Item": {
                        "userId": user_id,
                        "date": date,
                        "activities": existing_activities.copy(),
                    }
                }
                mock_table.update_item.return_value = {}

            result = add_activity({
                "userId": user_id,
                "date": date,
                "time": f"{i:02d}:00",
                "activityType": "other",
                "description": f"Activity {i}",
                "items": [],
            })

            assert result["success"] is True

            # 活動リストを更新
            existing_activities.append({
                "time": f"{i:02d}:00",
                "activityType": "other",
                "description": f"Activity {i}",
                "items": [],
            })

        # 最終的に正しい数の活動が保存されていることを確認
        if num_activities == 1:
            # 1つの場合はput_itemが呼ばれる
            call_args = mock_table.put_item.call_args
            saved_item = call_args[1]["Item"]
            assert len(saved_item["activities"]) == 1
        else:
            # 複数の場合は最後のupdate_itemを確認
            call_args = mock_table.update_item.call_args
            updated_activities = call_args[1]["ExpressionAttributeValues"][":activities"]
            assert len(updated_activities) == num_activities


@settings(max_examples=100)
@given(
    user_id=user_ids,
    date=dates,
    time=times,
    original_description=descriptions,
    new_description=descriptions,
)
def test_property_10_existing_record_update(
    user_id, date, time, original_description, new_description
):
    """
    Feature: healthspan100, Property 10: 既存レコードの更新
    検証対象: 要件3.5

    任意の既存の活動記録に対して、同じ日付の新しい活動を報告すると、
    既存レコードが上書きされずに追加されるべきである
    """
    with patch("activity.handler.table") as mock_table:
        # 最初の活動を追加（新規レコード）
        mock_table.get_item.return_value = {}
        mock_table.put_item.return_value = {}

        first_result = add_activity({
            "userId": user_id,
            "date": date,
            "time": time,
            "activityType": "other",
            "description": original_description,
            "items": [],
        })

        assert first_result["success"] is True

        # 同じ日付に2番目の活動を追加（既存レコードに追加）
        mock_table.get_item.return_value = {
            "Item": {
                "userId": user_id,
                "date": date,
                "activities": [{
                    "time": time,
                    "activityType": "other",
                    "description": original_description,
                    "items": [],
                }],
            }
        }
        mock_table.update_item.return_value = {}

        # 異なる時刻で2番目の活動を追加
        second_time = "23:59" if time != "23:59" else "00:00"
        second_result = add_activity({
            "userId": user_id,
            "date": date,
            "time": second_time,
            "activityType": "other",
            "description": new_description,
            "items": [],
        })

        assert second_result["success"] is True

        # update_itemが呼ばれたことを確認（上書きではなく追加）
        assert mock_table.update_item.called

        # 更新された活動リストを確認
        call_args = mock_table.update_item.call_args
        updated_activities = call_args[1]["ExpressionAttributeValues"][":activities"]

        # 2つの活動が存在することを確認（上書きされていない）
        assert len(updated_activities) == 2
        assert updated_activities[0]["time"] == time
        assert updated_activities[1]["time"] == second_time
