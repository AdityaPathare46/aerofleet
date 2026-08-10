import requests
try:
    r = requests.post("http://127.0.0.1:8000/api/v1/auth/register", json={"username":"newuser3","password":"password","email":"newuser3@example.com"})
    print(r.status_code, r.text)
except Exception as e:
    print(e)
