import uuid
from datetime import datetime, timezone, timedelta
from boto3.dynamodb.conditions import Key, Attr
from typing import List

def to_serializable(value):
    """Chuyển datetime về string ISO, giữ nguyên các loại khác."""
    if isinstance(value, datetime):
        return value.isoformat()
    return value

def recommended_actions_to_text(actions: dict) -> str:
    """
    Chuyển dict khuyến nghị điều chỉnh (recommended_actions) thành mô tả dạng text.

    Logic:
    - Chỉ sinh text tại các mốc thời gian bội số của 5 phút.
    - Với mỗi hành động:
        + Giá trị > 0 → tăng
        + Giá trị < 0 → giảm
        + Giá trị = 0 → bỏ qua
    - Đơn vị hiển thị theo từng loại setpoint.

    Input:
    - actions: dict
        {
            "FurnaceSpeedSP": float,
            "CoalSP": float,
            "FanSP": float
        }

    Output:
    - str hoặc None
        Chuỗi mô tả hành động khuyến nghị.
        None nếu không phải mốc 5 phút hoặc không có hành động.
    """
    minute = datetime.now(timezone.utc).minute
    if minute % 5 != 0:
        return
        
    descriptions = {
        "FurnaceSpeedSP": "Tốc độ quay của lò",
        "CoalSP": "Tốc độ cấp than",
        "FanSP": "Tốc độ quạt"
    }

    text_parts = []
    for key, value in actions.items():
        if value > 0:
            desc = descriptions.get(key, key)
            if key == "FurnaceSpeedSP":
                text_parts.append(f"{desc}: Tăng {value} RPM")
            elif key == "CoalSP":
                text_parts.append(f"{desc}: Tăng {value} tấn/h")
            elif key == "FanSP":
                text_parts.append(f"{desc}: Tăng {value} %")
        if value < 0:
            desc = descriptions.get(key, key)
            if key == "FurnaceSpeedSP":
                text_parts.append(f"{desc}: Giảm {abs(value)} RPM")
            elif key == "CoalSP":
                text_parts.append(f"{desc}: Giảm {abs(value)} tấn/h")
            elif key == "FanSP":
                text_parts.append(f"{desc}: Giảm {abs(value)} %")

    return ", ".join(text_parts)

def log_issue_to_dynamodb(table, issue_type: str, issues: list):
    """
    Ghi danh sách ISSUE / WARNING / KHUYẾN NGHỊ vào DynamoDB.

    Logic tổng quát:
    - Chỉ ghi log tại các mốc thời gian bội số của 5 phút.
    - Với mỗi issue:
        + Chuẩn hóa dữ liệu theo từng issue_type
        + Kiểm tra trùng lặp (duplicate) trước khi ghi
        + Ghi vào DynamoDB nếu chưa tồn tại

    Partition Key (PK):
    - issue_type

    Sort Key (SK):
    - datetime_uuid = <timestamp>_<uuid>

    Input:
    - table:
        DynamoDB Table object
    - issue_type: str
        Một trong: "SỰ CỐ", "NHẮC NHỞ", "KHUYẾN NGHỊ"
    - issues: list
        Danh sách dict (output từ rule engine / ML model)

    Output:
    - None
    """
    if not issues:
        return
    current_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:00")
    
    minute = datetime.now(timezone.utc).minute
    if minute % 5 != 0:
        return

    for item in issues:
        # print(f"Logging {issue_type}: {item}")

        # Sort Key = datetime + uuid để đảm bảo không trùng
        datetime_uuid = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:00") + f"_{uuid.uuid4()}"
        if issue_type == "NHẮC NHỞ":
            log_item = {
                "issue_type": issue_type,
                "datetime_uuid": datetime_uuid,
                "logic": to_serializable(item.get("logic")),
                "description": to_serializable(item.get("description")),
                "target": to_serializable(item.get("target")),
                "timestamp": (datetime.now(timezone.utc) + timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:00")
            }
        elif issue_type == "SỰ CỐ":
            log_item = {
                "issue_type": issue_type,
                "datetime_uuid": datetime_uuid,
                "logic": to_serializable(item.get("Rules")),
                "description": to_serializable(item.get("Warning")),
                "target": to_serializable(item.get("IssueType")),
                "timestamp": (datetime.now(timezone.utc) + timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:00")
            }
        elif issue_type == "KHUYẾN NGHỊ":
            if not isinstance(item, dict):
                continue
            log_item = {
                "issue_type": issue_type,
                "datetime_uuid": datetime_uuid,
                "logic": None,
                "description": recommended_actions_to_text(item),
                "target": "Thông số điều khiển",
                "timestamp": (datetime.now(timezone.utc) + timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:00")
            }
        try:
            response = table.scan(
                FilterExpression=Attr("issue_type").eq(issue_type) &
                                Attr("timestamp").eq(log_item["timestamp"]) &
                                Attr("logic").eq(log_item.get("logic")) &
                                Attr("target").eq(log_item.get("target"))
            )
            if response.get("Items"):
                # print(f"⚠️ Duplicate {issue_type} at {current_ts}, skipping log.")
                continue
            # print(f"Logging {issue_type}: {log_item}")
            table.put_item(Item=log_item)
            # print(f"✅ Logged {issue_type}: {log_item['description']}")
        except Exception as e:
            print(f"❌ Error logging {issue_type} to DynamoDB:", e)

def to_datetime(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    return None

def Playback_View_function(table, input):
    """
    Truy vấn dữ liệu playback từ DynamoDB theo:
        - issue_type
        - khoảng thời gian (start_date, end_date)
        - target (nếu có)
    Sau đó sort và phân trang kết quả trả về.
    """
    filter_model = input.filter
    pagination = max(input.pagination, 1)
    page_size = max(input.page_size, 1)

    logs = []

    # Parse start_date và end_date từ payload
    start_dt = to_datetime(filter_model.start_date) or datetime(2025, 1, 1)
    end_dt = to_datetime(filter_model.end_date) or datetime.utcnow()

    # Chuyển về string tương thích timestamp trong DynamoDB
    start_ts = start_dt.strftime("%Y-%m-%d %H:%M:%S")
    end_ts = end_dt.strftime("%Y-%m-%d %H:%M:%S")

    # Nếu filter issue_type rỗng, mặc định lấy tất cả
    issue_types = filter_model.issue_type or ["NHẮC NHỞ", "SỰ CỐ", "KHUYẾN NGHỊ"]
    start_uuid = start_ts + "_00000000"  # ghép phần uuid nhỏ nhất
    end_uuid   = end_ts + "_zzzzzzzz"    # ghép phần uuid lớn nhất

    for itype in issue_types:
        try:
            # print(f"Querying {itype} from {start_ts} to {end_ts}...")
            # response = table.scan(
            #     FilterExpression=Attr("issue_type").eq(itype) &
            #                     Attr("timestamp").between(start_ts, end_ts)
            # )
            response = table.query(
                KeyConditionExpression=Key("issue_type").eq(itype) &
                                    Key("datetime_uuid").between(start_uuid, end_uuid)
            )
            items = response.get("Items", [])
            # print(f"Found {len(items)} items for {itype}.")

            if filter_model.target:
                items = [i for i in items if i.get("target") in filter_model.target]

            logs.extend(items)

        except Exception as e:
            print(f"❌ Error querying {itype}:", e)

    logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    start_index = (pagination - 1) * page_size
    end_index = start_index + page_size
    page_items = logs[start_index:end_index]

    return {"data": page_items}
