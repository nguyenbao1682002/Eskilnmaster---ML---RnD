#!/bin/bash

source env/bin/activate
pip install -r requirements.txt

# Chạy FastAPI app ở chế độ nền với nohup
nohup uvicorn src.main:app --host 0.0.0.0 --port 8082 &
echo $! > ./logs/uvicorn.pid
echo "FastAPI đang chạy ở cổng 8082. PID: $(cat ./logs/uvicorn.pid)"
echo "Đang kiểm tra"
pytest
echo "Kiểm tra hoàn tất"