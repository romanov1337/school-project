import lgpio
import smbus2
import bme280
import time
import sys
import signal
import math
import RPi.GPIO as GPIO
import threading

# Speed sensor 1 constants (RPi.GPIO, pin 17)
PIN_SPEED1 = 17
RADIUS1 = 0.12

# Speed sensor 2 constants (lgpio, pin 27)  
RADIUS2 = 0.12
h2 = None
callback_id2 = None

# BME280
port = 1
address = 0x76
bus = smbus2.SMBus(port)
bme280.load_calibration_params(bus, address)

# Counters
speed1_count = 0
speed1_last_time = time.time()
speed2_count = 0
speed2_last_time = time.time()

running = True
speed_lock = threading.Lock()

# Initialize RPi.GPIO (sensor 1)
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN_SPEED1, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def speed1_callback(channel):
    """Callback for speed sensor 1 (RPi.GPIO)"""
    global speed1_count, speed1_last_time
    with speed_lock:
        speed1_count += 1
        speed1_last_time = time.time()

GPIO.add_event_detect(PIN_SPEED1, GPIO.FALLING, 
                     callback=speed1_callback, bouncetime=20)

# Callback for speed sensor 2 (lgpio)
def speed2_callback(gpio, level, tick):
    """Callback for speed sensor 2 (lgpio)"""
    global speed2_count, speed2_last_time
    with speed_lock:
        speed2_count += 1
        speed2_last_time = time.time()

# Signal handler
def signal_handler(sig, frame):
    global running
    print("\nStopping...")
    running = False

signal.signal(signal.SIGINT, signal_handler)

# Initialize lgpio (sensor 2)
try:
    h2 = lgpio.gpiochip_open(0)
    lgpio.gpio_claim_input(h2, 27)
    callback_id2 = lgpio.callback(h2, 27, lgpio.BOTH_EDGES, speed2_callback)
    print("Speed sensor 2 (pin 27) initialized")
except Exception as e:
    print(f"Error initializing sensor 2: {e}")
    sys.exit(1)

def calculate_speeds():
    """Calculate and print speeds every second"""
    while running:
        time.sleep(1)
        now = time.time()
        
        with speed_lock:
            # Speed 1 (RPi.GPIO)
            if speed1_count > 0:
                duration1 = now - speed1_last_time
                if duration1 > 0.01:
                    speed1 = (2 * math.pi * RADIUS1 * speed1_count) / duration1
                    print(f"Speed 1 (pin 17): {speed1:.2f} m/s")
                speed1_count = 0
            
            # Speed 2 (lgpio)
            if speed2_count > 0:
                duration2 = now - speed2_last_time
                if duration2 > 0.01:
                    speed2 = (2 * math.pi * RADIUS2 * speed2_count) / duration2
                    print(f"Speed 2 (pin 27): {speed2:.2f} m/s")
                speed2_count = 0

# Start speed calculation thread
speed_thread = threading.Thread(target=calculate_speeds, daemon=True)
speed_thread.start()

print("System started. Ctrl+C to stop")
print("Sensor 1: pin 17 (RPi.GPIO)")
print("Sensor 2: pin 27 (lgpio)")
print("BME280: I2C 0x76")

try:
    while running:
        # Read BME280 every 6 seconds
        data = bme280.sample(bus, address)
        print(f"\n--- BME280 ({time.strftime('%H:%M:%S')}) ---")
        print(f"Temperature: {data.temperature:.2f}°C")
        print(f"Pressure: {data.pressure:.1f} hPa")
        print("-" * 40)
        time.sleep(6)
        
except KeyboardInterrupt:
    pass

# Cleanup
print("\nCleaning up...")
running = False

if callback_id2:
    lgpio.callback_cancel(callback_id2)
if h2:
    lgpio.gpio_free(h2, 27)
    lgpio.gpiochip_close(h2)

GPIO.cleanup()
print("Done!")