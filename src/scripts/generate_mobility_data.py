import csv
import random
from datetime import datetime, timedelta
import os

def generate_data(num_rows=500):
    output_dir = ".context/testing_agentic_engineering_team/data"
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, "movement_predictions.csv")

    modes = ["walking", "cycling", "train", "car", "bus"]
    regions = ["Tokyo", "Osaka", "Fukuoka", "Nagoya"]
    
    # Anomaly setting: Tokyo has high error rate for Train -> Car
    
    start_time = datetime.now() - timedelta(days=30)
    
    fieldnames = [
        "user_id", "start_time", "end_time", "predicted_mode", 
        "actual_mode", "confidence", "distance_km", "region"
    ]

    with open(file_path, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for i in range(num_rows):
            user_id = f"USR-{random.randint(100, 150)}"
            region = random.choice(regions)
            
            # Times
            move_duration = random.randint(5, 60) # minutes
            move_start = start_time + timedelta(
                days=random.randint(0, 29), 
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            )
            move_end = move_start + timedelta(minutes=move_duration)
            
            # Mode & Accuracy logic
            true_mode = random.choice(modes)
            predicted_mode = true_mode
            
            # Simulate misclassification
            error_roll = random.random()
            if region == "Tokyo" and true_mode == "train":
                if error_roll < 0.35: # 35% error rate in Tokyo for trains
                    predicted_mode = "car"
            elif error_roll < 0.10: # 10% baseline error
                predicted_mode = random.choice([m for m in modes if m != true_mode])
            
            # Confidence
            if predicted_mode == true_mode:
                confidence = round(random.uniform(0.7, 0.99), 2)
            else:
                confidence = round(random.uniform(0.4, 0.75), 2)
            
            # Distance
            dist_km = round(random.uniform(0.5, 15.0), 2)
            
            # Feedback probability (80% users give feedback)
            feedback = true_mode if random.random() < 0.8 else ""

            writer.writerow({
                "user_id": user_id,
                "start_time": move_start.isoformat(),
                "end_time": move_end.isoformat(),
                "predicted_mode": predicted_mode,
                "actual_mode": feedback,
                "confidence": confidence,
                "distance_km": dist_km,
                "region": region
            })

    print(f"✅ Successfully generated {num_rows} rows to {file_path}")

if __name__ == "__main__":
    generate_data()
