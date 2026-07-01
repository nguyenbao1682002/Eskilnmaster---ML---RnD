import pickle
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
import joblib
import uuid
import warnings 
import pytz
import os
from fastapi.middleware.cors import CORSMiddleware
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from API_find_issues import check_incident, check_reminder
from API_classify_status_predict_trend import get_future_trend, get_past_trend, get_recommended_actions, get_status
from worklogs import log_issue_to_dynamodb, Playback_View_function
import boto3
from datetime import datetime

dynamodb = boto3.resource("dynamodb", region_name="ap-southeast-1")
log_table = dynamodb.Table("ESKilnMaster-playback")
# Suppress specific sklearn warnings
warnings.filterwarnings("ignore", category=UserWarning, module="sklearn.base")

## Config AI
# Models
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
status_model = pickle.load(open('./models/eskiln_status_classification_model.pkl', 'rb'))
recommendation_model = joblib.load(open('./models/eskiln_recommendation_setpoints.joblib', 'rb'))
# Future data points to predict
future_data_points = 15
# Threshold for trend classification
stability_threshold = 1  

features_to_analyze = [
    "KilnInletTemp", "KilnDriAmp", "Pyrometer", "x4G1GA01XAC01_O2_1min", "x4G1GA01XAC01_NO_1min"
]

selected_features = [
    "Pyrometer", "KilnDriAmp", "KilnInletTemp", "GA02_Oxi", "GA01_Oxi", 
    "GA03_Oxi", "HeatReplaceRatio", "TotalHeatConsumption", "FurnaceSpeed", "TowerOilTemp", 
    "AvgBZT", "RecHeadTemp"
]

tag_reminder = [
    # Tụt bin trung tâm, kiểm tra hệ thống rút liệu homosilo
    "x4C1CD01XCC01_Binfilling",
    # Kiểm tra, vệ sinh trám mái úp-đầu lò
    # Giảm nhiệt tháp-nguy cơ bám dính
    "x4G1PS02PGP01_T8201",
    "Temperature_C2",
    # Giảm nhiệt tháp- nguy cơ bám dính
    # Đo nhiệt báo sai, kiểm tra
    "x4G1PS01GPJ01_T8201I",
    # Cẩn thận CO hệ thống
    "x4G1GA01XAC01_CO",
    "x4G1GA02XAC01_A0901",
    "x4G1GA03XAC01_A0901",
    "x4G1GA04XAC01_A0901",
    # Idfan rung cao, cần xử lý
    "x4G1FN01MMS01_T9601",
    # Đo nhiệt độ đầu lò sai
    "KilnInletTemp",
    # Vệ sinh trám đầu lò
    "x4G1KJ01JST00_B5001",
    # Phân tích khí GA01 không chính xác
    "GA01_Oxi",
    # Tải lò cao, kiểm tra tình trạng động cơ chính lò
    "KilnDriAmp",
    # Điều chỉnh nâng CaOf, nguy cơ bám trám lò
    # CaOf cao, chú ý chuyển silo phụ
    "CaO_f",
    # Lò thiếu gió
    "S03_hot_meal",
    # Nhiệt búa cooler cao
    "x4R1RR01EXD01_T8102",
    # Nhiệt khí thải cooler thấp
    "x4S1GP02JST00_T8201",
    # Nhiệt clinker cao, điều chỉnh giảm nhiệt clinker
    # Nhiệt clinker thấp, điều chỉnh giảm quạt cooler
    "x4T1AY01JST00_B8702",
    # Giảm tốc độ lò nhanh, quá tải cooler-búa
    "x4R1FN01TVJ01_B5101_INFSC",
    # Vệ sinh lọc nước làm mát thủy lực cooler
    "x4R1GQ01HYS01_T8101",
    # Kiểm tra ống hút lọc bụi, kiểm tra van màn lọc bụi
    "x4C1BF01FNJ01_M2001_I",
    # Chú ý quá tải cooler, giảm sâu tốc độ lò
    "Grate_Hyd_Pressure",
    # Oxi các GA thấp, nguy cơ thiếu gió hệ thống
    "x4G1GA02XAC01_O2_1min",
    "x4G1GA03XAC01_O2_1min",
    "x4G1GA04XAC01_O2",
    # Kiểm tra nước làm mát, hệ thống tự lựa
    "x4K1KP01RST01_T8101",
    "x4K1KP01RST01_T8102",
    "x4K1KP01RST01_T8103",
    "x4K1KP01RST01_T8104",
    "x4K1KP01RST02_T8101",
    "x4K1KP01RST02_T8102",
    "x4K1KP01RST02_T8103",
    "x4K1KP01RST02_T8104",
    # Kiểm tra lại ghi tĩnh của 4R1FC02TVJ01B5101_INFS
    "x4R1FC02TVJ01B5101_INFS",
    # Kiểm tra lại ghi tĩnh của 4R1FC06TVJ01B5101_INFS
    "x4R1FC06TVJ01B5101_INFS"
]

tag_incident = [
    "Fan_4S1",
    "Kilnhood_Pressure",
    "Thermal_Exhaust",
    "Fan_4E1_Valve_Open_Close_Degree",
    "P_4E1GP1JST01_Pressure",
    "U_4C1CD01XCC01_Feedrate",
    "Valve_Open_Degree",
    "U_4C1BE02DRV01_02_IE",
    "Actual_Feed_Rate_PC",
    "Coal_Blower_Pressure_01",
    "Actual_Feed_Rate_SZ",
    "Coal_Blower_Pressure_02",
    "Fabric_Scale",
    "Temperature_C1",
    "Temperature_C2",
    "Temperature_C3",
    "KilnDriAmp",
    "Hydraulic_Pressure"
]

# Pydantic models for request validation
class StatusRequest(BaseModel):
    ActualFuel: Optional[float] = 0.0
    ActualFuelSP: Optional[float] = 0.0   
    Actual_Feed_Rate_PC: Optional[float] = 0.0 
    Actual_Feed_Rate_SZ: Optional[float] = 0.0
    AlternativeCoalSP: Optional[float] = 0.0
    AvgBZT: Optional[float] = 0.0
    CaO_f: Optional[float] = 0.0
    CoalSP: Optional[float] = 0.0
    Coal_Blower_Pressure_01: Optional[float] = 0.0    
    Coal_Blower_Pressure_02: Optional[float] = 0.0
    Conveyor_Flow_Rate_01: Optional[float] = 0.0
    Conveyor_Flow_Rate_02: Optional[float] = 0.0
    FanSP: Optional[float] = 0.0
    Fan_4S1: Optional[float] = 0.0
    Fan_4E1_Valve_Open_Close_Degree: Optional[float] = 0.0
    Fabric_Scale: Optional[float] = 0.0
    FurnaceSpeed: Optional[float] = 0.0
    FurnaceSpeedSP: Optional[float] = 0.0
    GA01_Oxi: Optional[float] = 0.0
    GA02_Oxi: Optional[float] = 0.0
    GA03_Oxi: Optional[float] = 0.0    
    HeatReplaceRatio: Optional[float] = 0.0
    Hydraulic_Pressure: Optional[float] = 0.0
    KilnDriAmp: Optional[float] = 0.0
    Kilnhood_Pressure: Optional[float] = 0.0
    KilnInletTemp: Optional[float] = 0.0
    MaterialTowerHeat: Optional[float] = 0.0
    Nox: Optional[float] = 0.0
    P_4E1GP1JST01_Pressure: Optional[float] = Field(0.0, alias = "4E1GP1JST01_Pressure")
    Pyrometer: Optional[float] = 0.0
    RecHeadTemp: Optional[float] = 0.0
    S03_hot_meal: Optional[float] = 0.0
    Temperature_C1: Optional[float] = 0.0
    Temperature_C2: Optional[float] = 0.0
    Temperature_C3: Optional[float] = 0.0
    Thermal_Exhaust: Optional[float] = 0.0
    TotalHeatConsumption: Optional[float] = 0.0
    TowerOilTemp: Optional[float] = 0.0
    U_4C1BE02DRV01_02_IE: Optional[float] = Field(0.0, alias = "4C1BE02DRV01_02_IE")
    U_4C1CD01XCC01_Feedrate: Optional[float] = Field(0.0, alias = "4C1CD01XCC01_Feedrate")
    Valve_Open_Degree: Optional[float] = 0.0
    x4C1CD01XCC01_Binfilling: Optional[float] = Field(0.0, alias = "4C1CD01XCC01_Binfilling")
    x4G1PS02PGP01_T8201: Optional[float] = Field(0.0, alias = "4G1PS02PGP01_T8201")
    x4G1PS02PGP02_T8201: Optional[float] = Field(0.0, alias = "4G1PS02PGP02_T8201")
    x4G1PS01GPJ01_T8201I: Optional[float] = Field(0.0, alias = "4G1PS01GPJ01_T8201I")
    x4G1GA01XAC01_CO: Optional[float] = Field(0.0, alias = "4G1GA01XAC01_CO")
    x4G1GA02XAC01_A0901: Optional[float] = Field(0.0, alias = "4G1GA02XAC01_A0901")
    x4G1GA03XAC01_A0901: Optional[float] = Field(0.0, alias = "4G1GA03XAC01_A0901")
    x4G1GA04XAC01_A0901: Optional[float] = Field(0.0, alias = "4G1GA04XAC01_A0901")
    x4G1FN01MMS01_T9601: Optional[float] = Field(0.0, alias = "4G1FN01MMS01_T9601")
    x4G1KJ01JST00_B5001: Optional[float] = Field(0.0, alias = "4G1KJ01JST00_B5001")
    x4R1RR01EXD01_T8102: Optional[float] = Field(0.0, alias = "4R1RR01EXD01_T8102")
    x4S1GP02JST00_T8201: Optional[float] = Field(0.0, alias = "4S1GP02JST00_T8201")
    x4T1AY01JST00_B8702: Optional[float] = Field(0.0, alias = "4T1AY01JST00_B8702")
    x4R1FN01TVJ01_B5101_INFSC: Optional[float] = Field(0.0, alias = "4R1FN01TVJ01_B5101_INFSC")
    x4R1GQ01HYS01_T8101: Optional[float] = Field(0.0, alias = "4R1GQ01HYS01_T8101")
    x4G1GA03XAC01_O2_1min: Optional[float] = Field(0.0, alias = "4G1GA03XAC01_O2_1min")
    x4G1GA02XAC01_O2_1min: Optional[float] = Field(0.0, alias = "4G1GA02XAC01_O2_1min")
    x4G1GA01XAC01_O2_1min: Optional[float] = Field(0.0, alias = "4G1GA01XAC01_O2_1min")
    x4G1GA01XAC01_NO_1min: Optional[float] = Field(0.0, alias = "4G1GA01XAC01_NO_1min")
    x4C1BF01FNJ01_M2001_I: Optional[float] = Field(0.0, alias = "4C1BF01FNJ01_M2001_I")
    Grate_Hyd_Pressure: Optional[float] = Field(0.0, alias = "Grate_Hyd_Pressure")
    x4G1GA04XAC01_O2: Optional[float] = Field(0.0, alias = "4G1GA04XAC01_O2")
    x4K1KP01RST01_T8101: Optional[float] = Field(0.0, alias = "4K1KP01RST01_T8101")
    x4K1KP01RST01_T8102: Optional[float] = Field(0.0, alias = "4K1KP01RST01_T8102")
    x4K1KP01RST01_T8103: Optional[float] = Field(0.0, alias = "4K1KP01RST01_T8103")
    x4K1KP01RST01_T8104: Optional[float] = Field(0.0, alias = "4K1KP01RST01_T8104")
    x4K1KP01RST02_T8101: Optional[float] = Field(0.0, alias = "4K1KP01RST02_T8101")
    x4K1KP01RST02_T8102: Optional[float] = Field(0.0, alias = "4K1KP01RST02_T8102")
    x4K1KP01RST02_T8103: Optional[float] = Field(0.0, alias = "4K1KP01RST02_T8103")
    x4K1KP01RST02_T8104: Optional[float] = Field(0.0, alias = "4K1KP01RST02_T8104")
    x4R1FC02TVJ01B5101_INFS: Optional[float] = Field(0.0, alias = "4R1FC02TVJ01B5101_INFS")
    x4R1FC06TVJ01B5101_INFS: Optional[float] = Field(0.0, alias = "4R1FC06TVJ01B5101_INFS")
    x4E1GP01JST00_T8202: Optional[float] = Field(0.0, alias = "4E1GP01JST00_T8202")

class Trend(BaseModel):
    data: List[Dict[str, float]]
    trend_info: Optional[Dict[str, str]] = None

class StatusTrendResponse(BaseModel):
    status: str
    past_trend: Trend
    future_trend: Trend
    recommendation: Optional[Dict[str, float]] = None

## API /classify_status_predict_trend
@app.post("/classify_status_predict_trend", tags=["ML"])
async def classify_status_predict_trend(request: List[Optional[StatusRequest]]):
    """
    API phân loại trạng thái hệ thống + phân tích xu hướng quá khứ & dự đoán tương lai.
    Chức năng chính:
        - Làm sạch dữ liệu đầu vào (xử lý các phần tử None).
        - Phân tích xu hướng quá khứ (past trend).
        - Phân loại trạng thái hiện tại (status classification).
        - Sinh khuyến nghị điều chỉnh (recommendation).
        - Dự đoán xu hướng trong tương lai (future trend).
    Input:
    - request: List[Optional[StatusRequest]]
        Danh sách trạng thái theo thời gian (có thể chứa None).
    Output:
    - StatusTrendResponse gồm:
        + status: trạng thái hiện tại của hệ thống
        + past_trend: xu hướng trong quá khứ
        + future_trend: xu hướng dự đoán
        + recommendation: khuyến nghị điều chỉnh
    """
    # print("len request:", len(request))
    # --- 1. Xử lý các phần tử None trong request ---
    # Nếu phần tử hiện tại là None:
    # - Ưu tiên lấy giá trị hợp lệ phía trước
    # - Nếu không có thì lấy phía sau
    for i in range(len(request)):
        if request[i] is None:
            if i > 0 and request[i - 1] is not None:
                request[i] = request[i - 1]
            elif i < len(request) - 1 and request[i + 1] is not None:
                request[i] = request[i + 1]
    # --- 2. Loại bỏ hoàn toàn các phần tử None còn sót lại ---
    request = [item for item in request if item is not None]
    # Kiểm tra request rỗng
    if not request:
        raise HTTPException(status_code=400, detail="Empty request list.")
    # --- 3. Chuyển dữ liệu sang pandas DataFrame ---
    # model_dump(): chuyển Pydantic model → dict
    data_df = pd.DataFrame([item.model_dump() for item in request])
    # print("data_df", data_df)

    # --- 4. Phân tích xu hướng quá khứ ---
    # Đảo ngược DataFrame để dữ liệu cũ nhất → mới nhất
    reversed_df = data_df.iloc[::-1].reset_index(drop=True)
    # Lấy xu hướng trong quá khứ (ví dụ: 1 giờ trước)
    past_trend = get_past_trend(reversed_df, features_to_analyze, stability_threshold)
    # Kiểm tra xem tất cả các feature đều ở trạng thái Stable hay không
    all_stable = all(value == 'Stable' for value in past_trend["trend_info"].values())
    # --- 5. Phân loại trạng thái hiện tại ---
    # Lấy bản ghi mới nhất (row đầu tiên)
    df_lastest = data_df[selected_features].iloc[0]
    # Chuẩn bị input cho model
    status_input = df_lastest.values.reshape(1, -1)
    # Dự đoán trạng thái hệ thống
    status = get_status(status_model, status_input)
    # --- 6. Sinh khuyến nghị ---
    # Nếu hệ thống ổn định → không cần điều chỉnh
    if all_stable:
        recommended_actions = {"FurnaceSpeedSP": 0, "CoalSP" : 0, "FanSP": 0}
    else:
        recommended_actions = get_recommended_actions(recommendation_model, status_input)  
        log_issue_to_dynamodb(log_table, "KHUYẾN NGHỊ", [recommended_actions])
    # --- 7. Dự đoán xu hướng tương lai ---
    # Ví dụ: dự đoán ${future_data_points} phút tiếp theo
    future_trend = get_future_trend(data_df, future_data_points, features_to_analyze)
    # --- 8. Gom toàn bộ kết quả trả về ---
    response = StatusTrendResponse(
        status = status,
        past_trend = past_trend,
        future_trend = future_trend,
        recommendation = recommended_actions
    )
    # print("Response:\n", response.json())
    return response

## API /find_issues
@app.post("/find_issues", tags=["ML"])
async def find_issues(request: List[Optional[StatusRequest]]):
    """
    API dùng để phát hiện SỰ CỐ và NHẮC NHỞ từ danh sách trạng thái đầu vào.
        - Nhận vào một list các StatusRequest (có thể chứa None).
        - Tự động fill giá trị None bằng phần tử hợp lệ gần nhất (trước hoặc sau).
        - Chuyển dữ liệu sang DataFrame để phục vụ xử lý ML/rule-based.
        - Kiểm tra:
            + Incident (Sự cố)
            + Reminder (Nhắc nhở)
        - Ghi log các vấn đề phát hiện được vào DynamoDB.
        - Trả về danh sách issues và warnings.
    """
    # --- 1. Xử lý các phần tử None trong request ---
    # Logic:
    # - Nếu phần tử hiện tại là None
    #   + Ưu tiên lấy giá trị phía trước (i-1) nếu tồn tại
    #   + Nếu không có thì lấy giá trị phía sau (i+1)
    for i in range(len(request)):
        if request[i] is None:
            if i > 0 and request[i - 1] is not None:
                request[i] = request[i - 1]
            elif i < len(request) - 1 and request[i + 1] is not None:
                request[i] = request[i + 1]
    # --- 2. Kiểm tra request rỗng ---
    if not request:
        raise HTTPException(status_code=400, detail="Empty request list.")
    # --- 3. Chuyển list StatusRequest sang pandas DataFrame ---
    data_df = pd.DataFrame([item.model_dump() for item in request])
    # --- 4. Kiểm tra SỰ CỐ (Incident) ---
    df_incident = data_df[tag_incident]
    # print("df_incidents:\n", df_incident)
    response_incident = check_incident(df_incident)
    # --- 5. Kiểm tra NHẮC NHỞ (Reminder) ---
    df_reminder = data_df[tag_reminder]
    # print("Here:\n", data_df[tag_reminder])
    response_reminder = check_reminder(df_reminder)
    # --- 6. Ghi log kết quả vào DynamoDB (nếu có) ---
    if response_reminder:
        log_issue_to_dynamodb(log_table, "NHẮC NHỞ", response_reminder)
    if response_incident:
        log_issue_to_dynamodb(log_table, "SỰ CỐ", response_incident)
    # --- 7. Trả kết quả về cho client ---
    output = {
        "issues": response_incident,
        "warnings": response_reminder
    }
    return output

class FilterModel(BaseModel):
    issue_type: Optional[List[str]] = []
    target: Optional[List[str]] = []
    start_date: Optional[datetime] = "2025-01-01T00:00:00.000Z"
    end_date: Optional[datetime] = "2026-01-01T00:00:00.000Z"
    @validator("start_date", "end_date", pre=True)
    def parse_datetime(cls, value):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        # thử parse theo định dạng FE gửi
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            # fallback: ISO 8601
            return datetime.fromisoformat(value.replace("Z", "+00:00"))

class Playback_View(BaseModel):
    filter: FilterModel
    pagination: int = Field(default=1, example=1)
    page_size: int = Field(default=20, example=20)

@app.post("/Playback", tags=["Playback"])
async def Playback_View_api(input: Playback_View):
    """
    API Playback dùng để truy vấn và phát lại dữ liệu lịch sử.

    Chức năng:
        - Nhận input dạng Playback_View (tham số truy vấn playback).
        - Gọi hàm xử lý chính để lấy dữ liệu từ DynamoDB (log_table).
        - Trả kết quả playback cho client.

    Xử lý lỗi:
        - Bắt toàn bộ exception và trả về HTTP 500 kèm message lỗi.
    """
    try:
        return Playback_View_function(log_table, input)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))