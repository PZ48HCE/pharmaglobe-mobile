import sys
import unittest
from unittest.mock import MagicMock, patch

from kivymd.app import MDApp
from kivy.properties import StringProperty, NumericProperty, ListProperty, BooleanProperty

class DummyMDApp(MDApp):
    active_tab = StringProperty("home")
    wishlist_prev_tab = StringProperty("home")
    user_points = NumericProperty(1004)
    saved_items = ListProperty([])
    destination_country = StringProperty("Global (All)")
    current_country = StringProperty("Global (All)")
    current_category = StringProperty("All")
    preferred_language = StringProperty("English")
    is_online = BooleanProperty(True)

    def build(self):
        return None

app_mock = DummyMDApp()
app_mock.theme_cls.primary_palette = "Red"
app_mock.theme_cls.theme_style = "Light"

import kivy.app
kivy.app.App.get_running_app = MagicMock(return_value=app_mock)

import main
from kivy.lang import Builder
# Import SmoothScrollEffect to __main__ so KV compiler can find it
import sys
import types
current_module = sys.modules[__name__]
setattr(current_module, 'SmoothScrollEffect', main.SmoothScrollEffect)

Builder.load_string(main.KV)

class MockWidget:
    def __init__(self, **kwargs):
        self.text = ""
        self.opacity = 0
        self.disabled = False
        self.source = ""
        self.height = 0
        for k, v in kwargs.items():
            setattr(self, k, v)
            
    def clear_widgets(self):
        pass
        
    def add_widget(self, widget):
        pass
        
    def bind(self, **kwargs):
        pass

class MockIds(dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for k, v in kwargs.items():
            setattr(self, k, v)
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

class TestPharmaGlobeClickLogic(unittest.TestCase):
    def test_med_click_flow(self):
        # Configure app mock properties
        app_mock.root = MockWidget()
        app_mock.root.ids = MockIds(
            details_title=MockWidget(),
            details_subtitle=MockWidget(),
            details_meta=MockWidget(),
            details_image_card=MockWidget(),
            details_image=MockWidget(),
            details_info_container=MockWidget(),
            language_chips_container=MockWidget(),
            tab_manager=MockWidget(current="home")
        )
        app_mock.root.transition = MockWidget(direction="")
        app_mock.root.current = "main_screen"
        
        sample_med = {
            "name": "Loxonin S",
            "generic_name": "Loxoprofen Sodium",
            "category": "Pain Reliever",
            "country": "Japan",
            "uses": "Headaches, fever reduction.",
            "dosage": "1 tablet daily",
            "precautions": "Take with food.",
            "price": "¥650",
            "shop_link": "http://example.com"
        }
        
        app_mock.populate_language_chips = lambda: main.PharmaGlobeApp.populate_language_chips(app_mock)
        app_mock.translate_current_medicine = lambda lang: main.PharmaGlobeApp.translate_current_medicine(app_mock, lang)
        app_mock._show_details_dialog = lambda med: main.PharmaGlobeApp._show_details_dialog(app_mock, med)

        print("Triggering show_medication_details on mock app...")
        try:
            # Set online to False to bypass background thread image search for test
            app_mock.is_online = False
            main.PharmaGlobeApp.show_medication_details(app_mock, sample_med)
            print("SUCCESS: show_medication_details test passed.")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.fail(f"Clicked failed with exception: {e}")

if __name__ == '__main__':
    unittest.main()
