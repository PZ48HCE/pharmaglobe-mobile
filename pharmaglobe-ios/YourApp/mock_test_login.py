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

# Instantiate a real MDApp subclass instance
app_mock = DummyMDApp()
app_mock.theme_cls.primary_palette = "Red"
app_mock.theme_cls.theme_style = "Light"

# Mock Kivy's App.get_running_app to return our DummyMDApp instance
import kivy.app
kivy.app.App.get_running_app = MagicMock(return_value=app_mock)

import main
from kivy.lang import Builder
# Import SmoothScrollEffect and FlagWidget to __main__ so KV compiler can find it
import sys
import types
current_module = sys.modules['__main__']
setattr(current_module, 'SmoothScrollEffect', main.SmoothScrollEffect)
setattr(current_module, 'FlagWidget', main.FlagWidget)

Builder.load_string(main.KV)
import med_database

class MockWidget:
    def __init__(self, **kwargs):
        self.text = ""
        self.opacity = 0
        self.disabled = False
        for k, v in kwargs.items():
            setattr(self, k, v)

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

class TestPharmaGlobeLoginLogic(unittest.TestCase):
    @patch('kivy.clock.Clock.schedule_once')
    def test_login_flow_and_widgets(self, mock_schedule_once):
        # Configure our global app mock properties
        app_mock.destination_country = "Global (All)"
        app_mock.current_country = "Global (All)"
        app_mock.current_category = "All"
        app_mock.preferred_language = "English"
        app_mock.saved_items = []
        app_mock.is_online = True
        
        # Mock widget structures
        app_mock.root = MockWidget()
        app_mock.root.ids = MockIds(
            login_loader=MockWidget(opacity=0, disabled=True),
            loader_text=MockWidget(text=""),
            login_destination_input=MockWidget(text="Japan"),
            login_language_input=MockWidget(text="English"),
            country_chips_container=MagicMock(),
            category_chips_container=MagicMock(),
            directory_grid=MagicMock(),
            tab_manager=MockWidget(current="home"),
        )
        app_mock.root.transition = MockWidget(direction="")
        app_mock.root.current = "login_screen"
        
        # Bind methods
        app_mock.populate_location_chips = lambda: main.PharmaGlobeApp.populate_location_chips(app_mock)
        app_mock.populate_category_chips = lambda: main.PharmaGlobeApp.populate_category_chips(app_mock)
        app_mock.render_directory = lambda: main.PharmaGlobeApp.render_directory(app_mock)
        app_mock.complete_login_flow = lambda m, v=None: main.PharmaGlobeApp.complete_login_flow(app_mock, m, v)
        
        # Call handle_login on main class
        main.PharmaGlobeApp.handle_login(app_mock, "Guest")
        
        # Ensure Clock.schedule_once was called to trigger complete_login
        self.assertTrue(mock_schedule_once.called)
        
        # Get complete_login callback
        callback = mock_schedule_once.call_args[0][0]
        
        # Trigger the complete_login callback
        print("Triggering complete_login callback...")
        callback(0)
        
        # Verify app properties are updated correctly
        self.assertEqual(app_mock.destination_country, "Japan")
        self.assertEqual(app_mock.current_country, "Japan")
        self.assertEqual(app_mock.preferred_language, "English")
        
        # Verify transition screen switching
        self.assertEqual(app_mock.root.current, "main_screen")
        self.assertEqual(app_mock.root.transition.direction, "up")
        print("MOCK TEST SUCCESS: Login flow verified successfully.")

if __name__ == '__main__':
    unittest.main()
