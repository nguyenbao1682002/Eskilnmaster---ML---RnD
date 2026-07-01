import pandas as pd
from typing import Optional, List, Dict
from sklearn.linear_model import LinearRegression

def get_future_trend(data: pd.DataFrame, future_data_points = 15, features_to_analyze: Optional[List[str]] = None):
    """
    Dự đoán (tạm thời) xu hướng tương lai bằng cách giữ nguyên giá trị hiện tại.
    Lưu ý:
    - Hiện tại CHƯA sử dụng mô hình dự đoán.
    - Giá trị tương lai được tạo bằng cách lặp lại giá trị mới nhất.
    - Hàm này đóng vai trò placeholder để dễ thay thế bằng model forecasting sau này.
    Input:
    - data: pandas DataFrame
        Dữ liệu lịch sử (row đầu tiên là mới nhất).
    - future_data_points: int
        Số điểm dữ liệu tương lai cần sinh (ví dụ: 15 phút).
    - features_to_analyze: List[str]
        Danh sách các feature cần dự đoán.
    Output:
    - dict gồm:
        + data: List[dict] – dữ liệu tương lai theo từng mốc
        + trend_info: None (chưa có model)
    """
    # Initialize the list for future trend data
    future_trend_data = []

    if data.empty:
        return Trend(data=[], trend_info="No data available")

    # Get the most recent data point for each feature
    latest_data = data.iloc[0]

    # Replicate the latest data for the next 5 minutes
    for _ in range(future_data_points):
        future_point = {feature: latest_data[feature] for feature in features_to_analyze}
        future_trend_data.append(future_point)
    
    # print("Future trend data:", future_trend_data)

    # Here, we're not providing trend_info as we don't have a predictive model yet
    # If needed, you can add a placeholder for trend_info or commit it
    Trend = {
        "data": future_trend_data,
        "trend_info": None
    }
    return Trend

def get_past_trend(data, features_to_analyze, stability_threshold=1):
    """
    Phân tích xu hướng QUÁ KHỨ của các feature bằng Linear Regression.
    Logic:
    - Tạo trục thời gian giả (TimeIndex) để đảm bảo thứ tự thời gian.
    - Với mỗi feature:
        + Fit mô hình Linear Regression theo thời gian.
        + Lấy slope (độ dốc) của đường hồi quy.
        + Phân loại xu hướng: Increasing / Decreasing / Stable.
    - Trả về:
        + Dữ liệu đường xu hướng (trend line) theo thời gian.
        + Thông tin xu hướng cho từng feature.
    Input:
    - data: pandas DataFrame
        Dữ liệu lịch sử (đã được sắp theo thời gian).
    - features_to_analyze: List[str]
        Danh sách feature cần phân tích xu hướng.
    - stability_threshold: float
        Ngưỡng slope để coi là Stable.
    Output:
    - dict:
        {
            "data": List[dict],       # Dữ liệu đường xu hướng
            "trend_info": Dict[str]   # Phân loại xu hướng
        }
    """
    # Initialize
    past_trend_data = []
    trend_info = {}
    # Adding a TimeIndex column for chronological order
    data['TimeIndex'] = range(len(data))

    # Analyze trend for each feature
    for feature in features_to_analyze:
        X = data['TimeIndex'].values.reshape(-1, 1)
        y = data[feature].dropna()

        if len(X) < 2 or y.empty:
            trend_info[feature] = "Not enough data"
            continue

        # Fit the Linear Regression model
        model = LinearRegression()
        model.fit(X, y)

        # Predict the trend line for the last points
        trend_line = model.predict(X)

        # Get the slope
        slope = model.coef_[0]

        # Classify the trend based on the slope
        trend_type = "Stable" if abs(slope) <= stability_threshold else "Increasing" if slope > 0 else "Decreasing"
        
        if feature == "x4G1GA01XAC01_O2_1min":
            trend_info["GA01_Oxi"] = trend_type
        elif feature == "x4G1GA01XAC01_NO_1min":
            trend_info["Nox"] = trend_type
        else:
            trend_info[feature] = trend_type

        # Add the predicted points to the list
        for i in range(len(data)):
            # Create the holder to contain the value at time i-th if not created yet
            point = past_trend_data[i] if i < len(past_trend_data) else {}
            # Assign value at that time i-th for the feature
            if feature == "x4G1GA01XAC01_O2_1min":
                point["4G1GA01XAC01_O2_1min"] = trend_line[i]
            elif feature == "x4G1GA01XAC01_NO_1min":
                point["4G1GA01XAC01_NO_1min"] = trend_line[i]
            else:
                point[feature] = trend_line[i]
            if i >= len(past_trend_data):
                past_trend_data.append(point)
    Trend = {
        "data": past_trend_data,
        "trend_info": trend_info
    }
    return Trend

# Using the eskiln_recommendation_setpoints pre-trained model
def get_recommended_actions(recommendation_model, input) -> Dict[str, float]: 
    """
    Sinh khuyến nghị điều chỉnh setpoint từ mô hình ML.

    Logic:
    - Nhận input trạng thái hiện tại của hệ thống.
    - Dùng recommendation_model để dự đoán các giá trị điều chỉnh.
    - Làm tròn kết quả theo chuẩn vận hành.
    - Trả về dict các hành động khuyến nghị.

    Input:
    - recommendation_model:
        Mô hình ML đã được train (multi-output regression).
    - input: np.ndarray
        Dữ liệu đầu vào shape (1, n_features).

    Output:
    - Dict[str, float]:
        {
            "FurnaceSpeedSP": float,
            "CoalSP": float,
            "FanSP": float
        }
    """
    output = recommendation_model.predict(input)[0]
    recommended_actions = {"FurnaceSpeedSP": round(output[0], 2), "CoalSP" : round(output[1], 1), "FanSP": round(output[2], 1)}
    return recommended_actions

# Using the eskiln_status_classification_model pre-trained model
def get_status(status_model, input):
        """
    Phân loại trạng thái hiện tại của hệ thống bằng mô hình ML.
    Logic:
    - Sử dụng status_model để dự đoán trạng thái.
    - Model trả về nhãn số (ví dụ: 0 / 1).
    - Mapping nhãn → trạng thái nghiệp vụ:
        + 0 → Stable
        + khác 0 → Unstable
    Input:
    - status_model:
        Mô hình phân loại đã được train.
    - input: np.ndarray
        Dữ liệu đầu vào shape (1, n_features).
    Output:
    - str:
        "Stable" hoặc "Unstable"
    """
    status_output = status_model.predict(input)[0]
    if status_output == 0:
        return "Stable"
    else:
        return "Unstable"