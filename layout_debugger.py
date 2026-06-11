import os
import sys

# Force headless execution
os.environ['KIVY_WINDOW'] = 'dummy'
os.environ['KIVY_USE_DEFAULT_ATTRIBUTES'] = '1'

from kivy.config import Config
Config.set('graphics', 'window_backend', 'dummy')

from kivy.clock import Clock
from kivy.metrics import dp

# Create a mock App object to satisfy references
class MockThemeCls:
    primary_color = [1, 1, 1, 1]
    accent_color = [1, 1, 1, 1]
    theme_style = "Light"

class MockApp:
    def __init__(self):
        self.saved_items = []
        self.user_points = 1000
        self.theme_cls = MockThemeCls()
        
    @staticmethod
    def get_running_app():
        return app_inst

app_inst = MockApp()

# Inject MockApp into sys.modules to prevent real app import if needed,
# or mock Kivy's App.get_running_app
import kivy.app
kivy.app.App.get_running_app = MockApp.get_running_app

import kivymd.app
kivymd.app.MDApp.get_running_app = MockApp.get_running_app

# Mock MDCard if needed? No, let's import it and see if we can instantiate it
from main import MobileMedicineCard, MDBoxLayout

mock_med = {
    "name": "Pabron Gold A (パブロンゴールドA)",
    "generic_name": "Guaifenesin + Dihydrocodeine Phosphate + Acetaminophen + Clorpheniramine Maleate + DL-Methylephedrine Hydrochloride + Anhydrous Caffeine",
    "category": "Cold & Flu",
    "price": "¥1,300 - ¥1,800 (44 packets / 210 tablets)",
    "country": "Japan",
    "image_url": "http://example.com/pabron.jpg"
}

print("Instantiating MobileMedicineCard...")
card = MobileMedicineCard(mock_med)
card.width = 320
card.height = 140

text_layout = None
for child in card.children:
    if isinstance(child, MDBoxLayout) and child.orientation == 'vertical':
        text_layout = child
        break

if text_layout:
    text_layout.width = 200
    for child in text_layout.children:
        if hasattr(child, 'width'):
            child.width = 200
            
    # Run clock ticks to let Kivy trigger its layout bindings
    Clock.tick()
    
    print("\n--- After Layout Simulation ---")
    print(f"Card dimensions: width={card.width}, height={card.height}")
    print(f"Text Layout height: {text_layout.height}")
    for lbl in reversed(text_layout.children):
        print(f"Label text={getattr(lbl, 'text', '')[:30]}...")
        print(f"      size={lbl.size}, text_size={lbl.text_size}, texture_size={lbl.texture_size}")
else:
    print("Could not find text_layout")

sys.exit(0)
