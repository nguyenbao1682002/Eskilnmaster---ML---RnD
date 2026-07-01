#!/bin/bash

source env/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --host 0.0.0.0 --port 8082 --reload