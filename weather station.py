import lgpio
import smbus2
import bme280
import time
import sys
import signal
import math
import RPi.GPIO as GPIO
import threading
import telebot

TOKEN = '8552257727:AAGStjh0u3eGJw75znZv9UZS8ku-QeonqZA'
bot = telebot.TeleBot(TOKEN)
MY_CHAT_ID = None

def send_to_my_chat(message):
    global MY_CHAT_ID
    if MY_CHAT_ID:
        try:
            bot.send_message(MY_CHAT_ID, message)
        except:
            pass

@bot.message_handler(commands=['start'])
def start_command(message):
    global MY_CHAT_ID
    MY_CHAT_ID = message.chat.id
    send_to_my_chat("✅ СИСТЕМА ДАТЧИКОВ ЗАПУЩЕНА!")

@bot.message_handler(commands=['temp'])
def temp_only(message):
    global MY_CHAT_ID
    if MY_CHAT_ID == message.chat.id:
        try:
            data = bme280.sample(bus, address)
            msg = f"🌡️  T: {data.temperature:.2f}°C"
            bot.send_message(MY_CHAT_ID, msg)
        except:
            bot.send_message(MY_CHAT_ID, "❌ Ошибка чтения BME280")
            
@bot.message_handler(commands=['press'])
def temp_only(message):
    global MY_CHAT_ID
    if MY_CHAT_ID == message.chat.id:
        try:
            data = bme280.sample(bus, address)
            msg = f"📈 P: {data.pressure:.1f} hPa"
            bot.send_message(MY_CHAT_ID, msg)
        except:
            bot.send_message(MY_CHAT_ID, "❌ Ошибка чтения BME280")

@bot.message_handler(commands=['speed of wind'])
def speed_only(message):
    global MY_CHAT_ID
    if MY_CHAT_ID == message.chat.id:
        msg = f"🌬️  Speed (pin 17): {speed1:.2f} м/с"
        bot.send_message(MY_CHAT_ID, msg)

@bot.message_handler(commands=['stop'])
def stop_bot(message):
    global MY_CHAT_ID, running
    if MY_CHAT_ID == message.chat.id:
        send_to_my_chat("🛑 РАБОТА ЗАВЕРШЕНА")
        running = False
        sys.exit(0)
            
@bot.message_handler(commands=['data'])
def send_data_now(message):
    global force_data_send
    force_data_send = True

force_data_send = False

PIN_SPEED1 = 17
RADIUS1 = 0.12
RADIUS2 = 0.12
h2 = None
callback_id2 = None

port = 1
address = 0x76
bus = smbus2.SMBus(port)
bme280.load_calibration_params(bus, address)

speed1_count = 0
speed1_last_time = time.time()
speed2_count = 0
speed2_last_time = time.time()

running = True
speed_lock = threading.Lock()

GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN_SPEED1, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def speed1_callback(channel):
    global speed1_count, speed1_last_time
    with speed_lock:
        speed1_count += 1
        speed1_last_time = time.time()

GPIO.add_event_detect(PIN_SPEED1, GPIO.FALLING, 
                     callback=speed1_callback, bouncetime=20)

def speed2_callback(gpio, level, tick):
    global speed2_count, speed2_last_time
    with speed_lock:
        speed2_count += 1
        speed2_last_time = time.time()

def signal_handler(sig, frame):
    global running
    send_to_my_chat("\nStopping...")
    running = False

signal.signal(signal.SIGINT, signal_handler)

try:
    h2 = lgpio.gpiochip_open(0)
    lgpio.gpio_claim_input(h2, 27)
    callback_id2 = lgpio.callback(h2, 27, lgpio.BOTH_EDGES, speed2_callback)
    send_to_my_chat("Speed sensor 2 (pin 27) initialized")
except Exception as e:
    send_to_my_chat(f"Error initializing sensor 2: {e}")
    sys.exit(1)

def calculate_speeds():
    global speed1, speed2
    speed1 = speed2 = 0
    while running:
        time.sleep(1)
        now = time.time()
        
        with speed_lock:
            if speed1_count > 0:
                duration1 = now - speed1_last_time
                if duration1 > 0.01:
                    speed1 = (2 * math.pi * RADIUS1 * speed1_count) / duration1
                    send_to_my_chat(f"Speed 1 (pin 17): {speed1:.2f} m/s")
                speed1_count = 0
            
            if speed2_count > 0:
                duration2 = now - speed2_last_time
                if duration2 > 0.01:
                    speed2 = (2 * math.pi * RADIUS2 * speed2_count) / duration2
                    send_to_my_chat(f"Speed 2 (pin 27): {speed2:.2f} m/s")
                speed2_count = 0

speed_thread = threading.Thread(target=calculate_speeds, daemon=True)
speed_thread.start()

def bot_thread():
    bot.polling(none_stop=True)

bot_thread_t = threading.Thread(target=bot_thread, daemon=True)
bot_thread_t.start()

send_to_my_chat("System started. Ctrl+C to stop")
send_to_my_chat("Sensor 1: pin 17 (RPi.GPIO)")
send_to_my_chat("Sensor 2: pin 27 (lgpio)")
send_to_my_chat("BME280: I2C 0x76")

try:
    while running:
        data = bme280.sample(bus, address)
        send_to_my_chat(f"\n--- BME280 ({time.strftime('%H:%M:%S')}) ---")
        send_to_my_chat(f"Temperature: {data.temperature:.2f}°C")
        send_to_my_chat(f"Pressure: {data.pressure:.1f} hPa")
        send_to_my_chat("-" * 40)
        time.sleep(6)
        
except KeyboardInterrupt:
    pass

send_to_my_chat("\nCleaning up...")
running = False

if callback_id2:
    lgpio.callback_cancel(callback_id2)
if h2:
    lgpio.gpio_free(h2, 27)
    lgpio.gpiochip_close(h2)

GPIO.cleanup()
send_to_my_chat("Done!")
