# 🏭ESKilnMaster---BinhPhuoc---ML
## 🔥Connect to EC2
Ask Team Lead or Manager to get the private key file **.pem** and **.ppk** file.  
**Owner: HoanVoESTEC - Võ Lý Hoang Hoan** 
### Method 1: Connect with VSCode
```bash
ssh -i "${KEY_SSH}.pem" ubuntu@ec2-${IP_SSH}.${REGION}.compute.amazonaws.com
```
- _**Example:** ssh -i "privatekey.pem" ubuntu@ec2-1-2-3-4.ap-southeast-1.compute.amazonaws.com_  
### Method 2: Use WinSCP to transfer file from your local machine to EC2
In the **Login** window, set the **File protocol** to **SFTP**.  
Set the **Host name** to your server's DNS name.  
- _**Example:** ec2-1-2-3-4.ap-southeast-1.compute.amazonaws.com_  

Set the **Port number** to 22 (the default for SSH/SFTP).   
Set the **User name** to **ubuntu**, as AWS EC2 instances typically use this as the default user for Ubuntu AMIs.  
In the **Authentication** section, under **Private key file**, browse to and select your **.ppk**.  
Transfer the repo to EC2 for deployment.  
## 🚀 Deployment in EC2
### 🚧Git clone:
```bash
git clone https://github.com/estec-digital/ESKilnMaster---BinhPhuoc---ML.git
cd ESKilnMaster---BinhPhuoc---ML
```
### 🐧Linux:
```bash
virtualenv env 
source .\env\bin\activate
pip install -r requirements.txt
```
### 🪟Windows:
```bash
virtualenv env 
.\env\Scripts\activate
pip install -r requirements.txt
```
## 🏁Start ML service in EC2
### 🌱Develop:
Start service on a specific port, the service running **on terminal** with auto reload.
```bash
uvicorn src.main:app --port ${PORT} --host ${HOST} --reload
```
- _**Example:** uvicorn src.main:app --port 8082 --host 0.0.0.0 --reload_
### 🌴Deploy:
Start service on a specific port, the service running **on background** and no hang up (nohup).
```bash
nohup uvicorn src.main:app --port ${PORT} --host ${HOST} &
```
- _**Example:** nohup uvicorn src.main:app --port 8082 --host 0.0.0.0 &_  

Check if the service is running to see the process id **PID**.
```bash
ps aux | grep ${PORT}
```
- _**Example:** ps aux | grep 8082_  

Kill the ML service process with **PID**.
```bash
kill -9 ${PID}
```
- _**Example:** kill -9 1234_  

## 🦾Swagger APIs from your local machine
To check if the ML service is alive on localhost, go here:  
**http://localhost:8082/docs#/**  
To check if the ML service is alive on EC2, go here:  
**http://54.251.242.155:8082/docs#/**  
## 🏃🏻Run Integration test (ML service APIs)
Check the **TESTING_URL** value in **test_api.py** before running the test where you have virtual environment.
```bash
pytest
```
