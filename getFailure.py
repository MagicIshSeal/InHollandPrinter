import requests
# TODO: Add automatic discovery of ML API and Image Server URLs
ML_API = "http://localhost:3333/p/"
IMAGE_SERVER = "http://10.207.206.135:8080"

def check_spaghetti(filename):
    image_url = f"{IMAGE_SERVER}/{filename}"
    
    response = requests.get(ML_API, params={"img": image_url})
    data = response.json()
    
    detections = data.get("detections", [])
    has_spaghetti = len(detections) > 0
    
    print(f"Detections: {detections}")
    print(f"Spaghetti detected: {has_spaghetti}")
    
    return has_spaghetti