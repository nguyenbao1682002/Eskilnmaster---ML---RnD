#!/bin/bash

if [ -f ./logs/uvicorn.pid ]; then
    kill -9 $(cat ./logs/uvicorn.pid)
    rm ./logs/uvicorn.pid
    echo "Đã dừng FastAPI."
else
    echo "Không tìm thấy PID. FastAPI có thể chưa chạy."
fi

deactivate