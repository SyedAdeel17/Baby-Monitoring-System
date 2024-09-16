import pygame
import tkinter as tk
from tkinter import Tk, Label, PhotoImage, messagebox, Checkbutton, BooleanVar
import time
import random
import firebase_admin
from firebase_admin import credentials, db

# Initialize pygame mixer
pygame.mixer.init()


# Initialize alert time tracking for different alerts
last_temp_alert_time = time.time()
last_cradle_alert_time = time.time()
last_crying_alert_time = time.time()

# Set different alert intervals (in seconds) for each type of alert
temp_alert_interval = 11  
cradle_alert_interval = 20  
crying_alert_interval = 8 
# Initialize variables for crying simulation
monitor_start_time = None
crying_played = False
crying_repeat_interval = 5

#
history_data = []

# Firebase setup
cred = credentials.Certificate("baby-monitoring1-firebase-adminsdk-ucdp8-b5f7e4dad3.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://baby-monitoring1-default-rtdb.asia-southeast1.firebasedatabase.app'
})

alerts_ref = db.reference('alerts')


last_heart_rate = 120

def fetch_data():
    global last_heart_rate, monitor_start_time
    
    heart_rate_change = random.choice([-1, 0, 1])
    last_heart_rate += heart_rate_change
    last_heart_rate = max(100, min(160, last_heart_rate))
    
    current_time = time.time()
    crying = False
    if monitor_start_time and (current_time - monitor_start_time >= 3):
        crying = True
    
    simulated_data = {
        'heart_rate': last_heart_rate,
        'temperature': round(random.uniform(35.0, 40.0), 1),
        'humidity': random.randint(30, 60),
        'cradle_occupied': random.choice([True, False]),
        'boundary_crossed': random.choice([True, False]),
        'crying': crying  
    }
    return simulated_data

def update_monitoring():
    global last_temp_alert_time, last_boundary_alert_time, last_crying_alert_time
    global crying_played
    data = fetch_data()

    if data:
        # Existing label updates
        heart_rate_label.config(text=f"Heart Rate: {data.get('heart_rate', '--')} bpm")
        temp_label.config(text=f"Temperature: {data.get('temperature', '--')} °C")
        humidity_label.config(text=f"Humidity: {data.get('humidity', '--')} %")

        # Save the data to history_data
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        history_data.append({
            'time': current_time,
            'heart_rate': data.get('heart_rate', '--'),
            'temperature': data.get('temperature', '--'),
            'humidity': data.get('humidity', '--')
        })

        # Monitor for alerts and conditions
        current_time_secs = time.time()

        # Monitor for abnormal temperature
        if monitor_temp.get() and (data.get('temperature', 0) > 39):
            if current_time_secs - last_temp_alert_time > temp_alert_interval:
                alert("Abnormal temperature detected!")
                last_temp_alert_time = current_time_secs

        # Monitor for cradle boundary crossing
        if monitor_cradle_sensor.get() and not data.get('cradle_occupied', True):
            if current_time_secs - last_cradle_alert_time > cradle_alert_interval:
                alert("Warning: Cradle crossed boundary!")
                last_boundary_alert_time = current_time_secs

        # Crying detection
        if data.get('crying', False):
            if not crying_played:
                if current_time_secs - last_crying_alert_time > crying_alert_interval:
                    play_crying_sound()
                    alert("Baby is crying!")
                    crying_played = True
                    last_crying_alert_time = current_time_secs

    global monitoring_task_id
    monitoring_task_id = root.after(2000, update_monitoring)


def play_crying_sound():
    try:
        pygame.mixer.music.load('baby-crying-64996.mp3')
        pygame.mixer.music.play()
        
        root.after(20000, stop_crying_sound)
    except pygame.error as e:
        print(f"Error loading or playing the sound: {e}")

def stop_crying_sound():
    if pygame.mixer.music.get_busy():
        pygame.mixer.music.stop()

def alert(message):
    
    messagebox.showwarning("Alert", message)
    stop_crying_sound() 
    
    
    send_alert_to_firebase(message)

def send_alert_to_firebase(message):
    current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    alerts_ref.push({
        'message': message,
        'timestamp': current_time
    })

def start_monitoring():
    global monitoring_task_id, monitor_start_time, crying_played
    if monitoring_task_id is None:
        monitor_start_time = time.time()  
        crying_played = False
        
    
        update_monitoring()

def stop_monitoring():
    global monitoring_task_id, monitor_start_time
    if monitoring_task_id is not None:
        root.after_cancel(monitoring_task_id)
        monitoring_task_id = None
    pygame.mixer.music.stop()  
    monitor_start_time = None

def show_realtime_page():
    hide_all_frames()
    realtime_frame.pack(fill=tk.BOTH, expand=True)

def show_historical_page():
    hide_all_frames()
    historical_frame.pack(fill=tk.BOTH, expand=True)
    update_history()

def hide_all_frames():
    realtime_frame.pack_forget()
    historical_frame.pack_forget()

def update_history():
    history_display.config(state=tk.NORMAL)
    history_display.delete(1.0, tk.END)
    for entry in history_data:
        history_text = (
            f"{entry['time']} - Heart Rate: {entry['heart_rate']} bpm,     "
            f"Temperature: {entry['temperature']} °C,     "
            f"Humidity: {entry['humidity']} %\n"
        )
        history_display.insert(tk.END, history_text)
    history_display.config(state=tk.DISABLED)

def on_baby_drag(event):
    x = event.x
    y = event.y
    canvas.moveto(baby_id, x - baby_image.width() // 2, y - baby_image.height() // 2)
    check_boundary(x - baby_image.width() // 2, y - baby_image.height() // 2)

def check_boundary(x0, y0):
    x1 = x0 + baby_image.width()
    y1 = y0 + baby_image.height()
    if (x0 < boundary_thickness or y0 < boundary_thickness or
        x1 > boundary_width + boundary_thickness or y1 > boundary_height + boundary_thickness):
        if not hasattr(check_boundary, 'alert_triggered') or not check_boundary.alert_triggered:
            alert("Warning: Baby lifted from cradle and crossed boundary!")
            send_boundary_alert()
            check_boundary.alert_triggered = True
    else:
        if hasattr(check_boundary, 'alert_triggered') and check_boundary.alert_triggered:
            check_boundary.alert_triggered = False

def on_cradle_drag(event):
    new_x = event.x
    new_y = event.y
    canvas.moveto(cradle_id, new_x - cradle_image.width() // 2, new_y - cradle_image.height() // 2)
    x0 = new_x - cradle_image.width() // 2
    y0 = new_y - cradle_image.height() // 2
    x1 = x0 + cradle_image.width()
    y1 = y0 + cradle_image.height()

    if monitor_boundaries.get():
        if (x0 <= boundary_thickness or y0 <= boundary_thickness or
            x1 >= boundary_width + boundary_thickness or y1 >= boundary_height + boundary_thickness):
            if not hasattr(on_cradle_drag, 'alert_triggered') or not on_cradle_drag.alert_triggered:
                alert("Warning: Cradle has touched the boundary!")
                send_boundary_alert()
                on_cradle_drag.alert_triggered = True
        else:
            if hasattr(on_cradle_drag, 'alert_triggered') and on_cradle_drag.alert_triggered:
                on_cradle_drag.alert_triggered = False

def send_boundary_alert():
    current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    boundary_data = {
        'message': "Cradle or baby touched boundary",
        'timestamp': current_time
    }
    alerts_ref.push(boundary_data)

# Initialize Tkinter
root = tk.Tk()
root.title("Smart Baby Monitoring Application")
root.geometry("800x600")
root.configure(bg="#f0f0f0")

# Global variables
monitoring_task_id = None
monitor_temp = BooleanVar(value=True)
monitor_boundaries = BooleanVar(value=True)
monitor_cradle_sensor = BooleanVar(value=True)

realtime_frame = tk.Frame(root, bg="#f0f0f0")
historical_frame = tk.Frame(root, bg="#f0f0f0")

top_frame = tk.Frame(realtime_frame, bg="#e0e0e0", pady=10)
top_frame.pack(fill=tk.X)

bottom_frame = tk.Frame(realtime_frame, bg="#e0e0e0", pady=10)
bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)

image_frame = tk.Frame(realtime_frame, bg="#f0f0f0")
image_frame.pack(pady=20, padx=20)

boundary_color = "#3498db"
boundary_thickness = 40  
boundary_width = 450  
boundary_height = 400 

canvas = tk.Canvas(image_frame, width=boundary_width + boundary_thickness * 2, height=boundary_height + boundary_thickness * 2, bg="#f0f0f0", highlightthickness=0)
canvas.pack()

canvas.create_rectangle(boundary_thickness, boundary_thickness, boundary_width + boundary_thickness, boundary_height + boundary_thickness, outline=boundary_color, width=boundary_thickness)

cradle_image = None
baby_image = None
try:
    cradle_image = PhotoImage(file="c2.png").subsample(2, 2)
    baby_image = PhotoImage(file="b3.png").subsample(3, 3)
except tk.TclError:
    print("Image file not found. Skipping...")

if cradle_image:
    cradle_x = (boundary_width - cradle_image.width()) // 2
    cradle_y = (boundary_height - cradle_image.height()) // 2
    cradle_id = canvas.create_image(cradle_x + boundary_thickness, cradle_y + boundary_thickness, anchor=tk.NW, image=cradle_image)
    canvas.tag_bind(cradle_id, "<B1-Motion>", on_cradle_drag)

if baby_image:
    baby_x = (boundary_width - baby_image.width()) // 2 + 50
    baby_y = (boundary_height - baby_image.height()) // 2 + 50
    baby_id = canvas.create_image(baby_x + boundary_thickness, baby_y + boundary_thickness, anchor=tk.NW, image=baby_image)
    canvas.tag_bind(baby_id, "<B1-Motion>", on_baby_drag)

sensor_frame = tk.Frame(top_frame, bg="#e0e0e0")
sensor_frame.pack(pady=30)

heart_rate_label = tk.Label(sensor_frame, text="Heart Rate: -- bpm", font=("Arial", 16), bg="#e0e0e0")
heart_rate_label.grid(row=0, column=0, padx=40)

temp_label = tk.Label(sensor_frame, text="Temperature: -- °C", font=("Arial", 16), bg="#e0e0e0")
temp_label.grid(row=0, column=1, padx=40)

humidity_label = tk.Label(sensor_frame, text="Humidity: -- %", font=("Arial", 16), bg="#e0e0e0")
humidity_label.grid(row=0, column=2, padx=40)

control_frame = tk.Frame(bottom_frame, bg="#e0e0e0")
control_frame.pack(pady=30)

start_button = tk.Button(control_frame, text="Start Monitoring", command=start_monitoring, font=("Arial", 12), bg="#4CAF50", fg="white", padx=10, pady=5)
start_button.grid(row=0, column=0, padx=30, pady=5)

stop_button = tk.Button(control_frame, text="Stop Monitoring", command=stop_monitoring, font=("Arial", 12), bg="#F44336", fg="white", padx=10, pady=5)
stop_button.grid(row=0, column=1, padx=30, pady=5)

historical_button = tk.Button(control_frame, text="Historical Data", command=show_historical_page, font=("Arial", 12), bg="#2196F3", fg="white", padx=10, pady=5)
historical_button.grid(row=0, column=2, padx=30, pady=5)

checkbox_frame = tk.Frame(top_frame, bg="#e0e0e0")
checkbox_frame.pack(pady=20)

temp_checkbox = Checkbutton(checkbox_frame, text="Monitor Temperature", variable=monitor_temp, bg="#e0e0e0")
temp_checkbox.grid(row=0, column=0, padx=10)

boundaries_checkbox = Checkbutton(checkbox_frame, text="Monitor Boundaries", variable=monitor_boundaries, bg="#e0e0e0")
boundaries_checkbox.grid(row=0, column=1, padx=10)

cradle_sensor_checkbox = Checkbutton(checkbox_frame, text="Monitor Cradle Sensor", variable=monitor_cradle_sensor, bg="#e0e0e0")
cradle_sensor_checkbox.grid(row=0, column=2, padx=10)

history_container = tk.Frame(historical_frame, bg="#f0f0f0")
history_container.pack(pady=10)

history_scroll_y = tk.Scrollbar(history_container, orient=tk.VERTICAL)
history_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

history_display = tk.Text(history_container, height=25, width=90, bg="#ffffff", font=("Arial", 16), wrap=tk.NONE, yscrollcommand=history_scroll_y.set)
history_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

history_scroll_y.config(command=history_display.yview)

back_button = tk.Button(historical_frame, text="Back to Home page", command=show_realtime_page, font=("Arial", 12), bg="#FFC107", fg="black", padx=10, pady=5)
back_button.pack(pady=10)

show_realtime_page()

root.mainloop()
