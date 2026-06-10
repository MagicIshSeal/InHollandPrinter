import requests
import threading
import http.server
import os
import cv2
import numpy as np
import subprocess
import time

ML_API = "http://localhost:3333/p/"
HOST_IP = "145.81.120.119"
IMAGE_DIR = "/home/mvane/Documents/GitClone/InHollandPrinter/img"
ML_API_DIR = "/home/mvane/Documents/GitClone/obico-server"
PORT = 8080

def start_ml_api():
    os.chdir(ML_API_DIR)
    # Check if container is already running
    result = subprocess.run("sudo docker compose ps ml_api | grep -q Up", shell=True)
    if result.returncode != 0:
        print("Starting ml_api container...")
        subprocess.run(["sudo", "docker", "compose", "up", "-d", "ml_api"])
    else:
        print("ml_api container is already running")

def start_image_server():
    print(f"Starting image server at http://{HOST_IP}:{PORT}/")
    os.chdir(IMAGE_DIR)
    handler = http.server.SimpleHTTPRequestHandler
    server = http.server.HTTPServer(("", PORT), handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

def check_spaghetti(filename):
    image_url = f"http://{HOST_IP}:{PORT}/{filename}"
    response = requests.get(ML_API, params={"img": image_url})
    print(response)
    return response.json().get("detections", [])

def overlay_detections(filename, detections, confidence_threshold=0.3):
    img = cv2.imread(filename)

    for label, confidence, (cx, cy, w, h) in detections:
        if confidence < confidence_threshold:
            continue

        # Convert center x/y + width/height to corner coordinates
        x1 = int(cx - w / 2)
        y1 = int(cy - h / 2)
        x2 = int(cx + w / 2)
        y2 = int(cy + h / 2)

        # Color goes green -> red based on confidence
        color = (0, int(255 * (1 - confidence)), int(255 * confidence))

        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        cv2.putText(img, f"{confidence:.0%}", (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    output = "output.jpg"
    cv2.imwrite(output, img)
    print(f"Saved to {output}")

start_ml_api()
time.sleep(5)
start_image_server()
filename = "fail.jpg"
t1 = time.time()    
detections = check_spaghetti(filename)
print(detections)
overlay_detections(filename, detections, confidence_threshold=0.3)
t2 = time.time()
print(f"Total time: {t2 - t1:.2f} seconds")