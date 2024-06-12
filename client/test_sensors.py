import random
import time

def generate_temperature():
    return round(random.uniform(20.0, 30.0), 2)

def generate_humidity():
    return round(random.uniform(30.0, 70.0), 2)

if __name__ == "__main__":
    while True:
        temp = generate_temperature()
        humidity = generate_humidity()
        print(f"Temperature: {temp}°C, Humidity: {humidity}%")
        time.sleep(0.33)
