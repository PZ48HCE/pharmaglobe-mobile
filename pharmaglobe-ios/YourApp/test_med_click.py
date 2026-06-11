import os
import sys
import time

# Use environment window backend if set, otherwise fallback to sdl2
if 'KIVY_WINDOW' not in os.environ:
    os.environ['KIVY_WINDOW'] = 'sdl2'
from kivy.config import Config

import main
import med_database

print("Initializing PharmaGlobeApp...")
app = main.PharmaGlobeApp()
app.root = app.build()
app.on_start()

# Load a sample medicine
meds = med_database.get_medicines_by_filters(country="Japan", category="Pain Reliever")
if not meds:
    print("No meds found in DB!")
    sys.exit(1)
sample_med = meds[0]
print(f"Sample Med: {sample_med['name']}")

print("Simulating show_medication_details click...")
try:
    app.show_medication_details(sample_med)
    print("SUCCESS: show_medication_details executed without exceptions.")
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
