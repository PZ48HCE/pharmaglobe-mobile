import os
import sys
import time

# Use environment window backend if set, otherwise fallback to sdl2
if 'KIVY_WINDOW' not in os.environ:
    os.environ['KIVY_WINDOW'] = 'sdl2'
from kivy.config import Config

import main

print("Initializing PharmaGlobeApp...")
app = main.PharmaGlobeApp()
# Mock root window to bypass KivyMD window requirement
from kivy.core.window import Window
app.root = app.build()
app.on_start()

print("Simulating Login as Guest...")
try:
    # Trigger login directly
    app.handle_login("Guest")
    
    # Tick clock manually to trigger schedule_once(complete_login, 1.2)
    from kivy.clock import Clock
    start_time = time.time()
    while time.time() - start_time < 2.0:
        Clock.tick()
        time.sleep(0.1)
        
    print("SUCCESS: Logged in programmatically without exceptions.")
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
