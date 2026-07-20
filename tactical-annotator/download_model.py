import argparse
import os
import shutil

def download_roboflow(api_key):
    from roboflow import Roboflow
    rf = Roboflow(api_key=api_key)
    project = rf.workspace().project("football-players-detection")
    version = project.version(1)
    dataset = version.download("yolov8")
    # Move the model to the desired location
    model_path = os.path.join(dataset.location, "weights", "best.pt")
    dest_path = "models/football_yolov8.pt"
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    shutil.copy(model_path, dest_path)
    print(f"Model downloaded and saved to {dest_path}")

def download_ultralytics():
    from ultralytics import YOLO
    model = YOLO('yolov8m.pt')  # This will download the model if not present
    model.save("models/football_yolov8.pt")
    print("Model downloaded from ultralytics and saved to models/football_yolov8.pt")
    print("Note: This is a general model and the Roboflow model will give better football-specific detection")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download YOLOv8 model for football player detection.")
    parser.add_argument("--source", choices=["roboflow", "ultralytics"], default="ultralytics", help="Source of the model")
    args = parser.parse_args()

    if args.source == "roboflow":
        api_key = input("Enter your Roboflow API key: ")
        download_roboflow(api_key)
    else:
        download_ultralytics()