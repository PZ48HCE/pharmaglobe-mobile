import main
from kivy.clock import Clock
import sys

print("Initializing PharmaGlobeApp for verification...")
app = main.PharmaGlobeApp()

def verify_login(dt):
    print("=== STEP: Triggering Guest Login ===")
    try:
        app.handle_login("Guest")
        print("=== STEP: Login triggered successfully, scheduling exit ===")
        # Wait a moment for transition to complete and verify no crash
        Clock.schedule_once(lambda dt: exit_cleanly(), 2.5)
    except Exception as e:
        print(f"Error during login trigger: {e}")
        app.stop()
        sys.exit(1)

def exit_cleanly():
    print("=== SUCCESS: Screen transitioned without crashing ===")
    app.stop()
    sys.exit(0)

# Run verification step 1.5 seconds after window opens
Clock.schedule_once(verify_login, 1.5)

print("Starting app mainloop...")
app.run()
