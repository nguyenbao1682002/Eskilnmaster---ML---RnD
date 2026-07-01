# By HoanVo
from datetime import datetime
import uuid
import pytz
import pandas as pd

def check_incident(row):
    """
    Kiểm tra và phát hiện SỰ CỐ (Incident) dựa trên các luật (rule-based).
    Logic chung:
    - So sánh sự thay đổi giữa 2 mốc thời gian liên tiếp (index 0 và 1).
    - Nếu thỏa điều kiện bất thường → sinh ra một incident.
    - Mỗi incident gồm:
        + ID
        + Loại sự cố (IssueType)
        + Nội dung cảnh báo
        + Trạng thái xác nhận (Acknowledge)
        + Thời gian phát hiện
        + Nguồn dữ liệu liên quan
        + Luật kiểm tra
    Input:
    - row: pandas DataFrame
        Dữ liệu đã được lọc các cột liên quan tới incident.
        Yêu cầu tối thiểu có 2 dòng dữ liệu (2 mốc thời gian).
    Output:
    - response_incident: List[dict]
        Danh sách các sự cố phát hiện được.
    """
    if row is None or row.empty:
        return ["No data available"]

    response_incident = []
    # print("row:", row)

    conditions = [
        (
            abs(row["Fan_4S1"].iloc[1] - row["Fan_4S1"].iloc[0]) / 2 > 50 and abs(row["Kilnhood_Pressure"].iloc[1] - row["Kilnhood_Pressure"].iloc[0]) <= 0.1 and 0 <= row["Thermal_Exhaust"].iloc[1] - row["Thermal_Exhaust"].iloc[0] <= 0.1,
            1,
            "Đo áp Kilnhood sai", 
            ["Quạt 4S1 täng/giảm 50A trong 30s",
            "Áp Kilnhood không thay đổi",
            "Nhiệt khí thải không thay đổi nhiều hoặc xu hướng giảm"], 
            ["±50A trong vòng 30s",
            "Không đổi hoặc thay đổi ít ±0.1mbar",
            "Không đổi hoặc có xu hướng giảm nhiệt độ"]),

        (
            abs(row["Fan_4E1_Valve_Open_Close_Degree"].iloc[0] - row["Fan_4E1_Valve_Open_Close_Degree"].iloc[1]) > 10 and abs(row["P_4E1GP1JST01_Pressure"].iloc[0] - row["P_4E1GP1JST01_Pressure"].iloc[1]) <= 0.1, 
            2,
            "Đo áp sau IDfan sai", 
            ["Độ mở/đóng van quạt 4E1 tăng 10% trong 30s",
            "Áp 4E1GP1JST01 thay đổi không đáng kể"], 
            ["Độ đóng/mở van ±10% quạtt 4E1",
            "Không đổi hoặc thay đổi ít ±0.1mbar"]),

        (
            abs(row["Valve_Open_Degree"].iloc[0] - row["Valve_Open_Degree"].iloc[1]) > 5 and abs(row["U_4C1BE02DRV01_02_IE"].iloc[0] - row["U_4C1BE02DRV01_02_IE"].iloc[1]) >= 10 and abs(row["U_4C1CD01XCC01_Feedrate"].iloc[0:15].mean() - row["U_4C1CD01XCC01_Feedrate"].iloc[1:16].mean()) < 0.01, 
            3,
            "Cân KF sai", 
            ["Actual kilnfeed không đổi",
            "Độ mở van giảm/tăng 5% trong 30s",
            "Dòng gàu tải giảm/tăng 10A trong 30s"], 
            ["Giá trị trung bình 15 phút không đổi",
            "±5% trong vòng 30s",
            "±10A trong vòng 30s"]),

        (
            abs(row['Actual_Feed_Rate_PC'].iloc[0] - row['Actual_Feed_Rate_PC'].iloc[1]) <= 0.1 and abs(row['Coal_Blower_Pressure_01'].iloc[0] - row['Coal_Blower_Pressure_01'].iloc[1]) / 2 >= 30, 
            4,
            "Cân than PC sai", 
            ["Actual feedrate của cân than không đổi",
            "Áp blower thổi than giảm/tăng 30mbar trong 30s"], 
            ["Không đổi hoặc thay đổi ít ±0.1t/h",
            "±30mbar trong vòng 30s"]),

        (
            abs(row['Actual_Feed_Rate_SZ'].iloc[0] - row['Actual_Feed_Rate_SZ'].iloc[1]) <= 0.1 and abs(row['Coal_Blower_Pressure_02'].iloc[0] - row['Coal_Blower_Pressure_02'].iloc[1]) / 2 >= 30, 
            5,
            "Cân than SZ sai", 
            ["Actual feedrate của cân than không đổi",
            "Áp blower thổi than giảm/tăng 30mbar trong 30s"], 
            ["Không đổi hoặc thay đổi ít ±0.1t/h",
            "±30mbar trong vòng 30s"]),

        (
            abs(row["Fabric_Scale"].iloc[0:15].mean() - row["Fabric_Scale"].iloc[1:16].mean()) < 0.01 and 10 <= (row['Temperature_C1'].iloc[6] - row['Temperature_C1'].iloc[0]) <= 15 and 8 <= (row['Temperature_C2'].iloc[0] - row['Temperature_C2'].iloc[6]) <= 10 and 8 <= (row['Temperature_C3'].iloc[0] - row['Temperature_C3'].iloc[8]) <= 10, 
            6,
            "Chất lượng vải xấu", 
            ["Cân vải không đổi",
            "Nhiệt C1 giảm",
            "Nhiệt C2 tăng",
            "Nhiệt C3 tăng"], 
            ["Giá trị trung bình 15 phút không đổi",
            "–10 —> –15oC trong vòng 5 phút",
            "＋8 —> 10oC trong vòng 5 phút (sau C1)",
            "＋8  —> 10oC trong vòng 7 phút (sau C1)"]),

        (
            abs(row['KilnDriAmp'].iloc[0] - row['KilnDriAmp'].iloc[1]) / 2 >= 30 and (row['Hydraulic_Pressure'].iloc[0] - row['Hydraulic_Pressure'].iloc[1]) / 2 >= 10, 
            7,
            "Lò ra trám", 
            ["Tải lò tăng/giảm đột ngột 30-50A trong vòng 30s",
            "Áp thủy lực ghi tăng 10-15bar trong vòng 30s"], 
            ["±30A trong 30s",
            "＋10bar trong 30s"]),
    ]

    for condition, issuetype, incident, source, rule in conditions:
        if condition:
            schema = {
                "ID": str(uuid.uuid4()),
                "IssueType": issuetype,
                "Warning": incident,
                "Acknowledge": False,
                "Date": datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")),
                "Sources": source,
                "Rules": rule
            }
            response_incident.append(schema)

    # print("response_incident:", response_incident)
    return response_incident

def check_reminder(row):
    """
    Kiểm tra và sinh NHẮC NHỞ (Reminder) dựa trên các luật đơn giản.
    Logic:
    - Đánh giá trạng thái hiện tại (row tại thời điểm mới nhất).
    - Nếu thỏa điều kiện bất thường → sinh ra reminder tương ứng.
    - Reminder không phải sự cố nghiêm trọng mà mang tính cảnh báo / nhắc vận hành.
    Input:
    - row: pandas DataFrame
        Dữ liệu đã được lọc các cột liên quan tới reminder.
        Yêu cầu tối thiểu có 1 dòng dữ liệu.
    Output:
    - response_reminder: List[dict]
        Danh sách các nhắc nhở phát hiện được.
    """
    if row is None or row.empty:
        return ["No data available"]

    response_reminder = []
    print("row:", row)
    conditions = [
        (
            row["x4C1CD01XCC01_Binfilling"].iloc[0] < 60,
            "Tụt bin trung tâm, kiểm tra hệ thống rút liệu homosilo", 
            "Bin trung tâm", 
            "4C1CD01XCC01_Binfilling < 60"),
        (
            abs(row["x4G1PS02PGP01_T8201"].iloc[0] - row["Temperature_C2"].iloc[0]) > 10,
            "Kiểm tra, vệ sinh trám mái úp - đầu lò", 
            "Nhiệt outlet C2", 
            "(4G1PS02PGP01_T8201-4G1PS02PGP02_T8201) > 10"),

        (
            row["x4G1PS02PGP01_T8201"].iloc[0] > 775 or row["Temperature_C2"].iloc[0] > 775,
            "Giảm nhiệt tháp - nguy cơ bám dính Nhiệt outlet C2", 
            "Nhiệt outlet C2", 
            "4G1PS02PGP01_T8201 > 775, 4G1PS02PGP02_T8201 > 775"),

        (
            row["x4G1PS01GPJ01_T8201I"].iloc[0] > 875,
            "Giảm nhiệt tháp - nguy cơ bám dính Nhiệt outlet C1", 
            "Nhiệt outlet C1", 
            "4G1PS01GPJ01_T8201I > 875"),

        (
            row["x4G1PS01GPJ01_T8201I"].iloc[0] < 810,
            "Đo nhiệt báo sai, kiểm tra", 
            "Nhiệt outlet C1", 
            "4G1PS01GPJ01_T8201I < 810"),

        (
            any([
                row["x4G1GA01XAC01_CO"].iloc[0] > 0.25,
                row["x4G1GA02XAC01_A0901"].iloc[0] > 0.25,
                row["x4G1GA03XAC01_A0901"].iloc[0] > 0.25,
                row["x4G1GA04XAC01_A0901"].iloc[0] > 0.25
            ]), 
            "Cẩn thận CO hệ thống", 
            "Hệ thống phân tích khí Ga01,2,3,4", 
            "4G1GA01XAC01_CO > 0.25, 4G1GA02XAC01_A0901 > 0.25, 4G1GA03XAC01_A0901 > 0.25, 4G1GA04XAC01_A0901 > 0.25"),

        (
            row["x4G1FN01MMS01_T9601"].iloc[0] > 4.5,
            "Idfan rung cao, cần xử lý", 
            "Quạt ID", 
            "4G1FN01MMS01_T9601 > 4.5"),

        (
            row["KilnInletTemp"].iloc[0] < 1000,
            "Đo nhiệt độ đầu lò sai", 
            "Đầu lò", 
            "KilnInletTemp < 1000"),

        (
            row["x4G1KJ01JST00_B5001"].iloc[0] < -8,
            "Vệ sinh trám đầu lò", 
            "Đầu lò", 
            "4G1KJ01JST00_B5001 < -8"),

        (
            row["GA01_Oxi"].iloc[0] > 6,
            "Phân tích khí GA01 không chính xác", 
            "Đầu lò", 
            "4G1GA01XAC01_O2 > 6"),

        (
            row["KilnDriAmp"].iloc[0] > 380,
            "Tải lò cao, kiểm tra tình trạng động cơ chính lò", 
            "Lò nung", 
            "4K1KP01DRV01_M2001_EI > 380"),

        (
            row["CaO_f"].iloc[0] < 0.8 and row["CaO_f"].iloc[59] < 0.8,
            "Điều chỉnh nâng CaOf, nguy cơ bám trám lò", 
            "Cooler", 
            "BP_KSCL_CL_CaOf < 0.8"),

        (
            row["CaO_f"].iloc[0] > 2,
            "CaOf cao, chú ý chuyển silo phụ", 
            "Cooler", 
            "BP_KSCL_CL_CaOf > 2"),

        (
            row["S03_hot_meal"].iloc[0] > 1.4,
            "Lò thiếu gió", 
            "Cooler", 
            "BP_KSCL_CL_SO3 > 1.4"),

        (
            row["x4R1RR01EXD01_T8102"].iloc[0] > 85,
            "Nhiệt búa cooler cao", 
            "Cooler", 
            "4R1RR01EXD01_T8102 > 85"),

        (
            row["x4S1GP02JST00_T8201"].iloc[0] < 260,
            "Nhiệt khí thải cooler thấp", 
            "Cooler", 
            "4S1GP02JST00_T8201 < 260"),

        (
            row["x4T1AY01JST00_B8702"].iloc[0] > 120,
            "Nhiệt clinker cao, điều chỉnh giảm nhiệt clinker", 
            "Cooler", 
            "4T1AY01JST00_B8702 > 120"),

        (
            row["x4T1AY01JST00_B8702"].iloc[0] < 100,
            "Nhiệt clinker thấp, điều chỉnh giảm quạt cooler", 
            "Cooler", 
            "4T1AY01JST00_B8702 < 100"),

        (
            (row["x4R1FN01TVJ01_B5101_INFSC"].iloc[1] - row["x4R1FN01TVJ01_B5101_INFSC"].iloc[0]) > 2500,
            "Giảm tốc độ lò nhanh, quá tải cooler-búa", 
            "Cooler", 
            "4R1FN01TVJ01_B5101_INFSC > 0.5"),

        (
            row["x4R1GQ01HYS01_T8101"].iloc[0] > 50.5,
            "Vệ sinh lọc nước làm mát thủy lực cooler", 
            "Cooler", 
            "4R1GQ01HYS01_T8101 > 50.5"),
        
        (
            row["x4C1BF01FNJ01_M2001_I"].iloc[0] < 8,
            "Kiểm tra ống hút lọc bụi, kiểm tra van màn lọc bụi",
            "Rawmeal Silo",
            "4C1BF01FNJ01_M2001_I < 8"),

        (
            row["Grate_Hyd_Pressure"].iloc[0] > 180,
            "Chú ý quá tải cooler, giảm sâu tốc độ lò",
            "Cooler",
            "Grate_Hyd_Pressure > 180"),
        
        (
            row["x4G1GA02XAC01_O2_1min"].iloc[0] < 2 and row["x4G1GA03XAC01_O2_1min"].iloc[0] < 2 and row["x4G1GA04XAC01_O2"].iloc[0] < 2,
            "Oxi các GA thấp, nguy cơ thiếu gió hệ thống",
            "Hệ thống phân tích khí GA02,3,4",
            "4G1GA02XAC01_O2_1min < 2, 4G1GA03XAC01_O2_1min < 2, 4G1GA04XAC01_O2 < 2"),

        (
            row["x4K1KP01RST01_T8101"].iloc[0] > 55 and row["x4K1KP01RST01_T8102"].iloc[0] > 55 and row["x4K1KP01RST01_T8103"].iloc[0] > 55 and row["x4K1KP01RST01_T8104"].iloc[0] > 55
            and row["x4K1KP01RST02_T8101"].iloc[0] > 55 and row["x4K1KP01RST02_T8102"].iloc[0] > 55 and row["x4K1KP01RST02_T8103"].iloc[0] > 55 and row["x4K1KP01RST02_T8104"].iloc[0] > 55,
            "Kiểm tra nước làm mát, hệ thống tự lựa",
            "Lò Nung",
            "4K1KP01RST01_T8101 > 55, 4K1KP01RST01_T8102 > 55, 4K1KP01RST01_T8103 > 55, 4K1KP01RST01_T8104 > 55, 4K1KP01RST02_T8101 > 55, 4K1KP01RST02_T8102 > 55, 4K1KP01RST02_T8103 > 55, 4K1KP01RST02_T8104 > 55"),

        (
            row["x4R1FC02TVJ01B5101_INFS"].iloc[0] < 26500,
            "Kiểm tra lại ghi tĩnh của x4R1FC02TVJ01B5101_INFS",
            "Cooler",
            "4R1FC02TVJ01B5101_INFS < 26500"),
        
        (
            row["x4R1FC06TVJ01B5101_INFS"].iloc[0] < 50000,
            "Kiểm tra lại ghi tĩnh của x4R1FC06TVJ01B5101_INFS",
            "Cooler",
            "4R1FC06TVJ01B5101_INFS < 50000"),
    ]
    # current_date_time = new_time.strftime("%d-%m-%Y - %I:%M %p")

    for condition, reminder, zone, logic in conditions:
        if condition:
            schema = {
                "logic": logic,
                "description": reminder,
                "target": zone,
                "datetime": datetime.now(pytz.timezone("Asia/Ho_Chi_Minh"))
            }
            response_reminder.append(schema)
    # print("response_reminder:", response_reminder)
    return response_reminder