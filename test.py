import requests

job_id = "2052755"
# Tạo URL mồi (cố tình viết sai phần đầu, chỉ cần đúng ID ở cuối)
dummy_url = f"https://www.vietnamworks.com/job-{job_id}-jv"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

print(f"Đang gửi request tới URL mồi:\n-> {dummy_url}\n")

# Gửi request
response = requests.get(dummy_url, headers=headers)

# In kết quả
print(f"Status Code : {response.status_code}")
print(f"URL thực tế : {response.url}")