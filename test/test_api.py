import sys
import os
from fastapi.testclient import TestClient
import pandas as pd
import requests
import json
import random
from load_dotenv import load_dotenv
from main import *

load_dotenv()
LOCAL_BASE_URL = os.getenv("LOCAL_BASE_URL")
PRODUCTION_BASE_URL= os.getenv("PRODUCTION_BASE_URL")
client = TestClient(app)
TESTING_URL = LOCAL_BASE_URL

with open(r"./json/test.json", "r") as file:
    test_data = json.load(file)

def test_swagger():
    response = client.get("/docs")
    assert response.status_code == 200

def test_API_success():
    response_API_find_issues = client.post("/find_issues", json=test_data)
    response_API_classify_status_predict_trend = client.post("/classify_status_predict_trend", json=test_data)
    assert response_API_find_issues.status_code == 200
    assert response_API_classify_status_predict_trend.status_code == 200

def test_get_status():
    data = [[1500, 300, 1000, 5, 20, 3, 58, 700, 3, 865, 5, 983]]
    result = get_status(status_model, data)
    assert result == "Stable"
    
def test_API_classify_status_predict_trend():
    response = client.post("/classify_status_predict_trend", json=test_data)
    assert response.status_code == 200
    assert "status" in response.json()
    assert "past_trend" in response.json()
    assert "future_trend" in response.json()
    
def test_API_find_issues():
    response = client.post("/find_issues", json=test_data)
    if response.json() != "No incidents":
        assert response.status_code == 200
        assert "issues" in response.json()
        assert "warnings" in response.json()