import os
import sys

# Force headless dummy graphics backend
os.environ['KIVY_WINDOW'] = 'dummy'
os.environ['KIVY_USE_DEFAULT_ATTRIBUTES'] = '1'
from kivy.config import Config
Config.set('graphics', 'window_backend', 'dummy')

import main
import med_database

print("Initializing PharmaGlobeApp...")
app = main.PharmaGlobeApp()
app.root = app.build()
app.on_start()

print("Retrieving a medicine from database...")
med = med_database.search_local_medicines("Loxonin")[0]
print(f"Testing details dialog rendering for: {med['name']}")

try:
    app._show_details_dialog(med)
    print("SUCCESS: details dialog rendered successfully without exceptions.")
except Exception as e:
    print(f"FAILED: Details rendering raised exception: {e}")
    sys.exit(1)
