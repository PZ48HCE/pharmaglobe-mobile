import os
import requests
import threading
import webbrowser
from PIL import Image as PILImage

# Import Kivy core libraries
from kivy.config import Config
# Force multi-touch emulation off for clean clicks
Config.set('input', 'mouse', 'mouse,disable_multitouch')

from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.widget import Widget
from kivy.properties import StringProperty, ListProperty, BooleanProperty, NumericProperty
from kivy.graphics import Color, Rectangle, Ellipse, Line
from kivy.clock import Clock
Clock.max_iteration = 30
from kivy.metrics import dp

# Import KivyMD components
from kivy.factory import Factory
from kivymd.app import MDApp
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDRaisedButton, MDIconButton
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.relativelayout import MDRelativeLayout
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.label import MDLabel, MDIcon

# Import backend logic helpers
import med_database as med
import openfda_helper
import barcode_helper
import ai_helper

# Register custom Japanese CJK font to resolve box rendering bugs
from kivy.core.text import LabelBase
try:
    font_path = os.path.join(os.path.dirname(__file__), "NotoSansJP-Regular.otf")
    if os.path.exists(font_path):
        LabelBase.register(
            name="Roboto",
            fn_regular=font_path,
            fn_bold=font_path,
            fn_italic=font_path,
            fn_bolditalic=font_path
        )
        print("Successfully registered Noto Sans JP as the default app font.")
except Exception as e:
    print(f"Error registering custom CJK font: {e}")


from kivy.effects.dampedscroll import DampedScrollEffect
class SmoothScrollEffect(DampedScrollEffect):
    """Custom scroll effect using damped scroll effect for snappy, responsive scrolling."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.friction = 0.05
        self.min_velocity = 0.5
        self.max_history = 5

from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp
import weakref

class ResponsiveScrollView(ScrollView):
    """
    A custom ScrollView that intercepts drags instantly for a super snappy feel.
    Ripples/clicks on child cards/buttons are immediate, and dragging starting from
    anywhere (including text labels) will scroll without any blocking or lag.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.scroll_timeout = 250
        self.scroll_distance = dp(10)
        
    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
            
        # Let Kivy's default mouse wheel scroll behavior handle scroll wheel events
        if 'button' in touch.profile and touch.button.startswith('scroll'):
            return super().on_touch_down(touch)
            
        if not self.children:
            return super().on_touch_down(touch)
            
        # We track this touch
        self._touch = touch
        touch.grab(self)
        
        # Save start coordinates and scrolling state
        touch.ud[f'sv_start_pos_{id(self)}'] = touch.pos
        touch.ud[f'sv_is_scrolling_{id(self)}'] = False
        
        # Propagate touch down to children immediately for instant press states/ripples
        touch.push()
        touch.apply_transform_2d(self.to_local)
        child_handled = False
        for child in reversed(self.children):
            if child.dispatch('on_touch_down', touch):
                child_handled = True
                break
        touch.pop()
        
        # Find which child widget grabbed the touch (if any)
        grabbed_child = None
        if len(touch.grab_list) > 1:
            for item in reversed(touch.grab_list):
                try:
                    w = item() if callable(item) else item
                    if w and w is not self:
                        grabbed_child = w
                        break
                except Exception:
                    pass
        touch.ud[f'sv_grabbed_child_{id(self)}'] = grabbed_child
        
        # Initialize scroll effects
        self._update_effect_bounds()
        if self.do_scroll_x and self.effect_x:
            self._effect_x_start_width = self.width
            self.effect_x.start(touch.x)
        if self.do_scroll_y and self.effect_y:
            self._effect_y_start_height = self.height
            self.effect_y.start(touch.y)
            
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is self or (f'sv_start_pos_{id(self)}' in touch.ud):
            start_pos = touch.ud.get(f'sv_start_pos_{id(self)}')
            if not start_pos:
                return super().on_touch_move(touch)
                
            is_scrolling = touch.ud.get(f'sv_is_scrolling_{id(self)}', False)
            
            if not is_scrolling:
                dx = abs(touch.x - start_pos[0])
                dy = abs(touch.y - start_pos[1])
                
                # Check if drag distance exceeds threshold
                if (self.do_scroll_x and dx > self.scroll_distance) or (self.do_scroll_y and dy > self.scroll_distance):
                    is_scrolling = True
                    touch.ud[f'sv_is_scrolling_{id(self)}'] = True
                    
                    # Intercept the touch! Ungrab the child widget
                    grabbed_child = touch.ud.get(f'sv_grabbed_child_{id(self)}')
                    if grabbed_child:
                        try:
                            touch.ungrab(grabbed_child)
                        except Exception:
                            pass
                            
                        # Cancel pressed/ripple states of the child and its parent hierarchies
                        curr = grabbed_child
                        while curr and curr is not self:
                            if hasattr(curr, 'state'):
                                curr.state = 'normal'
                            if hasattr(curr, 'cancel_ripple'):
                                curr.cancel_ripple()
                            curr = curr.parent
                            
                    # Force grab to ourselves
                    touch.grab_current = self
            
            if is_scrolling:
                # Update scroll effects directly
                if self.do_scroll_x and self.effect_x:
                    self.effect_x.update(touch.x)
                if self.do_scroll_y and self.effect_y:
                    self.effect_y.update(touch.y)
                return True
            else:
                # Send touch move to children normally
                if self.children:
                    touch.push()
                    touch.apply_transform_2d(self.to_local)
                    for child in reversed(self.children):
                        child.dispatch('on_touch_move', touch)
                    touch.pop()
                return True
                
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self or (f'sv_start_pos_{id(self)}' in touch.ud):
            is_scrolling = touch.ud.get(f'sv_is_scrolling_{id(self)}', False)
            
            # Stop scroll effects
            if self.do_scroll_x and self.effect_x:
                self.effect_x.stop(touch.x)
            if self.do_scroll_y and self.effect_y:
                self.effect_y.stop(touch.y)
                
            # Release our own grab
            touch.ungrab(self)
            self._touch = None
            
            if not is_scrolling:
                # Tap! Propagate touch up to children
                if self.children:
                    touch.push()
                    touch.apply_transform_2d(self.to_local)
                    grabbed_child = touch.ud.get(f'sv_grabbed_child_{id(self)}')
                    if grabbed_child:
                        try:
                            grabbed_child.dispatch('on_touch_up', touch)
                        except Exception:
                            pass
                    else:
                        for child in reversed(self.children):
                            child.dispatch('on_touch_up', touch)
                    touch.pop()
                
            return True
            
        return super().on_touch_up(touch)

from kivy.factory import Factory
Factory.register('ResponsiveScrollView', cls=ResponsiveScrollView)


from kivy.uix.image import Image
from kivy.network.urlrequest import UrlRequest
import hashlib

class UAAsyncImage(Image):
    """Custom Image widget that downloads remote images using a custom User-Agent to bypass 403 errors, caching them locally."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.allow_stretch = True
        self.keep_ratio = True

    def on_source(self, instance, value):
        if not value:
            return
        if value.startswith("http://") or value.startswith("https://"):
            self.load_remote_image(value)

    def load_remote_image(self, url):
        app = MDApp.get_running_app()
        cache_dir = os.path.join(app.user_data_dir, "image_cache") if app else "image_cache"
        if not os.path.exists(cache_dir):
            try:
                os.makedirs(cache_dir, exist_ok=True)
            except Exception as e:
                print(f"UAAsyncImage: Error creating cache directory: {e}")
            
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        ext = url.split(".")[-1].split("?")[0]
        if len(ext) > 4 or not ext.isalnum():
            ext = "png"
        cache_path = os.path.join(cache_dir, f"{url_hash}.{ext}")
        
        if os.path.exists(cache_path):
            self.source = cache_path
            return
            
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
        }
        
        def on_success(req, result):
            try:
                with open(cache_path, "wb") as f:
                    f.write(req.resp_body)
                self.source = cache_path
                self.reload()
            except Exception as e:
                print(f"UAAsyncImage: Error saving cache file: {e}")
                
        def on_failure(req, result):
            print(f"UAAsyncImage: Failed to download image {url} (code {req.resp_status})")
            
        def on_error(req, error):
            print(f"UAAsyncImage: Error downloading image {url}: {error}")
            
        UrlRequest(url, on_success=on_success, on_failure=on_failure, on_error=on_error, req_headers=headers)

Factory.register('UAAsyncImage', cls=UAAsyncImage)


class FlagWidget(Widget):
    country = StringProperty("Global (All)")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self.draw_flag, size=self.draw_flag, country=self.draw_flag)
        
    def draw_flag(self, *args):
        self.canvas.before.clear()
        x, y = self.pos
        w, h = self.size
        if w <= 0 or h <= 0:
            return
            
        c = self.country.lower()
        with self.canvas.before:
            if "japan" in c:
                # White flag with red circle
                Color(1, 1, 1, 1)
                Rectangle(pos=(x, y), size=(w, h))
                Color(0.9, 0.1, 0.1, 1)
                r = min(w, h) * 0.55
                Ellipse(pos=(x + (w - r) / 2, y + (h - r) / 2), size=(r, r))
            elif "usa" in c:
                # USA flag representation
                Color(1, 1, 1, 1)
                Rectangle(pos=(x, y), size=(w, h))
                Color(0.9, 0.1, 0.1, 1)
                stripe_h = h / 7
                for i in range(0, 7, 2):
                    Rectangle(pos=(x, y + i * stripe_h), size=(w, stripe_h))
                # Blue canton
                Color(0.1, 0.2, 0.6, 1)
                Rectangle(pos=(x, y + h * 3/7), size=(w * 0.45, h * 4/7))
            elif "france" in c:
                # Blue, White, Red vertical bands
                Color(0.05, 0.15, 0.45, 1)
                Rectangle(pos=(x, y), size=(w/3, h))
                Color(1, 1, 1, 1)
                Rectangle(pos=(x + w/3, y), size=(w/3, h))
                Color(0.9, 0.1, 0.1, 1)
                Rectangle(pos=(x + 2*w/3, y), size=(w/3, h))
            elif "spain" in c:
                # Red, Yellow, Red horizontal bands
                Color(0.9, 0.1, 0.1, 1)
                Rectangle(pos=(x, y), size=(w, h))
                Color(1, 0.8, 0, 1)
                Rectangle(pos=(x, y + h/4), size=(w, h/2))
            elif "germany" in c:
                # Black, Red, Gold horizontal bands
                Color(0.1, 0.1, 0.1, 1)
                Rectangle(pos=(x, y + 2*h/3), size=(w, h/3))
                Color(0.9, 0.1, 0.1, 1)
                Rectangle(pos=(x, y + h/3), size=(w, h/3))
                Color(1, 0.8, 0, 1)
                Rectangle(pos=(x, y), size=(w, h/3))
            elif "south korea" in c or "korea" in c:
                # White background with red/blue taegeuk
                Color(1, 1, 1, 1)
                Rectangle(pos=(x, y), size=(w, h))
                r = min(w, h) * 0.55
                cx = x + w / 2
                cy = y + h / 2
                Color(0.9, 0.1, 0.1, 1)
                Ellipse(pos=(cx - r/2, cy - r/2), size=(r, r), angle_start=0, angle_end=180)
                Color(0.1, 0.2, 0.6, 1)
                Ellipse(pos=(cx - r/2, cy - r/2), size=(r, r), angle_start=180, angle_end=360)
            elif "uk" in c or "united kingdom" in c or "britain" in c:
                # Blue background with red/white cross
                Color(0.1, 0.2, 0.6, 1)
                Rectangle(pos=(x, y), size=(w, h))
                Color(1, 1, 1, 1)
                Rectangle(pos=(x + w*0.4, y), size=(w*0.2, h))
                Rectangle(pos=(x, y + h*0.4), size=(w, h*0.2))
                Color(0.9, 0.1, 0.1, 1)
                Rectangle(pos=(x + w*0.45, y), size=(w*0.1, h))
                Rectangle(pos=(x, y + h*0.45), size=(w, h*0.1))
            elif "india" in c:
                # Saffron, White, Green horizontal bands
                Color(1.0, 0.6, 0.2, 1)
                Rectangle(pos=(x, y + 2*h/3), size=(w, h/3))
                Color(1, 1, 1, 1)
                Rectangle(pos=(x, y + h/3), size=(w, h/3))
                Color(0.15, 0.6, 0.15, 1)
                Rectangle(pos=(x, y), size=(w, h/3))
                Color(0.1, 0.2, 0.6, 1)
                r = h / 4
                Ellipse(pos=(x + (w - r)/2, y + (h - r)/2), size=(r, r))
            else:
                # Global (All): Light blue earth circle
                Color(0.85, 0.93, 1.0, 1.0)
                Rectangle(pos=(x, y), size=(w, h))
                Color(0.1, 0.45, 0.85, 0.7)
                r = min(w, h) * 0.7
                Ellipse(pos=(x + (w - r)/2, y + (h - r)/2), size=(r, r))
                Color(1, 1, 1, 0.5)
                Line(circle=(x + w/2, y + h/2, r/2, 0, 360), width=1)


Factory.register('FlagWidget', cls=FlagWidget)


# ==================== KV INTERFACE DESIGN ====================
# Complete layout declaration in Kivy string language
KV = """
#:import SmoothScrollEffect __main__.SmoothScrollEffect
#:import FlagWidget __main__.FlagWidget
<ResponsiveScrollView>:
    effect_cls: SmoothScrollEffect
    scroll_wheel_distance: dp(40)
    scroll_type: ['content']
    scroll_distance: dp(5)
    scroll_timeout: 1000

<SafeIconButton@MDCard>:
    icon: ""
    icon_color: 0.1, 0.1, 0.12, 1
    icon_size: "24sp"
    size_hint: None, None
    size: dp(40), dp(40)
    radius: [dp(10)]
    md_bg_color: 0, 0, 0, 0
    line_color: 0, 0, 0, 0
    line_width: 1
    elevation: 0
    ripple_behavior: True
    MDIcon:
        icon: root.icon
        theme_text_color: "Custom"
        text_color: root.icon_color
        font_size: root.icon_size
        pos_hint: {"center_x": 0.5, "center_y": 0.5}
        halign: "center"

ScreenManager:
    id: screen_manager

    Screen:
        name: "login_screen"
        MDFloatLayout:
            md_bg_color: 0.96, 0.97, 0.98, 1

            Widget:
                canvas.before:
                    Color:
                        rgba: 1.0, 0.42, 0.36, 0.05
                    Ellipse:
                        pos: dp(-100), dp(100)
                        size: dp(400), dp(400)
                    Color:
                        rgba: 0.0, 0.55, 1.0, 0.04
                    Ellipse:
                        pos: dp(200), dp(-100)
                        size: dp(400), dp(400)

            ResponsiveScrollView:
                do_scroll_x: False
                do_scroll_y: True
                pos_hint: {"center_x": 0.5, "center_y": 0.5}
                size_hint: (1, 1)

                MDBoxLayout:
                    orientation: 'vertical'
                    padding: dp(24)
                    spacing: dp(20)
                    size_hint_y: None
                    height: self.minimum_height
                    pos_hint: {"center_x": 0.5}

                    Widget:
                        size_hint_y: None
                        height: dp(20)

                    MDBoxLayout:
                        orientation: 'vertical'
                        size_hint_y: None
                        height: self.minimum_height
                        spacing: dp(8)
                        pos_hint: {"center_x": 0.5}

                        MDCard:
                            size_hint: (None, None)
                            size: (80, 80)
                            radius: [24, 24, 24, 24]
                            md_bg_color: 1.0, 0.42, 0.36, 0.1
                            line_color: 1.0, 0.42, 0.36, 0.2
                            line_width: 1
                            pos_hint: {"center_x": 0.5}
                            elevation: 0

                            MDIcon:
                                icon: "sheep"
                                theme_text_color: "Custom"
                                text_color: 1.0, 0.42, 0.36, 1
                                pos_hint: {"center_x": 0.5, "center_y": 0.5}
                                halign: "center"
                                font_size: "38sp"

                        MDLabel:
                            text: "PharmaGlobe"
                            font_style: "H4"
                            bold: True
                            halign: "center"
                            theme_text_color: "Custom"
                            text_color: 0.1, 0.1, 0.12, 1
                            size_hint_y: None
                            height: self.texture_size[1]

                        MDLabel:
                            text: "Your Global Travel Health Companion"
                            font_style: "Caption"
                            halign: "center"
                            theme_text_color: "Custom"
                            text_color: 0.5, 0.55, 0.55, 1
                            italic: True
                            size_hint_y: None
                            height: self.texture_size[1]

                    MDCard:
                        orientation: 'vertical'
                        size_hint_y: None
                        height: self.minimum_height
                        padding: dp(20)
                        spacing: dp(14)
                        radius: [24, 24, 24, 24]
                        md_bg_color: 1, 1, 1, 1
                        line_color: 0.9, 0.91, 0.94, 1
                        line_width: 1
                        pos_hint: {"center_x": 0.5}
                        elevation: 2

                        MDLabel:
                            text: "Login / Register"
                            font_style: "Subtitle1"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: 0.1, 0.1, 0.12, 1
                            size_hint_y: None
                            height: self.texture_size[1]

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(56)
                            spacing: dp(10)

                            MDTextField:
                                id: phone_code
                                text: "+81"
                                size_hint_x: 0.25
                                mode: "rectangle"
                                halign: "center"
                                line_color_focus: 1.0, 0.42, 0.36, 1
                                text_color_focus: 0.1, 0.1, 0.12, 1
                                hint_text_color_focus: 0.5, 0.55, 0.55, 1

                            MDTextField:
                                id: phone_input
                                hint_text: "Mobile Number"
                                size_hint_x: 0.75
                                mode: "rectangle"
                                input_filter: "int"
                                line_color_focus: 1.0, 0.42, 0.36, 1
                                text_color_focus: 0.1, 0.1, 0.12, 1

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(56)
                            spacing: dp(10)

                            MDIcon:
                                icon: "airplane"
                                theme_text_color: "Custom"
                                text_color: 1.0, 0.42, 0.36, 1
                                pos_hint: {"center_y": 0.5}
                                size_hint_x: None
                                width: dp(24)

                            MDTextField:
                                id: login_destination_input
                                text: "Japan"
                                hint_text: "Travel Destination"
                                readonly: True
                                mode: "rectangle"
                                line_color_focus: 1.0, 0.42, 0.36, 1
                                text_color_focus: 0.1, 0.1, 0.12, 1
                                on_focus: if self.focus: app.open_login_destination_menu(self)

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(56)
                            spacing: dp(10)

                            MDIcon:
                                icon: "translate"
                                theme_text_color: "Custom"
                                text_color: 1.0, 0.42, 0.36, 1
                                pos_hint: {"center_y": 0.5}
                                size_hint_x: None
                                width: dp(24)

                            MDTextField:
                                id: login_language_input
                                text: "English"
                                hint_text: "Preferred Language"
                                readonly: True
                                mode: "rectangle"
                                line_color_focus: 1.0, 0.42, 0.36, 1
                                text_color_focus: 0.1, 0.1, 0.12, 1
                                on_focus: if self.focus: app.open_login_language_menu(self)

                        MDRaisedButton:
                            text: "Send OTP & Log In"
                            md_bg_color: 1.0, 0.42, 0.36, 1
                            text_color: 1, 1, 1, 1
                            bold: True
                            size_hint_x: 1
                            height: dp(44)
                            on_release: app.handle_login("mobile", phone_input.text)

                        MDLabel:
                            text: "— OR CONNECT WITH —"
                            halign: "center"
                            theme_text_color: "Custom"
                            text_color: 0.5, 0.55, 0.55, 1
                            font_style: "Caption"
                            size_hint_y: None
                            height: dp(20)

                        MDBoxLayout:
                            orientation: 'horizontal'
                            spacing: dp(14)
                            size_hint_y: None
                            height: dp(48)
                            pos_hint: {"center_x": 0.5}
                            adaptive_width: True

                            MDCard:
                                size_hint: None, None
                                size: dp(48), dp(48)
                                radius: [dp(14)]
                                md_bg_color: 0.94, 0.94, 0.96, 1
                                elevation: 0
                                ripple_behavior: True
                                on_release: app.handle_login("Google")
                                AnchorLayout:
                                    anchor_x: "center"
                                    anchor_y: "center"
                                    MDIcon:
                                        icon: "google"
                                        theme_text_color: "Custom"
                                        text_color: 0.85, 0.25, 0.2, 1
                                        size_hint: None, None
                                        size: dp(24), dp(24)

                            MDCard:
                                size_hint: None, None
                                size: dp(48), dp(48)
                                radius: [dp(14)]
                                md_bg_color: 0.94, 0.94, 0.96, 1
                                elevation: 0
                                ripple_behavior: True
                                on_release: app.handle_login("Facebook")
                                AnchorLayout:
                                    anchor_x: "center"
                                    anchor_y: "center"
                                    MDIcon:
                                        icon: "facebook"
                                        theme_text_color: "Custom"
                                        text_color: 0.2, 0.4, 0.8, 1
                                        size_hint: None, None
                                        size: dp(24), dp(24)

                            MDCard:
                                size_hint: None, None
                                size: dp(48), dp(48)
                                radius: [dp(14)]
                                md_bg_color: 0.94, 0.94, 0.96, 1
                                elevation: 0
                                ripple_behavior: True
                                on_release: app.handle_login("Apple")
                                AnchorLayout:
                                    anchor_x: "center"
                                    anchor_y: "center"
                                    MDIcon:
                                        icon: "apple"
                                        theme_text_color: "Custom"
                                        text_color: 0.1, 0.1, 0.12, 1
                                        size_hint: None, None
                                        size: dp(24), dp(24)

                            MDCard:
                                size_hint: None, None
                                size: dp(48), dp(48)
                                radius: [dp(14)]
                                md_bg_color: 0.94, 0.94, 0.96, 1
                                elevation: 0
                                ripple_behavior: True
                                on_release: app.handle_login("Yahoo")
                                AnchorLayout:
                                    anchor_x: "center"
                                    anchor_y: "center"
                                    MDIcon:
                                        icon: "yahoo"
                                        theme_text_color: "Custom"
                                        text_color: 0.5, 0.2, 0.75, 1
                                        size_hint: None, None
                                        size: dp(24), dp(24)

                    MDTextButton:
                        text: "Continue as Guest"
                        theme_text_color: "Custom"
                        text_color: 1.0, 0.42, 0.36, 1
                        pos_hint: {"center_x": 0.5}
                        font_style: "Button"
                        on_release: app.handle_login("Guest")

                    Widget:
                        size_hint_y: None
                        height: dp(20)

            MDBoxLayout:
                id: login_loader
                orientation: 'vertical'
                pos_hint: {"x": 0, "y": 0}
                size_hint: (1, 1) if self.opacity > 0 else (None, None)
                size: (self.parent.width, self.parent.height) if self.opacity > 0 else (0, 0)
                md_bg_color: 1, 1, 1, 0.9
                spacing: dp(15)
                padding: dp(20)
                opacity: 0
                disabled: True

                Widget:
                    size_hint_y: 0.35

                MDSpinner:
                    size_hint: (None, None)
                    size: (50, 50)
                    pos_hint: {"center_x": 0.5}
                    color: 1.0, 0.42, 0.36, 1
                    active: True

                MDLabel:
                    id: loader_text
                    text: "Connecting to secure servers..."
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 1.0, 0.42, 0.36, 1
                    font_style: "Subtitle1"
                    bold: True

                Widget:
                    size_hint_y: 0.35

    Screen:
        name: "register_screen"
        MDFloatLayout:
            md_bg_color: 0.96, 0.97, 0.98, 1

            Widget:
                canvas.before:
                    Color:
                        rgba: 1.0, 0.42, 0.36, 0.05
                    Ellipse:
                        pos: dp(-100), dp(100)
                        size: dp(400), dp(400)
                    Color:
                        rgba: 0.0, 0.55, 1.0, 0.04
                    Ellipse:
                        pos: dp(200), dp(-100)
                        size: dp(400), dp(400)

            ResponsiveScrollView:
                do_scroll_x: False
                do_scroll_y: True
                pos_hint: {"center_x": 0.5, "center_y": 0.5}
                size_hint: (1, 1)

                MDBoxLayout:
                    orientation: 'vertical'
                    padding: dp(24)
                    spacing: dp(14)
                    size_hint_y: None
                    height: self.minimum_height
                    pos_hint: {"center_x": 0.5}

                    MDBoxLayout:
                        orientation: 'horizontal'
                        size_hint_y: None
                        height: dp(48)
                        spacing: dp(10)

                        MDIconButton:
                            icon: "arrow-left"
                            pos_hint: {"center_y": 0.5}
                            on_release:
                                root.transition.direction = "right"
                                root.current = "login_screen"

                        MDLabel:
                            text: "Create Account"
                            font_style: "H5"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: 0.1, 0.1, 0.12, 1
                            pos_hint: {"center_y": 0.5}

                    MDCard:
                        orientation: 'vertical'
                        size_hint_y: None
                        height: self.minimum_height
                        padding: dp(20)
                        spacing: dp(12)
                        radius: [24, 24, 24, 24]
                        md_bg_color: 1, 1, 1, 1
                        line_color: 0.9, 0.91, 0.94, 1
                        line_width: 1
                        pos_hint: {"center_x": 0.5}
                        elevation: 2

                        MDTextField:
                            id: reg_first_name
                            hint_text: "First Name"
                            mode: "rectangle"
                            line_color_focus: 1.0, 0.42, 0.36, 1
                            text_color_focus: 0.1, 0.1, 0.12, 1

                        MDTextField:
                            id: reg_middle_name
                            hint_text: "Middle Name (Optional)"
                            mode: "rectangle"
                            line_color_focus: 1.0, 0.42, 0.36, 1
                            text_color_focus: 0.1, 0.1, 0.12, 1

                        MDTextField:
                            id: reg_surname
                            hint_text: "Surname"
                            mode: "rectangle"
                            line_color_focus: 1.0, 0.42, 0.36, 1
                            text_color_focus: 0.1, 0.1, 0.12, 1

                        MDTextField:
                            id: reg_username
                            hint_text: "Username"
                            mode: "rectangle"
                            line_color_focus: 1.0, 0.42, 0.36, 1
                            text_color_focus: 0.1, 0.1, 0.12, 1

                        MDTextField:
                            id: reg_gmail
                            hint_text: "Gmail / Email Address"
                            mode: "rectangle"
                            line_color_focus: 1.0, 0.42, 0.36, 1
                            text_color_focus: 0.1, 0.1, 0.12, 1

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(56)
                            spacing: dp(10)

                            MDTextField:
                                id: reg_age
                                hint_text: "Age"
                                input_filter: "int"
                                mode: "rectangle"
                                line_color_focus: 1.0, 0.42, 0.36, 1
                                text_color_focus: 0.1, 0.1, 0.12, 1
                                size_hint_x: 0.3

                            MDTextField:
                                id: reg_dob
                                hint_text: "Date of Birth (YYYY-MM-DD)"
                                mode: "rectangle"
                                line_color_focus: 1.0, 0.42, 0.36, 1
                                text_color_focus: 0.1, 0.1, 0.12, 1
                                size_hint_x: 0.7

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(56)
                            spacing: dp(10)

                            MDTextField:
                                id: reg_height
                                hint_text: "Height (cm) - Optional"
                                mode: "rectangle"
                                line_color_focus: 1.0, 0.42, 0.36, 1
                                text_color_focus: 0.1, 0.1, 0.12, 1
                                size_hint_x: 0.5

                            MDTextField:
                                id: reg_weight
                                hint_text: "Weight (kg) - Optional"
                                mode: "rectangle"
                                line_color_focus: 1.0, 0.42, 0.36, 1
                                text_color_focus: 0.1, 0.1, 0.12, 1
                                size_hint_x: 0.5

                        MDTextField:
                            id: reg_password
                            hint_text: "New Password"
                            password: True
                            mode: "rectangle"
                            line_color_focus: 1.0, 0.42, 0.36, 1
                            text_color_focus: 0.1, 0.1, 0.12, 1

                        MDTextField:
                            id: reg_confirm_password
                            hint_text: "Confirm Password"
                            password: True
                            mode: "rectangle"
                            line_color_focus: 1.0, 0.42, 0.36, 1
                            text_color_focus: 0.1, 0.1, 0.12, 1

                        MDRaisedButton:
                            text: "Create Account & Login"
                            md_bg_color: 0.0, 0.55, 1.0, 1
                            text_color: 1, 1, 1, 1
                            bold: True
                            size_hint_x: 1
                            height: dp(44)
                            on_release: app.process_new_user_registration()

    Screen:
        name: "main_screen"
        MDFloatLayout:
            md_bg_color: 0.96, 0.97, 0.98, 1

            MDBoxLayout:
                orientation: 'vertical'
                size_hint: 1, 1

                ScreenManager:
                    id: tab_manager
                    size_hint_y: 1

                    Screen:
                        name: "home"
                        MDBoxLayout:
                            orientation: 'vertical'
                            
                            MDBoxLayout:
                                size_hint_y: None
                                height: dp(56)
                                padding: [dp(12), 0, dp(12), 0]
                                spacing: dp(6)
                                md_bg_color: 0.96, 0.97, 0.98, 1
                                
                                SafeIconButton:
                                    icon: "cog-outline"
                                    icon_color: 0.1, 0.1, 0.12, 1
                                    size_hint: None, None
                                    size: dp(40), dp(40)
                                    pos_hint: {"center_y": 0.5}
                                    on_release: app.switch_tab("my_page")

                                MDCard:
                                    size_hint: None, None
                                    size: dp(90), dp(32)
                                    radius: [dp(8)]
                                    md_bg_color: 1, 1, 1, 1
                                    line_color: 0.9, 0.91, 0.94, 1
                                    line_width: 1
                                    elevation: 0
                                    pos_hint: {"center_y": 0.5}
                                    padding: [dp(4), 0, dp(4), 0]
                                    MDBoxLayout:
                                        orientation: 'horizontal'
                                        spacing: dp(4)
                                        MDCard:
                                            size_hint: None, None
                                            size: dp(22), dp(22)
                                            radius: [dp(6)]
                                            md_bg_color: 1.0, 0.42, 0.36, 1.0
                                            pos_hint: {"center_y": 0.5}
                                            elevation: 0
                                            MDLabel:
                                                text: "P"
                                                font_style: "Caption"
                                                bold: True
                                                halign: "center"
                                                valign: "middle"
                                                theme_text_color: "Custom"
                                                text_color: 1, 1, 1, 1
                                        MDLabel:
                                            text: str(app.user_points)
                                            font_style: "Body2"
                                            bold: True
                                            theme_text_color: "Custom"
                                            text_color: 0.0, 0.55, 1.0, 1.0
                                            valign: "middle"

                                Widget:

                                MDLabel:
                                    text: "PharmaGlobe"
                                    font_style: "Subtitle1"
                                    bold: True
                                    halign: "center"
                                    theme_text_color: "Custom"
                                    text_color: 1.0, 0.42, 0.36, 1.0
                                    pos_hint: {"center_y": 0.5}
                                    size_hint_x: None
                                    width: dp(110)

                                Widget:

                                MDFloatLayout:
                                    size_hint: None, None
                                    size: dp(40), dp(40)
                                    pos_hint: {"center_y": 0.5}
                                    SafeIconButton:
                                        icon: "bell-outline"
                                        icon_color: 0.1, 0.1, 0.12, 1
                                        pos_hint: {"center_x": 0.5, "center_y": 0.5}
                                        on_release: app.show_dialog("Notifications", "You have 68 unread notifications from Payke hub.")
                                    MDCard:
                                        size_hint: None, None
                                        size: dp(16), dp(16)
                                        radius: [dp(4)]
                                        md_bg_color: 1.0, 0.3, 0.3, 1
                                        elevation: 0
                                        pos_hint: {"center_x": 0.75, "center_y": 0.75}
                                        MDLabel:
                                            text: "68"
                                            font_style: "Caption"
                                            font_size: "9sp"
                                            bold: True
                                            halign: "center"
                                            valign: "middle"
                                            theme_text_color: "Custom"
                                            text_color: 1, 1, 1, 1

                                MDCard:
                                    size_hint: None, None
                                    size: dp(34), dp(34)
                                    radius: [dp(10)]
                                    md_bg_color: 1.0, 0.9, 0.88, 1
                                    line_color: 1.0, 0.42, 0.36, 0.3
                                    line_width: 1
                                    elevation: 0
                                    pos_hint: {"center_y": 0.5}
                                    ripple_behavior: True
                                    on_release: app.switch_tab("my_page")
                                    MDIcon:
                                        icon: "sheep"
                                        theme_text_color: "Custom"
                                        text_color: 1.0, 0.42, 0.36, 1
                                        font_size: "20sp"
                                        pos_hint: {"center_x": 0.5, "center_y": 0.5}
                                        halign: "center"

                            ResponsiveScrollView:
                                id: home_scroll
                                do_scroll_x: False
                                MDBoxLayout:
                                    orientation: 'vertical'
                                    padding: dp(16)
                                    spacing: dp(18)
                                    size_hint_y: None
                                    height: self.minimum_height

                                    MDCard:
                                        size_hint_y: None
                                        height: dp(48)
                                        radius: [dp(14)]
                                        md_bg_color: 1, 1, 1, 1
                                        line_color: 0.9, 0.91, 0.94, 1
                                        elevation: 1
                                        padding: [dp(16), 0, dp(16), 0]
                                        ripple_behavior: True
                                        on_release: app.switch_to_search_tab_with_focus()
                                        MDBoxLayout:
                                            orientation: 'horizontal'
                                            spacing: dp(10)
                                            MDIcon:
                                                icon: "magnify"
                                                theme_text_color: "Custom"
                                                text_color: 0.5, 0.55, 0.55, 1
                                                pos_hint: {"center_y": 0.5}
                                            MDLabel:
                                                text: "Search by product name, ingredient, symptom..."
                                                theme_text_color: "Custom"
                                                text_color: 0.65, 0.65, 0.75, 1
                                                font_style: "Body2"
                                                valign: "middle"

                                    MDCard:
                                        orientation: 'vertical'
                                        size_hint_y: None
                                        height: dp(190)
                                        radius: [dp(20)]
                                        md_bg_color: 1, 1, 1, 1
                                        line_color: 0.9, 0.91, 0.94, 1
                                        elevation: 1
                                        padding: [dp(8), dp(12), dp(8), dp(10)]
                                        spacing: dp(10)

                                        MDGridLayout:
                                            cols: 4
                                            rows: 2
                                            spacing: dp(4)

                                            MDCard:
                                                orientation: 'vertical'
                                                ripple_behavior: True
                                                elevation: 0
                                                md_bg_color: 0, 0, 0, 0
                                                on_release: app.switch_tab("scanner")
                                                MDIcon:
                                                    icon: "barcode-scan"
                                                    theme_text_color: "Custom"
                                                    text_color: 1.0, 0.42, 0.36, 1
                                                    font_size: "24sp"
                                                    pos_hint: {"center_x": 0.5}
                                                    halign: "center"
                                                MDLabel:
                                                    text: "Scan"
                                                    font_style: "Caption"
                                                    halign: "center"
                                                    theme_text_color: "Custom"
                                                    text_color: 0.1, 0.1, 0.12, 1
                                                    size_hint_y: None
                                                    height: dp(16)

                                            MDCard:
                                                orientation: 'vertical'
                                                ripple_behavior: True
                                                elevation: 0
                                                md_bg_color: 0, 0, 0, 0
                                                on_release: app.switch_tab("chat")
                                                MDIcon:
                                                    icon: "chat-processing"
                                                    theme_text_color: "Custom"
                                                    text_color: 0.0, 0.55, 1.0, 1
                                                    font_size: "24sp"
                                                    pos_hint: {"center_x": 0.5}
                                                    halign: "center"
                                                MDLabel:
                                                    text: "AI Chat"
                                                    font_style: "Caption"
                                                    halign: "center"
                                                    theme_text_color: "Custom"
                                                    text_color: 0.1, 0.1, 0.12, 1
                                                    size_hint_y: None
                                                    height: dp(16)

                                            MDCard:
                                                orientation: 'vertical'
                                                ripple_behavior: True
                                                elevation: 0
                                                md_bg_color: 0, 0, 0, 0
                                                on_release: app.switch_tab("search")
                                                MDIcon:
                                                    icon: "magnify"
                                                    theme_text_color: "Custom"
                                                    text_color: 0.7, 0.4, 0.95, 1
                                                    font_size: "24sp"
                                                    pos_hint: {"center_x": 0.5}
                                                    halign: "center"
                                                MDLabel:
                                                    text: "Search"
                                                    font_style: "Caption"
                                                    halign: "center"
                                                    theme_text_color: "Custom"
                                                    text_color: 0.1, 0.1, 0.12, 1
                                                    size_hint_y: None
                                                    height: dp(16)

                                            MDCard:
                                                orientation: 'vertical'
                                                ripple_behavior: True
                                                elevation: 0
                                                md_bg_color: 0, 0, 0, 0
                                                on_release: app.switch_tab("coupons")
                                                MDIcon:
                                                    icon: "ticket-percent"
                                                    theme_text_color: "Custom"
                                                    text_color: 1.0, 0.6, 0.1, 1
                                                    font_size: "24sp"
                                                    pos_hint: {"center_x": 0.5}
                                                    halign: "center"
                                                MDLabel:
                                                    text: "Coupons"
                                                    font_style: "Caption"
                                                    halign: "center"
                                                    theme_text_color: "Custom"
                                                    text_color: 0.1, 0.1, 0.12, 1
                                                    size_hint_y: None
                                                    height: dp(16)

                                            MDCard:
                                                orientation: 'vertical'
                                                ripple_behavior: True
                                                elevation: 0
                                                md_bg_color: 0, 0, 0, 0
                                                on_release: app.switch_tab("articles")
                                                MDIcon:
                                                    icon: "card-text"
                                                    theme_text_color: "Custom"
                                                    text_color: 0.2, 0.8, 0.2, 1
                                                    font_size: "24sp"
                                                    pos_hint: {"center_x": 0.5}
                                                    halign: "center"
                                                MDLabel:
                                                    text: "Articles"
                                                    font_style: "Caption"
                                                    halign: "center"
                                                    theme_text_color: "Custom"
                                                    text_color: 0.1, 0.1, 0.12, 1
                                                    size_hint_y: None
                                                    height: dp(16)

                                            MDCard:
                                                orientation: 'vertical'
                                                ripple_behavior: True
                                                elevation: 0
                                                md_bg_color: 0, 0, 0, 0
                                                on_release: app.switch_tab("ranking")
                                                MDIcon:
                                                    icon: "trophy"
                                                    theme_text_color: "Custom"
                                                    text_color: 1.0, 0.8, 0.2, 1
                                                    font_size: "24sp"
                                                    pos_hint: {"center_x": 0.5}
                                                    halign: "center"
                                                MDLabel:
                                                    text: "Ranking"
                                                    font_style: "Caption"
                                                    halign: "center"
                                                    theme_text_color: "Custom"
                                                    text_color: 0.1, 0.1, 0.12, 1
                                                    size_hint_y: None
                                                    height: dp(16)

                                            MDCard:
                                                orientation: 'vertical'
                                                ripple_behavior: True
                                                elevation: 0
                                                md_bg_color: 0, 0, 0, 0
                                                on_release: app.switch_tab("wishlist")
                                                MDIcon:
                                                    icon: "bookmark"
                                                    theme_text_color: "Custom"
                                                    text_color: 0.85, 0.25, 0.2, 1
                                                    font_size: "24sp"
                                                    pos_hint: {"center_x": 0.5}
                                                    halign: "center"
                                                MDLabel:
                                                    text: "Wishlist"
                                                    font_style: "Caption"
                                                    halign: "center"
                                                    theme_text_color: "Custom"
                                                    text_color: 0.1, 0.1, 0.12, 1
                                                    size_hint_y: None
                                                    height: dp(16)

                                            MDCard:
                                                orientation: 'vertical'
                                                ripple_behavior: True
                                                elevation: 0
                                                md_bg_color: 0, 0, 0, 0
                                                on_release: app.switch_tab("my_page")
                                                MDIcon:
                                                    icon: "cog"
                                                    theme_text_color: "Custom"
                                                    text_color: 0.5, 0.55, 0.55, 1
                                                    font_size: "24sp"
                                                    pos_hint: {"center_x": 0.5}
                                                    halign: "center"
                                                MDLabel:
                                                    text: "Settings"
                                                    font_style: "Caption"
                                                    halign: "center"
                                                    theme_text_color: "Custom"
                                                    text_color: 0.1, 0.1, 0.12, 1
                                                    size_hint_y: None
                                                    height: dp(16)

                                        MDBoxLayout:
                                            size_hint_y: None
                                            height: dp(10)
                                            pos_hint: {"center_x": 0.5}
                                            adaptive_width: True
                                            spacing: dp(6)
                                            MDCard:
                                                size_hint: None, None
                                                size: dp(12), dp(4)
                                                radius: [dp(1)]
                                                md_bg_color: 1.0, 0.42, 0.36, 1
                                                elevation: 0
                                            MDCard:
                                                size_hint: None, None
                                                size: dp(4), dp(4)
                                                radius: [dp(1)]
                                                md_bg_color: 0.8, 0.8, 0.8, 1
                                                elevation: 0

                                    MDCard:
                                        orientation: 'horizontal'
                                        size_hint_y: None
                                        height: dp(135)
                                        radius: [dp(20)]
                                        md_bg_color: 1.0, 0.95, 0.93, 1
                                        line_color: 1.0, 0.85, 0.8, 1
                                        line_width: 1
                                        elevation: 0
                                        padding: dp(14)
                                        spacing: dp(10)

                                        MDBoxLayout:
                                            orientation: 'vertical'
                                            spacing: dp(3)
                                            size_hint_x: 0.65

                                            MDLabel:
                                                text: "LUCKY ROULETTE"
                                                font_style: "Overline"
                                                bold: True
                                                theme_text_color: "Custom"
                                                text_color: 1.0, 0.42, 0.36, 1

                                            MDLabel:
                                                text: "Up to 3 times a day!"
                                                font_style: "Subtitle2"
                                                bold: True
                                                theme_text_color: "Custom"
                                                text_color: 0.1, 0.1, 0.12, 1

                                            MDLabel:
                                                text: "Spin to win extra points!"
                                                font_style: "Caption"
                                                theme_text_color: "Custom"
                                                text_color: 0.4, 0.4, 0.45, 1

                                            Widget:

                                            MDRaisedButton:
                                                text: "Spin Now"
                                                md_bg_color: 1.0, 0.42, 0.36, 1
                                                text_color: 1, 1, 1, 1
                                                font_style: "Button"
                                                bold: True
                                                size_hint_y: None
                                                height: dp(30)
                                                on_release: app.spin_roulette()

                                        MDCard:
                                            size_hint: None, None
                                            size: dp(90), dp(90)
                                            radius: [dp(24)]
                                            md_bg_color: 1.0, 0.85, 0.8, 0.4
                                            elevation: 0
                                            pos_hint: {"center_y": 0.5}
                                            MDIcon:
                                                icon: "clover"
                                                theme_text_color: "Custom"
                                                text_color: 1.0, 0.42, 0.36, 1
                                                font_size: "38sp"
                                                pos_hint: {"center_x": 0.5, "center_y": 0.5}
                                                halign: "center"

                                    MDCard:
                                        orientation: 'horizontal'
                                        size_hint_y: None
                                        height: dp(100)
                                        radius: [dp(20)]
                                        md_bg_color: 0.9, 0.95, 1.0, 1
                                        line_color: 0.8, 0.9, 1.0, 1
                                        line_width: 1
                                        elevation: 0
                                        padding: dp(14)
                                        spacing: dp(10)

                                        MDBoxLayout:
                                            orientation: 'vertical'
                                            spacing: dp(4)
                                            size_hint_x: 0.7

                                            MDLabel:
                                                text: "Earn points by playing games!"
                                                font_style: "Subtitle2"
                                                bold: True
                                                theme_text_color: "Custom"
                                                text_color: 0.0, 0.55, 1.0, 1

                                            Widget:

                                            MDTextButton:
                                                text: "Learn More >"
                                                theme_text_color: "Custom"
                                                text_color: 0.0, 0.55, 1.0, 1
                                                bold: True
                                                on_release: app.play_game()

                                        MDIcon:
                                            icon: "controller-classic"
                                            theme_text_color: "Custom"
                                            text_color: 0.0, 0.55, 1.0, 1
                                            font_size: "36sp"
                                            pos_hint: {"center_y": 0.5}

                                    MDLabel:
                                        text: "Recommended for you"
                                        font_style: "Subtitle1"
                                        bold: True
                                        theme_text_color: "Custom"
                                        text_color: 0.1, 0.1, 0.12, 1
                                        size_hint_y: None
                                        height: dp(24)

                                    MDGridLayout:
                                        id: directory_grid
                                        cols: 1
                                        adaptive_height: True
                                        spacing: dp(12)

                    Screen:
                        name: "wishlist"
                        MDBoxLayout:
                            orientation: 'vertical'
                            MDBoxLayout:
                                size_hint_y: None
                                height: dp(56)
                                padding: [dp(8), 0, dp(8), 0]
                                md_bg_color: 1, 1, 1, 1
                                SafeIconButton:
                                    icon: "arrow-left"
                                    on_release: app.switch_tab(app.wishlist_prev_tab)
                                MDLabel:
                                    text: "Wishlist"
                                    font_style: "H6"
                                    bold: True
                                    halign: "center"
                                SafeIconButton:
                                    icon: "bell-outline"
                                    on_release: app.show_dialog("Notifications", "No notifications.")
                            
                            ResponsiveScrollView:
                                MDGridLayout:
                                    id: wishlist_grid
                                    cols: 1
                                    adaptive_height: True
                                    spacing: dp(12)
                                    padding: dp(12)

                    Screen:
                        name: "articles"
                        MDBoxLayout:
                            orientation: 'vertical'
                            MDBoxLayout:
                                size_hint_y: None
                                height: dp(56)
                                padding: [dp(8), 0, dp(8), 0]
                                md_bg_color: 1, 1, 1, 1
                                SafeIconButton:
                                    icon: "home-outline"
                                    on_release: app.switch_tab("home")
                                MDLabel:
                                    text: "Health Articles"
                                    font_style: "H6"
                                    bold: True
                                    halign: "center"
                                SafeIconButton:
                                    icon: "bell-outline"
                                    on_release: app.show_dialog("Notifications", "No notifications.")
                            
                            ResponsiveScrollView:
                                MDGridLayout:
                                    id: articles_grid
                                    cols: 1
                                    adaptive_height: True
                                    spacing: dp(12)
                                    padding: dp(12)

                    Screen:
                        name: "coupons"
                        MDBoxLayout:
                            orientation: 'vertical'
                            MDBoxLayout:
                                size_hint_y: None
                                height: dp(56)
                                padding: [dp(8), 0, dp(8), 0]
                                md_bg_color: 1, 1, 1, 1
                                SafeIconButton:
                                    icon: "home-outline"
                                    on_release: app.switch_tab("home")
                                MDLabel:
                                    text: "Redeem Rewards"
                                    font_style: "H6"
                                    bold: True
                                    halign: "center"
                                SafeIconButton:
                                    icon: "bell-outline"
                                    on_release: app.show_dialog("Notifications", "No notifications.")
                            
                            ResponsiveScrollView:
                                MDGridLayout:
                                    id: coupons_grid
                                    cols: 1
                                    adaptive_height: True
                                    spacing: dp(12)
                                    padding: dp(12)

                    Screen:
                        name: "search"
                        MDBoxLayout:
                            orientation: 'vertical'
                            padding: dp(12)
                            spacing: dp(10)

                            MDBoxLayout:
                                size_hint_y: None
                                height: dp(56)
                                spacing: dp(10)
                                SafeIconButton:
                                    icon: "home-outline"
                                    on_release: app.switch_tab("home")
                                MDLabel:
                                    text: "Search Medicines"
                                    font_style: "Subtitle1"
                                    bold: True

                            MDBoxLayout:
                                size_hint_y: None
                                height: dp(56)
                                spacing: dp(10)

                                MDTextField:
                                    id: search_field
                                    hint_text: "Search name, ingredient, symptom..."
                                    mode: "rectangle"
                                    line_color_focus: 1.0, 0.42, 0.36, 1
                                    size_hint_x: 0.8
                                    on_text_validate: app.execute_search()

                                MDCard:
                                    size_hint: None, None
                                    size: dp(48), dp(48)
                                    radius: [dp(14)]
                                    md_bg_color: 1.0, 0.42, 0.36, 1
                                    elevation: 0
                                    ripple_behavior: True
                                    on_release: app.execute_search()
                                    MDIcon:
                                        icon: "magnify"
                                        theme_text_color: "Custom"
                                        text_color: 1, 1, 1, 1
                                        pos_hint: {"center_x": 0.5, "center_y": 0.5}
                                        halign: "center"

                            MDBoxLayout:
                                size_hint_y: None
                                height: dp(36)
                                spacing: dp(10)
                                MDLabel:
                                    text: "Source:"
                                    theme_text_color: "Secondary"
                                    size_hint_x: 0.25
                                    valign: "middle"
                                MDRaisedButton:
                                    id: search_source_btn
                                    text: "Local Database"
                                    md_bg_color: 0.9, 0.92, 0.94, 1
                                    text_color: 0.1, 0.1, 0.12, 1
                                    size_hint_x: 0.75
                                    on_release: app.toggle_search_source()

                            MDBoxLayout:
                                size_hint_y: None
                                height: dp(46)
                                orientation: 'vertical'
                                spacing: dp(2)
                                ResponsiveScrollView:
                                    do_scroll_y: False
                                    MDBoxLayout:
                                        id: popular_search_chips
                                        orientation: 'horizontal'
                                        adaptive_width: True
                                        spacing: dp(8)
                                        padding: [dp(2), 0, dp(2), 0]

                            ResponsiveScrollView:
                                do_scroll_y: False
                                size_hint_y: None
                                height: dp(44)
                                MDBoxLayout:
                                    id: country_chips_container
                                    orientation: 'horizontal'
                                    adaptive_width: True
                                    spacing: dp(8)
                                    padding: [dp(2), 0, dp(2), 0]

                            ResponsiveScrollView:
                                do_scroll_y: False
                                size_hint_y: None
                                height: dp(44)
                                MDBoxLayout:
                                    id: category_chips_container
                                    orientation: 'horizontal'
                                    adaptive_width: True
                                    spacing: dp(8)
                                    padding: [dp(2), 0, dp(2), 0]

                            ResponsiveScrollView:
                                MDGridLayout:
                                    id: search_grid
                                    cols: 1
                                    adaptive_height: True
                                    spacing: dp(12)

                    Screen:
                        name: "scanner"
                        MDBoxLayout:
                            orientation: 'vertical'
                            padding: dp(12)
                            spacing: dp(10)

                            MDBoxLayout:
                                size_hint_y: None
                                height: dp(46)
                                spacing: dp(10)
                                SafeIconButton:
                                    icon: "home-outline"
                                    on_release: app.switch_tab("home")
                                MDLabel:
                                    text: "Barcode Scanner"
                                    font_style: "Subtitle1"
                                    bold: True

                            MDCard:
                                size_hint_y: 0.6
                                md_bg_color: 0, 0, 0, 1
                                radius: [20, 20, 20, 20]
                                padding: dp(5)
                                BoxLayout:
                                    id: camera_container

                            MDBoxLayout:
                                size_hint_y: 0.4
                                orientation: 'vertical'
                                spacing: dp(10)
                                padding: [dp(10), dp(10), dp(10), 0]

                                MDRaisedButton:
                                    text: "📸 Capture Frame & Scan Barcode"
                                    md_bg_color: 1.0, 0.42, 0.36, 1
                                    text_color: 1, 1, 1, 1
                                    size_hint_x: 1
                                    on_release: app.capture_and_scan()

                                MDLabel:
                                    text: "— OR ENTER MANUALLY —"
                                    halign: "center"
                                    theme_text_color: "Secondary"
                                    font_style: "Caption"

                                MDBoxLayout:
                                    size_hint_y: None
                                    height: dp(56)
                                    spacing: dp(10)

                                    MDTextField:
                                        id: manual_barcode_field
                                        hint_text: "Type barcode number (UPC/EAN)..."
                                        mode: "rectangle"
                                        line_color_focus: 1.0, 0.42, 0.36, 1
                                        size_hint_x: 0.8

                                    MDCard:
                                        size_hint: None, None
                                        size: dp(48), dp(48)
                                        radius: [dp(14)]
                                        md_bg_color: 1.0, 0.42, 0.36, 1
                                        elevation: 0
                                        ripple_behavior: True
                                        on_release: app.execute_manual_scan()
                                        MDIcon:
                                            icon: "arrow-right-bold"
                                            theme_text_color: "Custom"
                                            text_color: 1, 1, 1, 1
                                            pos_hint: {"center_x": 0.5, "center_y": 0.5}
                                            halign: "center"

                    Screen:
                        name: "my_page"
                        MDBoxLayout:
                            orientation: 'vertical'
                            MDBoxLayout:
                                size_hint_y: None
                                height: dp(56)
                                padding: [dp(8), 0, dp(8), 0]
                                md_bg_color: 1, 1, 1, 1
                                SafeIconButton:
                                    icon: "home-outline"
                                    on_release: app.switch_tab("home")
                                MDLabel:
                                    text: "My Page"
                                    font_style: "H6"
                                    bold: True
                                    halign: "center"
                                SafeIconButton:
                                    icon: "bell-outline"
                                    on_release: app.show_dialog("Notifications", "No notifications.")

                            ResponsiveScrollView:
                                do_scroll_x: False
                                MDBoxLayout:
                                    orientation: 'vertical'
                                    padding: dp(16)
                                    spacing: dp(16)
                                    size_hint_y: None
                                    height: self.minimum_height

                                    MDBoxLayout:
                                        orientation: 'horizontal'
                                        size_hint_y: None
                                        height: dp(60)
                                        spacing: dp(15)
                                        pos_hint: {"center_x": 0.5}
                                        adaptive_width: True

                                        MDBoxLayout:
                                            orientation: 'horizontal'
                                            spacing: dp(6)
                                            size_hint: None, None
                                            size: dp(90), dp(36)
                                            pos_hint: {"center_y": 0.5}
                                            MDCard:
                                                size_hint: None, None
                                                size: dp(24), dp(18)
                                                radius: [dp(2)]
                                                md_bg_color: 1, 1, 1, 1
                                                line_color: 0.8, 0.8, 0.8, 1
                                                line_width: 1
                                                elevation: 0
                                                pos_hint: {"center_y": 0.5}
                                                FlagWidget:
                                                    country: app.destination_country
                                            MDLabel:
                                                text: app.destination_country
                                                font_style: "Body2"
                                                bold: True
                                                theme_text_color: "Secondary"
                                                valign: "middle"

                                        MDCard:
                                            size_hint: None, None
                                            size: dp(110), dp(36)
                                            radius: [dp(10)]
                                            md_bg_color: 0.93, 0.96, 1.0, 1
                                            line_color: 0.0, 0.55, 1.0, 0.3
                                            line_width: 1
                                            elevation: 0
                                            pos_hint: {"center_y": 0.5}
                                            padding: [dp(8), 0, dp(8), 0]
                                            MDBoxLayout:
                                                orientation: 'horizontal'
                                                spacing: dp(6)
                                                MDCard:
                                                    size_hint: None, None
                                                    size: dp(22), dp(22)
                                                    radius: [dp(6)]
                                                    md_bg_color: 1.0, 0.42, 0.36, 1
                                                    pos_hint: {"center_y": 0.5}
                                                    elevation: 0
                                                    MDLabel:
                                                        text: "P"
                                                        font_style: "Caption"
                                                        bold: True
                                                        halign: "center"
                                                        valign: "middle"
                                                        theme_text_color: "Custom"
                                                        text_color: 1, 1, 1, 1
                                                MDLabel:
                                                    text: str(app.user_points)
                                                    font_style: "Subtitle1"
                                                    bold: True
                                                    theme_text_color: "Custom"
                                                    text_color: 0.0, 0.55, 1.0, 1
                                                    valign: "middle"

                                    MDCard:
                                        orientation: 'horizontal'
                                        size_hint_y: None
                                        height: dp(90)
                                        radius: [dp(16)]
                                        md_bg_color: 0.95, 0.9, 1.0, 1
                                        line_color: 0.8, 0.7, 0.95, 1
                                        line_width: 1
                                        elevation: 1
                                        padding: dp(12)
                                        spacing: dp(10)
                                        
                                        MDBoxLayout:
                                            orientation: 'vertical'
                                            spacing: dp(2)
                                            size_hint_x: 0.7
                                            MDLabel:
                                                text: "Invite Friends, Get 500 Points!"
                                                font_style: "Subtitle2"
                                                bold: True
                                                theme_text_color: "Custom"
                                                text_color: 0.7, 0.4, 0.95, 1
                                            MDLabel:
                                                text: "Share the joy! Invite friends today."
                                                font_style: "Caption"
                                                theme_text_color: "Secondary"
                                        MDIcon:
                                            icon: "gift-outline"
                                            theme_text_color: "Custom"
                                            text_color: 0.7, 0.4, 0.95, 1
                                            font_size: "32sp"
                                            pos_hint: {"center_y": 0.5}

                                    MDCard:
                                        orientation: 'vertical'
                                        size_hint_y: None
                                        height: dp(270)
                                        radius: [dp(16)]
                                        md_bg_color: 1, 1, 1, 1
                                        line_color: 0.9, 0.91, 0.94, 1
                                        line_width: 1
                                        elevation: 1
                                        padding: [dp(4), dp(8), dp(4), dp(8)]
                                        spacing: dp(2)

                                        OneLineAvatarIconListItem:
                                            text: "Wishlist"
                                            on_release: app.switch_tab("wishlist")
                                            IconLeftWidget:
                                                icon: "bookmark-outline"
                                                theme_text_color: "Custom"
                                                text_color: 1.0, 0.42, 0.36, 1
                                            IconRightWidget:
                                                icon: "chevron-right"
                                                theme_text_color: "Custom"
                                                text_color: 0.7, 0.7, 0.7, 1

                                        OneLineAvatarIconListItem:
                                            text: "History"
                                            on_release: app.show_dialog("History", "No scan history recorded yet.")
                                            IconLeftWidget:
                                                icon: "history"
                                                theme_text_color: "Custom"
                                                text_color: 0.0, 0.55, 1.0, 1
                                            IconRightWidget:
                                                icon: "chevron-right"
                                                theme_text_color: "Custom"
                                                text_color: 0.7, 0.7, 0.7, 1

                                        OneLineAvatarIconListItem:
                                            text: "Account Settings"
                                            on_release: app.show_key_dialog()
                                            IconLeftWidget:
                                                icon: "account-cog-outline"
                                                theme_text_color: "Custom"
                                                text_color: 0.7, 0.4, 0.95, 1
                                            IconRightWidget:
                                                icon: "chevron-right"
                                                theme_text_color: "Custom"
                                                text_color: 0.7, 0.7, 0.7, 1

                                        OneLineAvatarIconListItem:
                                            text: "Redeem points for rewards"
                                            on_release: app.switch_tab("coupons")
                                            IconLeftWidget:
                                                icon: "ticket-percent-outline"
                                                theme_text_color: "Custom"
                                                text_color: 1.0, 0.6, 0.1, 1
                                            IconRightWidget:
                                                icon: "chevron-right"
                                                theme_text_color: "Custom"
                                                text_color: 0.7, 0.7, 0.7, 1

                                        OneLineAvatarIconListItem:
                                            text: "System Settings"
                                            on_release: app.show_dialog("Settings", "Change language, notifications or privacy settings here.")
                                            IconLeftWidget:
                                                icon: "cog-outline"
                                                theme_text_color: "Custom"
                                                text_color: 0.5, 0.55, 0.55, 1
                                            IconRightWidget:
                                                icon: "chevron-right"
                                                theme_text_color: "Custom"
                                                text_color: 0.7, 0.7, 0.7, 1

                                    MDCard:
                                        size_hint: (0.7, None)
                                        height: dp(40)
                                        radius: [dp(12)]
                                        md_bg_color: 1, 1, 1, 1
                                        line_color: 0.7, 0.7, 0.7, 1
                                        line_width: 1
                                        elevation: 0
                                        pos_hint: {"center_x": 0.5}
                                        ripple_behavior: True
                                        on_release: app.handle_logout()
                                        MDLabel:
                                            text: "Logout"
                                            halign: "center"
                                            valign: "middle"
                                            bold: True
                                            theme_text_color: "Custom"
                                            text_color: 0.5, 0.55, 0.55, 1

                    Screen:
                        name: "chat"
                        MDBoxLayout:
                            orientation: 'vertical'
                            padding: dp(12)
                            spacing: dp(10)

                            MDBoxLayout:
                                size_hint_y: None
                                height: dp(46)
                                spacing: dp(10)
                                SafeIconButton:
                                    icon: "home-outline"
                                    on_release: app.switch_tab("home")
                                MDRaisedButton:
                                    id: chat_persona_btn
                                    text: "🩺 AI Health Consultant"
                                    md_bg_color: 0.9, 0.92, 0.94, 1
                                    text_color: 0.1, 0.1, 0.12, 1
                                    size_hint_x: 0.6
                                    on_release: app.toggle_chat_persona()
                                MDRaisedButton:
                                    text: "Clear"
                                    md_bg_color: 0.8, 0.2, 0.2, 1
                                    text_color: 1, 1, 1, 1
                                    size_hint_x: 0.2
                                    on_release: app.clear_chat()

                            ResponsiveScrollView:
                                id: chat_scroll
                                MDGridLayout:
                                    id: chat_grid
                                    cols: 1
                                    adaptive_height: True
                                    spacing: dp(10)
                                    padding: [0, dp(5), 0, dp(5)]

                            MDBoxLayout:
                                size_hint_y: None
                                height: dp(54)
                                spacing: dp(10)

                                MDTextField:
                                    id: chat_input_field
                                    hint_text: "Type symptom or ask questions..."
                                    mode: "rectangle"
                                    line_color_focus: 1.0, 0.42, 0.36, 1
                                    size_hint_x: 0.8
                                    on_text_validate: app.send_chat_message()

                                MDCard:
                                    size_hint: None, None
                                    size: dp(48), dp(48)
                                    radius: [dp(14)]
                                    md_bg_color: 1.0, 0.42, 0.36, 1
                                    elevation: 0
                                    ripple_behavior: True
                                    on_release: app.send_chat_message()
                                    MDIcon:
                                        icon: "send"
                                        theme_text_color: "Custom"
                                        text_color: 1, 1, 1, 1
                                        pos_hint: {"center_x": 0.5, "center_y": 0.5}
                                        halign: "center"

                    Screen:
                        name: "ranking"
                        MDBoxLayout:
                            orientation: 'vertical'
                            MDBoxLayout:
                                size_hint_y: None
                                height: dp(56)
                                padding: [dp(8), 0, dp(8), 0]
                                md_bg_color: 1, 1, 1, 1
                                SafeIconButton:
                                    icon: "home-outline"
                                    on_release: app.switch_tab("home")
                                MDLabel:
                                    text: "Scan Ranking"
                                    font_style: "H6"
                                    bold: True
                                    halign: "center"
                                SafeIconButton:
                                    icon: "bell-outline"
                                    on_release: app.show_dialog("Notifications", "No notifications.")
                            
                            ResponsiveScrollView:
                                size_hint_y: None
                                height: dp(46)
                                do_scroll_y: False
                                MDBoxLayout:
                                    id: ranking_chips_container
                                    orientation: 'horizontal'
                                    adaptive_width: True
                                    spacing: dp(8)
                                    padding: [dp(12), 0, dp(12), 0]

                            ResponsiveScrollView:
                                MDGridLayout:
                                    id: ranking_grid
                                    cols: 1
                                    adaptive_height: True
                                    spacing: dp(12)
                                    padding: dp(12)

                MDFloatLayout:
                    size_hint_y: None
                    height: dp(60)
                    canvas.before:
                        Color:
                            rgba: 0.9, 0.91, 0.94, 1
                        Line:
                            points: 0, self.height, self.width, self.height
                            width: 1

                    MDCard:
                        size_hint: 1, 1
                        radius: [0, 0, 0, 0]
                        md_bg_color: 1, 1, 1, 1
                        elevation: 0

                        MDBoxLayout:
                            orientation: 'horizontal'
                            spacing: dp(2)

                            MDCard:
                                orientation: 'vertical'
                                size_hint_x: 0.2
                                md_bg_color: 0, 0, 0, 0
                                ripple_behavior: True
                                padding: [0, dp(4), 0, dp(4)]
                                on_release: app.switch_tab("home")
                                MDIcon:
                                    icon: "home"
                                    theme_text_color: "Custom"
                                    text_color: (1.0, 0.42, 0.36, 1.0) if app.active_tab == "home" else (0.5, 0.55, 0.55, 1.0)
                                    font_size: "20sp"
                                    pos_hint: {"center_x": 0.5}
                                    halign: "center"
                                MDLabel:
                                    text: "Home"
                                    font_style: "Caption"
                                    font_size: "9sp"
                                    halign: "center"
                                    theme_text_color: "Custom"
                                    text_color: (1.0, 0.42, 0.36, 1.0) if app.active_tab == "home" else (0.5, 0.55, 0.55, 1.0)

                            MDRelativeLayout:
                                size_hint_x: 0.2
                                on_touch_down: if self.collide_point(*args[1].pos): app.switch_tab("articles")
                                MDBoxLayout:
                                    orientation: 'vertical'
                                    pos_hint: {"center_x": 0.5, "center_y": 0.5}
                                    MDIcon:
                                        icon: "card-text"
                                        theme_text_color: "Custom"
                                        text_color: (1.0, 0.42, 0.36, 1.0) if app.active_tab == "articles" else (0.5, 0.55, 0.55, 1.0)
                                        font_size: "20sp"
                                        pos_hint: {"center_x": 0.5}
                                        halign: "center"
                                    MDLabel:
                                        text: "Articles"
                                        font_style: "Caption"
                                        font_size: "9sp"
                                        halign: "center"
                                        theme_text_color: "Custom"
                                        text_color: (1.0, 0.42, 0.36, 1.0) if app.active_tab == "articles" else (0.5, 0.55, 0.55, 1.0)
                                MDCard:
                                    size_hint: None, None
                                    size: dp(15), dp(15)
                                    radius: [dp(6)]
                                    md_bg_color: 1.0, 0.3, 0.3, 1
                                    elevation: 0
                                    pos_hint: {"center_x": 0.65, "center_y": 0.75}
                                    MDLabel:
                                        text: "18"
                                        font_style: "Caption"
                                        font_size: "8sp"
                                        bold: True
                                        halign: "center"
                                        valign: "middle"
                                        theme_text_color: "Custom"
                                        text_color: 1, 1, 1, 1

                            Widget:
                                size_hint_x: 0.2

                            MDRelativeLayout:
                                size_hint_x: 0.2
                                on_touch_down: if self.collide_point(*args[1].pos): app.switch_tab("coupons")
                                MDBoxLayout:
                                    orientation: 'vertical'
                                    pos_hint: {"center_x": 0.5, "center_y": 0.5}
                                    MDIcon:
                                        icon: "ticket-percent"
                                        theme_text_color: "Custom"
                                        text_color: (1.0, 0.42, 0.36, 1.0) if app.active_tab == "coupons" else (0.5, 0.55, 0.55, 1.0)
                                        font_size: "20sp"
                                        pos_hint: {"center_x": 0.5}
                                        halign: "center"
                                    MDLabel:
                                        text: "Coupons"
                                        font_style: "Caption"
                                        font_size: "9sp"
                                        halign: "center"
                                        theme_text_color: "Custom"
                                        text_color: (1.0, 0.42, 0.36, 1.0) if app.active_tab == "coupons" else (0.5, 0.55, 0.55, 1.0)
                                MDCard:
                                    size_hint: None, None
                                    size: dp(22), dp(14)
                                    radius: [dp(5)]
                                    md_bg_color: 1.0, 0.55, 0.0, 1
                                    elevation: 0
                                    pos_hint: {"center_x": 0.7, "center_y": 0.75}
                                    MDLabel:
                                        text: "49%"
                                        font_style: "Caption"
                                        font_size: "7sp"
                                        bold: True
                                        halign: "center"
                                        valign: "middle"
                                        theme_text_color: "Custom"
                                        text_color: 1, 1, 1, 1

                            MDCard:
                                orientation: 'vertical'
                                size_hint_x: 0.2
                                md_bg_color: 0, 0, 0, 0
                                ripple_behavior: True
                                padding: [0, dp(4), 0, dp(4)]
                                on_release: app.switch_tab("search")
                                MDIcon:
                                    icon: "magnify"
                                    theme_text_color: "Custom"
                                    text_color: (1.0, 0.42, 0.36, 1.0) if app.active_tab == "search" else (0.5, 0.55, 0.55, 1.0)
                                    font_size: "20sp"
                                    pos_hint: {"center_x": 0.5}
                                    halign: "center"
                                MDLabel:
                                    text: "Search"
                                    font_style: "Caption"
                                    font_size: "9sp"
                                    halign: "center"
                                    theme_text_color: "Custom"
                                    text_color: (1.0, 0.42, 0.36, 1.0) if app.active_tab == "search" else (0.5, 0.55, 0.55, 1.0)

                    MDCard:
                        size_hint: None, None
                        size: dp(60), dp(60)
                        radius: [dp(30)]
                        md_bg_color: 1.0, 0.42, 0.36, 1.0
                        elevation: 4
                        pos_hint: {"center_x": 0.5}
                        y: dp(14)
                        ripple_behavior: True
                        on_release: app.switch_tab("scanner")
                        MDIcon:
                            icon: "barcode-scan"
                            theme_text_color: "Custom"
                            text_color: 1, 1, 1, 1
                            font_size: "24sp"
                            pos_hint: {"center_x": 0.5, "center_y": 0.5}
                            halign: "center"

    Screen:
        name: "details_screen"
        MDBoxLayout:
            orientation: 'vertical'
            md_bg_color: 0.96, 0.97, 0.98, 1

            MDTopAppBar:
                id: details_toolbar
                title: "Product Details"
                anchor_title: "left"
                elevation: 1
                md_bg_color: 1, 1, 1, 1
                specific_text_color: 1.0, 0.42, 0.36, 1
                left_action_items: [["arrow-left", lambda x: app.go_back_to_main()]]

            ResponsiveScrollView:
                do_scroll_x: False
                MDBoxLayout:
                    orientation: 'vertical'
                    padding: dp(16)
                    spacing: dp(16)
                    size_hint_y: None
                    height: self.minimum_height

                    MDCard:
                        id: details_image_card
                        size_hint_y: None
                        height: dp(220)
                        radius: [16, 16, 16, 16]
                        md_bg_color: 1, 1, 1, 1
                        line_color: 0.9, 0.91, 0.94, 1
                        line_width: 1
                        padding: dp(8)
                        elevation: 1

                        UAAsyncImage:
                            id: details_image
                            source: ""
                            allow_stretch: True
                            keep_ratio: True

                    MDBoxLayout:
                        orientation: 'vertical'
                        size_hint_y: None
                        height: self.minimum_height
                        spacing: dp(6)

                        MDLabel:
                            id: details_title
                            text: "Product Name"
                            font_style: "H5"
                            theme_text_color: "Custom"
                            text_color: 0.1, 0.1, 0.12, 1
                            bold: True
                            size_hint_y: None
                            height: self.texture_size[1]

                        MDLabel:
                            id: details_subtitle
                            text: "Active Ingredients"
                            font_style: "Subtitle1"
                            theme_text_color: "Custom"
                            text_color: 0.5, 0.55, 0.55, 1
                            italic: True
                            size_hint_y: None
                            height: self.texture_size[1]

                        MDLabel:
                            id: details_meta
                            text: "Category / Location"
                            font_style: "Caption"
                            theme_text_color: "Custom"
                            text_color: 1.0, 0.42, 0.36, 1
                            bold: True
                            size_hint_y: None
                            height: self.texture_size[1]

                        # Language Translator Chips Row
                        ResponsiveScrollView:
                            size_hint_y: None
                            height: dp(38)
                            do_scroll_y: False
                            MDBoxLayout:
                                id: language_chips_container
                                orientation: 'horizontal'
                                adaptive_width: True
                                spacing: dp(8)
                                padding: [0, dp(2), 0, dp(2)]

                    MDSeparator:
                        color: 0.9, 0.91, 0.94, 1

                    MDBoxLayout:
                        id: details_info_container
                        orientation: 'vertical'
                        spacing: dp(14)
                        size_hint_y: None
                        height: self.minimum_height
"""

# ==================== HELPER LAYOUT CLASSES ====================
class NonBlockingCard(MDCard):
    """MDCard subclass that does not block ScrollView scrolling when dragged."""
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.ud[f'nb_card_touch_{id(self)}'] = touch.pos
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        key = f'nb_card_touch_{id(self)}'
        if key in touch.ud:
            down_pos = touch.ud[key]
            if abs(touch.x - down_pos[0]) > dp(8) or abs(touch.y - down_pos[1]) > dp(8):
                if touch.grab_current is self:
                    touch.ungrab(self)
                return False
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        key = f'nb_card_touch_{id(self)}'
        if key in touch.ud:
            down_pos = touch.ud[key]
            if abs(touch.x - down_pos[0]) > dp(8) or abs(touch.y - down_pos[1]) > dp(8):
                if touch.grab_current is self:
                    touch.ungrab(self)
                return True
        return super().on_touch_up(touch)


class CountryChip(NonBlockingCard):
    """Custom chip widget for Location filtering."""
    def __init__(self, text, active=False, on_select=None, **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.on_select = on_select
        self.active = active
        
        self.orientation = 'horizontal'
        self.size_hint = (None, None)
        self.width = max(dp(85), len(text) * 8 + dp(28))
        self.height = dp(36)
        self.radius = [16, 16, 16, 16]
        self.padding = [10, 4, 10, 4]
        self.elevation = 0
        self.ripple_behavior = True
        
        self.label_widget = MDLabel(
            text=text,
            font_style="Caption",
            bold=True,
            valign="middle",
            halign="center",
            size_hint_y=None,
            height=20,
            pos_hint={"center_y": 0.5}
        )
        self.add_widget(self.label_widget)
        self.update_ui()
        self.bind(on_release=lambda x: self.trigger_select())

    def update_ui(self):
        app = MDApp.get_running_app()
        is_dark = (app.theme_cls.theme_style == "Dark")
        active_color = (0.85, 0.65, 0.13, 1.0) if is_dark else (1.0, 0.42, 0.36, 1.0)
        
        if self.active:
            self.md_bg_color = active_color
            self.line_color = active_color
            self.label_widget.text_color = (1, 1, 1, 1)
            self.label_widget.theme_text_color = "Custom"
        else:
            self.md_bg_color = (0.18, 0.18, 0.2, 0.6) if is_dark else (0.9, 0.92, 0.94, 0.6)
            self.line_color = (0.25, 0.25, 0.28, 0.4) if is_dark else (0.85, 0.87, 0.9, 0.4)
            self.label_widget.text_color = (0.75, 0.75, 0.8, 1.0) if is_dark else (0.35, 0.38, 0.42, 1.0)
            self.label_widget.theme_text_color = "Custom"
            
    def trigger_select(self):
        if self.on_select:
            self.on_select(self.text)


class CategoryChip(NonBlockingCard):
    """Custom chip widget with icon for Category filtering."""
    def __init__(self, text, icon_name, active=False, on_select=None, **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.icon_name = icon_name
        self.on_select = on_select
        self.active = active
        
        self.orientation = 'horizontal'
        self.size_hint = (None, None)
        self.width = max(dp(110), len(text) * 8 + dp(48))
        self.height = dp(36)
        self.radius = [16, 16, 16, 16]
        self.padding = [10, 4, 10, 4]
        self.spacing = 8
        self.elevation = 0
        self.ripple_behavior = True
        
        self.icon_widget = MDIcon(
            icon=icon_name,
            size_hint=(None, None),
            size=(20, 20),
            pos_hint={"center_y": 0.5},
            font_size="18sp"
        )
        
        self.label_widget = MDLabel(
            text=text,
            font_style="Caption",
            bold=True,
            valign="middle",
            halign="left",
            size_hint_y=None,
            height=20,
            pos_hint={"center_y": 0.5}
        )
        
        self.add_widget(self.icon_widget)
        self.add_widget(self.label_widget)
        self.update_ui()
        self.bind(on_release=lambda x: self.trigger_select())

    def update_ui(self):
        app = MDApp.get_running_app()
        is_dark = (app.theme_cls.theme_style == "Dark")
        active_color = (0.85, 0.65, 0.13, 1.0) if is_dark else (1.0, 0.42, 0.36, 1.0)
        
        if self.active:
            self.md_bg_color = active_color
            self.line_color = active_color
            self.icon_widget.text_color = (1, 1, 1, 1)
            self.icon_widget.theme_text_color = "Custom"
            self.label_widget.text_color = (1, 1, 1, 1)
            self.label_widget.theme_text_color = "Custom"
        else:
            self.md_bg_color = (0.18, 0.18, 0.2, 0.6) if is_dark else (0.9, 0.92, 0.94, 0.6)
            self.line_color = (0.25, 0.25, 0.28, 0.4) if is_dark else (0.85, 0.87, 0.9, 0.4)
            self.icon_widget.text_color = (0.75, 0.75, 0.8, 1.0) if is_dark else (0.35, 0.38, 0.42, 1.0)
            self.icon_widget.theme_text_color = "Custom"
            self.label_widget.text_color = (0.75, 0.75, 0.8, 1.0) if is_dark else (0.35, 0.38, 0.42, 1.0)
            self.label_widget.theme_text_color = "Custom"
            
    def trigger_select(self):
        if self.on_select:
            self.on_select(self.text)


class MobileMedicineCard(NonBlockingCard):
    """Custom card widget for displaying medication summaries with rating stars and medals."""
    def __init__(self, med, rank=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.padding = [dp(12), dp(10), dp(12), dp(10)]
        self.spacing = dp(12)
        self.size_hint_y = None
        self.height = dp(140)
        self.radius = [dp(16), dp(16), dp(16), dp(16)]
        
        app = MDApp.get_running_app()
        is_dark = (app.theme_cls.theme_style == "Dark")
        
        self.md_bg_color = (0.13, 0.13, 0.15, 1) if is_dark else (1.0, 1.0, 1.0, 1.0)
        self.line_color = (0.2, 0.2, 0.22, 1) if is_dark else (0.9, 0.91, 0.94, 1.0)
        self.line_width = 1
        self.ripple_behavior = True
        
        self.bind(on_release=lambda x: MDApp.get_running_app().show_medication_details(med))
        
        name = med.get("name", "Unknown Medicine")
        generic = med.get("generic_name", med.get("active_ingredients", "Not Specified"))
        cat = med.get("category", "General")
        price = med.get("price", "Price varies")
        country = med.get("country", "")
        image_url = med.get("image_url", "")
        
        # 1. Left side: MDRelativeLayout for image and rank medal badge overlay
        img_layout = MDRelativeLayout(size_hint=(None, None), size=(80, 90), pos_hint={"center_y": 0.5})
        
        # Inner Image container
        img_container = MDBoxLayout(size_hint=(1, 1), padding=4)
        if image_url:
            img = UAAsyncImage(
                source=image_url,
                allow_stretch=True,
                keep_ratio=True
            )
            img_container.add_widget(img)
        else:
            icon_name = "medication"
            cat_lower = cat.lower()
            if "pain" in cat_lower:
                icon_name = "pill"
            elif "cold" in cat_lower or "cough" in cat_lower or "flu" in cat_lower:
                icon_name = "thermometer"
            elif "digest" in cat_lower or "stomach" in cat_lower or "acid" in cat_lower:
                icon_name = "bottle-tonic-plus"
            elif "allergy" in cat_lower:
                icon_name = "flower"
                
            primary_color = (0.85, 0.65, 0.13, 1.0) if is_dark else (1.0, 0.42, 0.36, 1.0)
            primary_bg = (0.85, 0.65, 0.13, 0.15) if is_dark else (1.0, 0.42, 0.36, 0.1)
            primary_line = (0.85, 0.65, 0.13, 0.25) if is_dark else (1.0, 0.42, 0.36, 0.2)
            
            icon_card = MDCard(
                size_hint=(None, None),
                size=(68, 68),
                radius=[20, 20, 20, 20],
                md_bg_color=primary_bg,
                line_color=primary_line,
                line_width=1,
                pos_hint={"center_x": 0.5, "center_y": 0.5},
                elevation=0
            )
            
            icon_widget = MDIcon(
                icon=icon_name,
                theme_text_color="Custom",
                text_color=primary_color,
                pos_hint={"center_x": 0.5, "center_y": 0.5},
                halign="center",
                font_size="24sp"
            )
            icon_card.add_widget(icon_widget)
            img_container.add_widget(icon_card)
            
        img_layout.add_widget(img_container)
        
        # Rank badge overlay
        if rank is not None:
            if rank == 1:
                medal_color = (1.0, 0.8, 0.2, 1.0)  # Gold
            elif rank == 2:
                medal_color = (0.75, 0.75, 0.75, 1.0)  # Silver
            elif rank == 3:
                medal_color = (0.8, 0.5, 0.2, 1.0)  # Bronze
            else:
                medal_color = (0.6, 0.65, 0.7, 1.0)  # Grey
                
            medal_badge = MDCard(
                size_hint=(None, None),
                size=(22, 22),
                radius=[6, 6, 6, 6],
                md_bg_color=medal_color,
                elevation=1,
                pos_hint={"x": 0, "top": 1}
            )
            medal_badge.add_widget(MDLabel(
                text=str(rank),
                font_style="Caption",
                font_size="10sp",
                bold=True,
                halign="center",
                valign="middle",
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1)
            ))
            img_layout.add_widget(medal_badge)
            
        self.add_widget(img_layout)
        
        # 2. Middle side: text details
        text_layout = MDBoxLayout(
            orientation='vertical',
            spacing=dp(2),
            size_hint_y=None,
            pos_hint={"center_y": 0.5}
        )
        text_layout.bind(minimum_height=text_layout.setter('height'))
        
        # Adjust card height dynamically based on text_layout height
        def adjust_card_height(instance, val):
            self.height = max(dp(140), val + dp(24))
        text_layout.bind(height=adjust_card_height)
        
        def update_text_size(instance, val):
            # Ensure loop safety with float precision checks
            if not instance.text_size or abs(instance.text_size[0] - val) > 0.5:
                instance.text_size = (val, None)
        
        header_text = f"{country.upper()}   |   {cat.upper()}" if country else cat.upper()
        primary_color = (0.85, 0.65, 0.13, 1.0) if is_dark else (1.0, 0.42, 0.36, 1.0)
        text_primary = (0.95, 0.95, 0.98, 1.0) if is_dark else (0.1, 0.1, 0.12, 1.0)
        
        lbl_header = MDLabel(
            text=header_text,
            theme_text_color="Custom",
            text_color=primary_color,
            font_style="Caption",
            bold=True,
            size_hint_y=None,
            height=dp(14)
        )
        text_layout.add_widget(lbl_header)
        
        lbl_name = MDLabel(
            text=name,
            theme_text_color="Custom",
            text_color=text_primary,
            font_style="Subtitle1",
            bold=True,
            adaptive_height=True
        )
        lbl_name.bind(width=update_text_size)
        text_layout.add_widget(lbl_name)
        
        # Dynamic Rating Stars
        name_hash = sum(ord(c) for c in name)
        rating = round(4.0 + (name_hash % 11) / 10.0, 1)  # Rating between 4.0 and 5.0
        rating_count = (name_hash * 7) % 200 + 15
        
        stars_layout = MDBoxLayout(orientation='horizontal', size_hint=(None, None), size=(dp(145), dp(16)), spacing=2)
        for i in range(1, 6):
            if rating >= i:
                icon_name = "star"
                color = (1.0, 0.75, 0.1, 1.0)
            elif rating >= i - 0.5:
                icon_name = "star-half-full"
                color = (1.0, 0.75, 0.1, 1.0)
            else:
                icon_name = "star-outline"
                color = (0.7, 0.7, 0.7, 0.5)
            stars_layout.add_widget(MDIcon(
                icon=icon_name,
                theme_text_color="Custom",
                text_color=color,
                font_size="12sp",
                size_hint=(None, None),
                size=(12, 12),
                pos_hint={"center_y": 0.5}
            ))
            
        text_muted = (0.65, 0.65, 0.7, 1.0) if is_dark else (0.5, 0.55, 0.55, 1.0)
        
        stars_layout.add_widget(MDLabel(
            text=f"{rating} ({rating_count})",
            font_style="Caption",
            font_size="10sp",
            theme_text_color="Custom",
            text_color=text_muted,
            valign="middle",
            halign="left",
            size_hint=(None, None),
            size=(dp(70), dp(16))
        ))
        text_layout.add_widget(stars_layout)
        
        lbl_generic = MDLabel(
            text=f"Active: {generic}",
            theme_text_color="Custom",
            text_color=text_muted,
            font_style="Caption",
            italic=True,
            adaptive_height=True
        )
        lbl_generic.bind(width=update_text_size)
        text_layout.add_widget(lbl_generic)
        
        lbl_price = MDLabel(
            text=f"Price: {price}",
            theme_text_color="Custom",
            text_color=text_primary,
            font_style="Caption",
            adaptive_height=True
        )
        lbl_price.bind(width=update_text_size)
        text_layout.add_widget(lbl_price)
        
        self.add_widget(text_layout)
        
        # 3. Right side: Wishlist Bookmark and Chevron
        right_layout = MDBoxLayout(
            orientation='vertical',
            size_hint=(None, None),
            width=dp(40),
            height=dp(70),
            spacing=dp(10),
            pos_hint={"center_y": 0.5}
        )
        
        is_saved = name in MDApp.get_running_app().saved_items
        bookmark_btn = Factory.SafeIconButton(
            icon="bookmark" if is_saved else "bookmark-outline",
            icon_color=primary_color if is_saved else (0.6, 0.65, 0.7, 1.0),
            size_hint=(None, None),
            size=(dp(28), dp(28)),
            radius=[dp(6), dp(6), dp(6), dp(6)],
            pos_hint={"center_x": 0.5}
        )
        bookmark_btn.bind(on_release=lambda x: self.trigger_wishlist(med))
        right_layout.add_widget(bookmark_btn)
        
        chevron = MDIcon(
            icon="chevron-right",
            theme_text_color="Custom",
            text_color=(0.6, 0.6, 0.7, 0.8),
            pos_hint={"center_x": 0.5},
            font_size="20sp",
            size_hint=(None, None),
            size=(24, 24)
        )
        right_layout.add_widget(chevron)
        self.add_widget(right_layout)
        
    def trigger_wishlist(self, med):
        MDApp.get_running_app().toggle_wishlist(med)


class ChatBubble(NonBlockingCard):
    """Custom speech bubble card for AI Chat messaging in theme-aware styling."""
    def __init__(self, sender, text, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 12
        self.size_hint_y = None
        self.size_hint_x = 0.8
        self.radius = [12, 12, 12, 12]
        self.elevation = 0
        
        # Check active theme style
        app = MDApp.get_running_app()
        is_dark = (app.theme_cls.theme_style == "Dark")
        
        if sender == "user":
            if is_dark:
                self.md_bg_color = (0.76, 0.12, 0.18, 1.0)  # Crimson Red
                label_color = (1.0, 0.8, 0.8, 0.9)
                text_color = (1.0, 1.0, 1.0, 1.0)
            else:
                self.md_bg_color = (1.0, 0.42, 0.36, 1.0)  # Coral
                label_color = (1.0, 1.0, 1.0, 0.8)
                text_color = (1.0, 1.0, 1.0, 1.0)
            self.pos_hint = {"right": 0.98}
            sender_name = "You"
        else:
            if is_dark:
                self.md_bg_color = (0.18, 0.18, 0.2, 1.0)  # Dark charcoal
                label_color = (0.85, 0.65, 0.13, 1.0)      # Golden Amber
                text_color = (0.95, 0.95, 0.98, 1.0)
            else:
                self.md_bg_color = (0.9, 0.92, 0.94, 1.0)  # Light grey
                label_color = (1.0, 0.42, 0.36, 1.0)
                text_color = (0.1, 0.1, 0.12, 1.0)
            self.pos_hint = {"left": 0.02}
            sender_name = "PharmaGlobe Assistant"
            
        self.add_widget(MDLabel(
            text=sender_name,
            theme_text_color="Custom",
            text_color=label_color,
            font_style="Caption",
            bold=True
        ))
        lbl = MDLabel(
            text=text,
            theme_text_color="Custom",
            text_color=text_color,
            font_style="Body2",
            size_hint_y=None
        )
        lbl.bind(width=lambda inst, val: setattr(inst, 'text_size', (val, None)))
        lbl.bind(texture_size=lambda inst, size: setattr(inst, 'height', size[1]))
        self.add_widget(lbl)
        self.bind(minimum_height=self.setter('height'))


# ==================== MAIN APPLICATION ====================

class PharmaGlobeApp(MDApp):
    # App State properties
    active_tab = StringProperty("home")
    wishlist_prev_tab = StringProperty("home")
    user_points = NumericProperty(1004)
    saved_items = ListProperty([])

    current_country = StringProperty("Global (All)")
    current_category = StringProperty("All")
    search_source = StringProperty("Local Database")
    chat_persona = StringProperty("🩺 AI Health Consultant")
    gemini_key = StringProperty("")
    is_online = BooleanProperty(True)
    current_language = StringProperty("English")
    preferred_language = StringProperty("English")
    home_country = StringProperty("USA")
    destination_country = StringProperty("Global (All)")
    
    # Store chat history arrays in memory
    health_chat_history = ListProperty([])
    dev_chat_history = ListProperty([])

    def build(self):
        # Configure overall themes for Black Clover (Amber/Gold primary, Red accent, Dark style)
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Amber"
        self.theme_cls.accent_palette = "Red"
        
        # Initialize default lists
        self.health_chat_history = [{
            "role": "assistant",
            "content": "Hello! I am your AI Health Consultant. Describe symptoms, ask about health problems, or ask for regional OTC medicine recommendations."
        }]
        self.dev_chat_history = [{
            "role": "assistant",
            "content": "Hello! I am the lead Developer of PharmaGlobe Mobile. I can explain the KivyMD frontend, Buildozer packaging specs, OpenCV scanners, or help you write code."
        }]
        
        # Barcode Auto-scanning State
        self.auto_scan_event = None
        self.is_scanning_frame = False
        self.scan_paused = False
        
        # Populate initial wishlist items so the view feels premium immediately
        self.saved_items = ["Loxonin S (ロキソニンS)", "Pepto-Bismol"]
        
        # Load environment API Key if configured
        self.gemini_key = ai_helper.get_env_api_key()
        
        # Schedule network check
        Clock.schedule_once(lambda dt: self.check_connection(), 1)
        Clock.schedule_interval(lambda dt: self.check_connection(), 45)
        
        # Dynamically apply Black Clover dark theme color mappings on the KV layout string
        bc_kv = KV
        # Backgrounds: light-grey/white -> deep midnight black and grimoire charcoal card
        bc_kv = bc_kv.replace("md_bg_color: 0.96, 0.97, 0.98, 1", "md_bg_color: 0.08, 0.08, 0.1, 1")
        bc_kv = bc_kv.replace("md_bg_color: 1, 1, 1, 1", "md_bg_color: 0.13, 0.13, 0.15, 1")
        bc_kv = bc_kv.replace("md_bg_color: 1.0, 1.0, 1.0, 1.0", "md_bg_color: 0.13, 0.13, 0.15, 1.0")
        bc_kv = bc_kv.replace("md_bg_color: 1, 1, 1, 0.9", "md_bg_color: 0.13, 0.13, 0.15, 0.9")
        bc_kv = bc_kv.replace("md_bg_color: 0.94, 0.94, 0.96, 1", "md_bg_color: 0.18, 0.18, 0.2, 1")
        
        # Primary highlights: Coral -> golden Dawn gold
        bc_kv = bc_kv.replace("md_bg_color: 1.0, 0.42, 0.36, 1.0", "md_bg_color: 0.85, 0.65, 0.13, 1.0")
        bc_kv = bc_kv.replace("md_bg_color: 1.0, 0.42, 0.36, 1", "md_bg_color: 0.85, 0.65, 0.13, 1")
        bc_kv = bc_kv.replace("text_color: 1.0, 0.42, 0.36, 1", "text_color: 0.85, 0.65, 0.13, 1")
        bc_kv = bc_kv.replace("text_color: 1.0, 0.42, 0.36, 1.0", "text_color: 0.85, 0.65, 0.13, 1.0")
        bc_kv = bc_kv.replace("md_bg_color: 1.0, 0.42, 0.36, 0.1", "md_bg_color: 0.85, 0.65, 0.13, 0.15")
        
        # Dark text colors: Dark grey -> White/light grey
        bc_kv = bc_kv.replace("text_color: 0.1, 0.1, 0.12, 1", "text_color: 0.95, 0.95, 0.98, 1")
        bc_kv = bc_kv.replace("text_color_focus: 0.1, 0.1, 0.12, 1", "text_color_focus: 0.95, 0.95, 0.98, 1")
        bc_kv = bc_kv.replace("text_color: 0.1, 0.1, 0.1, 1", "text_color: 0.95, 0.95, 0.98, 1")
        bc_kv = bc_kv.replace("text_color: 0.2, 0.2, 0.2, 1", "text_color: 0.9, 0.9, 0.92, 1")
        bc_kv = bc_kv.replace("text_color: 0.2, 0.2, 0.22, 1", "text_color: 0.9, 0.9, 0.92, 1")
        
        # Muted text colors: Medium grey -> Lighter grey
        bc_kv = bc_kv.replace("text_color: 0.5, 0.55, 0.55, 1", "text_color: 0.65, 0.65, 0.7, 1")
        bc_kv = bc_kv.replace("text_color: 0.3, 0.3, 0.35, 1", "text_color: 0.75, 0.75, 0.8, 1")
        bc_kv = bc_kv.replace("text_color: 0.4, 0.4, 0.45, 1", "text_color: 0.7, 0.7, 0.75, 1")
        
        # Blue accents: Blue -> Crimson Red for anti-magic
        bc_kv = bc_kv.replace("md_bg_color: 0.0, 0.55, 1.0, 1", "md_bg_color: 0.76, 0.12, 0.18, 1")
        bc_kv = bc_kv.replace("text_color: 0.0, 0.55, 1.0, 1", "text_color: 0.76, 0.12, 0.18, 1")
        
        # Load KV layout
        return Builder.load_string(bc_kv)

    def on_start(self):
        # Build country chips, category chips, and popular searches
        self.populate_location_chips()
        self.populate_category_chips()
        self.populate_popular_searches()
        
        # Build displays for all tabs
        self.render_directory()
        self.render_chat_feed()
        self.render_wishlist()
        self.render_articles()
        self.render_coupons()
        self.render_rankings()
        
        # Start status LED animation
        Clock.schedule_interval(self.animate_status_led, 0.6)
        
        # Auto-login hook for testing/debugging
        if os.environ.get("PHARMAGLOBE_AUTO_LOGIN") == "1":
            print("AUTO-LOGIN: Triggering auto guest login...")
            Clock.schedule_once(lambda dt: self.handle_login("Guest"), 0.5)

    # ==================== NAVIGATION & TAB CONTROLLERS ====================
    def switch_tab(self, tab_name):
        if tab_name == "wishlist":
            self.wishlist_prev_tab = self.active_tab
        self.active_tab = tab_name
        self.root.ids.tab_manager.current = tab_name
        
        # Stop camera if leaving scanner, start if entering
        if tab_name == "scanner":
            self.start_camera()
        elif hasattr(self.root, "ids") and "scanner_camera" in self.root.ids:
            self.stop_camera()
                
        # Trigger dynamic rendering of tabs when active
        if tab_name == "wishlist":
            self.render_wishlist()
        elif tab_name == "articles":
            self.render_articles()
        elif tab_name == "coupons":
            self.render_coupons()
        elif tab_name == "ranking":
            self.render_rankings()
        elif tab_name == "home":
            self.render_directory()

    def switch_to_search_tab_with_focus(self):
        self.switch_tab("search")
        def set_focus(dt):
            self.root.ids.search_field.focus = True
        Clock.schedule_once(set_focus, 0.1)

    # ==================== WISHLIST & BOOKMARK SYSTEM ====================
    def toggle_wishlist(self, med):
        med_name = med.get("name")
        if med_name in self.saved_items:
            self.saved_items.remove(med_name)
            self.show_dialog("Wishlist Updated", f"Removed '{med_name}' from your Wishlist.")
        else:
            self.saved_items.append(med_name)
            self.show_dialog("Wishlist Updated", f"Saved '{med_name}' to your Wishlist.")
            
        # Refresh current active containers to update UI states
        self.render_wishlist()
        self.render_directory()
        self.render_rankings()
        self.execute_search()

    def render_wishlist(self):
        if not hasattr(self.root, "ids") or "wishlist_grid" not in self.root.ids:
            return
        grid = self.root.ids.wishlist_grid
        grid.clear_widgets()
        
        saved_meds = []
        for name in self.saved_items:
            results = med.search_local_medicines(name)
            if results:
                saved_meds.append(results[0])
                
        if not saved_meds:
            grid.add_widget(MDLabel(
                text="Your wishlist is empty.\nTap the bookmark button on any medicine card to save it.",
                halign="center",
                theme_text_color="Secondary",
                size_hint_y=None,
                height=dp(100)
            ))
            return
            
        for item in saved_meds:
            grid.add_widget(MobileMedicineCard(item))

    # ==================== ARTICLES GENERATOR ====================
    def render_articles(self):
        if not hasattr(self.root, "ids") or "articles_grid" not in self.root.ids:
            return
        grid = self.root.ids.articles_grid
        grid.clear_widgets()
        
        articles = [
            {
                "title": "Top 10 Curated OTC Medicines to Buy in Japan",
                "time": "5 min read",
                "icon": "pill",
                "content": "Japan offers a wide variety of highly effective OTC medications. Popular recommendations include Loxonin S (for pain), Pabron Gold A (for cold/flu), Ohta's Isan (for digestion), and EVE Quick. Make sure to consult the active ingredients and match with equivalents from your home country."
            },
            {
                "title": "Understanding French Pharmacy Symbols & Labels",
                "time": "4 min read",
                "icon": "barcode",
                "content": "In France, pharmacies are easily spotted by their neon green crosses. OTC medicines such as Doliprane (paracetamol) and Spasfon are widely trusted. Keep in mind that dosages are strictly regulated, so read the package inserts or talk to the pharmacist."
            },
            {
                "title": "How to Find Allergy Relievers in South Korea",
                "time": "6 min read",
                "icon": "flower",
                "content": "Allergies can strike anywhere. In South Korea, popular antihistamines like Zyrtec are readily available over the counter. If you have severe symptoms, look for local pharmacies marked with a red 'Yak' symbol."
            },
            {
                "title": "Traveler's Guide to Spanish Pharmacy Terms",
                "time": "3 min read",
                "icon": "translate",
                "content": "When traveling in Spain, knowing a few key terms can help: 'Analgesico' for pain relievers, 'Antigripal' for cold medicines, and 'Fermacia' for pharmacy. Brand names like Gelocatil and Almax are standard OTC options."
            }
        ]
        
        is_dark = (self.theme_cls.theme_style == "Dark")
        for art in articles:
            card = NonBlockingCard(
                orientation='horizontal',
                size_hint_y=None,
                height=dp(80),
                radius=[12, 12, 12, 12],
                padding=dp(12),
                spacing=dp(12),
                md_bg_color=(0.13, 0.13, 0.15, 1) if is_dark else (1, 1, 1, 1),
                line_color=(0.2, 0.2, 0.22, 1) if is_dark else (0.9, 0.91, 0.94, 1.0),
                line_width=1,
                ripple_behavior=True,
                on_release=lambda x, a=art: self.show_dialog(a["title"], a["content"])
            )
            
            icon_box = MDCard(
                size_hint=(None, None),
                size=(dp(44), dp(44)),
                radius=[dp(12)],
                md_bg_color=(0.85, 0.65, 0.13, 0.15) if is_dark else (1.0, 0.42, 0.36, 0.1),
                pos_hint={"center_y": 0.5},
                elevation=0
            )
            icon_box.add_widget(MDIcon(
                icon=art["icon"],
                theme_text_color="Custom",
                text_color=(0.85, 0.65, 0.13, 1) if is_dark else (1.0, 0.42, 0.36, 1),
                pos_hint={"center_x": 0.5, "center_y": 0.5},
                halign="center"
            ))
            
            text_box = MDBoxLayout(orientation='vertical', spacing=dp(2))
            text_box.add_widget(MDLabel(
                text=art["title"],
                font_style="Subtitle2",
                bold=True,
                theme_text_color="Custom",
                text_color=(0.95, 0.95, 0.98, 1) if is_dark else (0.1, 0.1, 0.12, 1)
            ))
            text_box.add_widget(MDLabel(
                text=art["time"],
                font_style="Caption",
                theme_text_color="Secondary"
            ))
            
            chevron = MDIcon(
                icon="chevron-right",
                theme_text_color="Custom",
                text_color=(0.85, 0.65, 0.13, 1) if is_dark else (0.7, 0.7, 0.7, 1),
                pos_hint={"center_y": 0.5},
                size_hint_x=None,
                width=dp(24)
            )
            
            card.add_widget(icon_box)
            card.add_widget(text_box)
            card.add_widget(chevron)
            grid.add_widget(card)

    # ==================== REWARDS & COUPOUN SYSTEM ====================
    def render_coupons(self):
        if not hasattr(self.root, "ids") or "coupons_grid" not in self.root.ids:
            return
        grid = self.root.ids.coupons_grid
        grid.clear_widgets()
        
        coupons = [
            {"name": "Matsumoto Kiyoshi 10% Off", "points": 200, "desc": "Get a 10% discount on cosmetics, health foods, and supplements."},
            {"name": "Sun Drug 5% OTC Discount", "points": 100, "desc": "Receive a 5% discount on all over-the-counter medicines."},
            {"name": "Duty-Free Shopping Voucher (Y1,000)", "points": 900, "desc": "1,000 Yen discount on tax-free purchases at airport duty-free shops."},
            {"name": "Starbucks Gift Card (Y500)", "points": 500, "desc": "Get a 500 Yen e-gift card for Starbucks locations."}
        ]
        
        is_dark = (self.theme_cls.theme_style == "Dark")
        for cp in coupons:
            card = NonBlockingCard(
                orientation='vertical',
                size_hint_y=None,
                height=dp(110),
                radius=[12, 12, 12, 12],
                padding=dp(12),
                spacing=dp(6),
                md_bg_color=(0.13, 0.13, 0.15, 1) if is_dark else (1, 1, 1, 1),
                line_color=(0.2, 0.2, 0.22, 1) if is_dark else (0.9, 0.91, 0.94, 1.0),
                line_width=1,
                elevation=1
            )
            
            header = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(24))
            header.add_widget(MDLabel(
                text=cp["name"],
                font_style="Subtitle2",
                bold=True,
                theme_text_color="Custom",
                text_color=(0.95, 0.95, 0.98, 1) if is_dark else (0.1, 0.1, 0.12, 1)
            ))
            
            points_badge = MDCard(
                size_hint=(None, None),
                size=(dp(70), dp(20)),
                radius=[dp(8)],
                md_bg_color=(0.76, 0.12, 0.18, 0.15) if is_dark else (0.93, 0.96, 1.0, 1),
                pos_hint={"center_y": 0.5},
                elevation=0
            )
            points_badge.add_widget(MDLabel(
                text=f"{cp['points']} P",
                font_style="Caption",
                bold=True,
                halign="center",
                theme_text_color="Custom",
                text_color=(0.76, 0.12, 0.18, 1) if is_dark else (0.0, 0.55, 1.0, 1)
            ))
            header.add_widget(points_badge)
            
            desc_lbl = MDLabel(
                text=cp["desc"],
                font_style="Caption",
                theme_text_color="Secondary",
                size_hint_y=None,
                height=dp(30)
            )
            
            btn = MDRaisedButton(
                text="Redeem Voucher",
                md_bg_color=(0.85, 0.65, 0.13, 1.0) if is_dark else (1.0, 0.42, 0.36, 1.0),
                text_color=(1, 1, 1, 1),
                size_hint_y=None,
                height=dp(28),
                pos_hint={"right": 1},
                on_release=lambda x, name=cp["name"], cost=cp["points"]: self.redeem_coupon(name, cost)
            )
            
            card.add_widget(header)
            card.add_widget(desc_lbl)
            card.add_widget(btn)
            grid.add_widget(card)

    def redeem_coupon(self, name, cost):
        if self.user_points >= cost:
            self.user_points -= cost
            
            import random
            barcode = f"PAYKE-{random.randint(1000, 9999)}-{random.randint(10, 99)}"
            
            is_dark = (self.theme_cls.theme_style == "Dark")
            
            box = MDBoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None, height=dp(120))
            box.add_widget(MDLabel(
                text="Show this barcode at the store cashier to redeem your coupon:",
                halign="center",
                font_style="Caption",
                theme_text_color="Secondary"
            ))
            box.add_widget(MDLabel(
                text=barcode,
                halign="center",
                font_style="H5",
                bold=True,
                theme_text_color="Custom",
                text_color=(0.85, 0.65, 0.13, 1.0) if is_dark else (1.0, 0.42, 0.36, 1.0)
            ))
            box.add_widget(MDLabel(
                text="||||| | ||| |||| | || |||| | ||",
                halign="center",
                font_style="H4",
                theme_text_color="Custom",
                text_color=(0.95, 0.95, 0.98, 1) if is_dark else (0.1, 0.1, 0.12, 1)
            ))
            
            dialog = MDDialog(
                title="Redeem Successful!",
                type="custom",
                content_cls=box,
                buttons=[MDRaisedButton(
                    text="Done",
                    md_bg_color=(0.85, 0.65, 0.13, 1.0) if is_dark else (1.0, 0.42, 0.36, 1.0),
                    text_color=(1, 1, 1, 1),
                    on_release=lambda x: dialog.dismiss()
                )]
            )
            dialog.open()
            self.render_coupons()
        else:
            self.show_dialog("Insufficient Points", f"You need {cost} Points to redeem this voucher.\nSpin the Lucky Roulette or scan products to earn more points!")

    # ==================== LUCKY ROULETTE GAMING ====================
    def spin_roulette(self):
        from kivymd.uix.label import MDLabel
        box = MDBoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None, height=dp(110))
        
        status_lbl = MDLabel(
            text="Spinning the Lucky Wheel...",
            halign="center",
            font_style="Subtitle1",
            bold=True,
            theme_text_color="Custom",
            text_color=(1.0, 0.42, 0.36, 1.0)
        )
        points_lbl = MDLabel(
            text="[b]P 0[/b]",
            halign="center",
            font_style="H4",
            markup=True,
            theme_text_color="Custom",
            text_color=(0.0, 0.55, 1.0, 1.0)
        )
        box.add_widget(status_lbl)
        box.add_widget(points_lbl)
        
        dialog = MDDialog(
            title="Lucky Roulette",
            type="custom",
            content_cls=box,
            buttons=[]
        )
        dialog.open()
        
        rewards = [15, 50, 100, 500, 10, 25, 200, 30]
        import random
        reward = random.choice(rewards)
        
        def animate_spin(dt):
            current_tick = getattr(animate_spin, 'tick', 0)
            if current_tick < 8:
                points_lbl.text = f"[b]P {random.choice(rewards)}[/b]"
                animate_spin.tick = current_tick + 1
            else:
                Clock.unschedule(animate_spin)
                points_lbl.text = f"[b]P {reward}[/b]"
                status_lbl.text = f"Congratulations! You won {reward} Points!"
                self.user_points += reward
                
                dialog.buttons = [MDRaisedButton(
                    text="Claim Points",
                    md_bg_color=(1.0, 0.42, 0.36, 1.0),
                    text_color=(1, 1, 1, 1),
                    on_release=lambda x: dialog.dismiss()
                )]
                dialog.update_buttons()
                animate_spin.tick = 0
                
        animate_spin.tick = 0
        Clock.schedule_interval(animate_spin, 0.15)

    # ==================== SCAN RANKING GENERATOR ====================
    def render_rankings(self):
        if not hasattr(self.root, "ids") or "ranking_grid" not in self.root.ids:
            return
        grid = self.root.ids.ranking_grid
        grid.clear_widgets()
        
        # Populate selector chips if empty
        chips_container = self.root.ids.ranking_chips_container
        if len(chips_container.children) == 0:
            ranking_categories = ["All", "Hot items", "Regular items", "Beauty & Body"]
            for rcat in ranking_categories:
                is_active = (rcat == "All")
                chip = CountryChip(
                    text=rcat,
                    active=is_active,
                    on_select=lambda val: self.show_dialog("Filter", f"Filtered rankings by: {val}")
                )
                chips_container.add_widget(chip)
                
        # Curate top 5 products from database
        results = [
            med.search_local_medicines("Loxonin")[0],
            med.search_local_medicines("Pabron Gold")[0],
            med.search_local_medicines("Ohta's Isan")[0],
            med.search_local_medicines("EVE Quick")[0],
            med.search_local_medicines("Allegra FX")[0]
        ]
        
        for idx, item in enumerate(results, start=1):
            grid.add_widget(MobileMedicineCard(item, rank=idx))

    # ==================== AUTHENTICATION CONTROLLERS ====================
    def handle_login(self, method, value=None):
        """Simulates native mobile and social login with credentials and OTP verification."""
        if method == "Google":
            self.show_social_credential_dialog(method)
            return
        elif method in ["Facebook", "Apple", "Yahoo"]:
            self.show_secure_auth_dialog(method)
            return
        elif method == "mobile":
            if not value or not value.strip():
                return
            self.show_mobile_otp_dialog(value)
            return
        elif method == "Guest":
            self.complete_login_flow("Guest")
            return

    def show_secure_auth_dialog(self, provider):
        import webbrowser
        from kivymd.uix.label import MDLabel
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDRaisedButton
        from kivy.metrics import dp
        from kivymd.uix.boxlayout import MDBoxLayout
        
        self.social_provider = provider
        
        urls = {
            "Facebook": "https://www.facebook.com/login",
            "Apple": "https://appleid.apple.com",
            "Yahoo": "https://login.yahoo.com"
        }
        url = urls.get(provider, "https://www.google.com")
        
        # Automatically open the login page in the user's browser
        try:
            webbrowser.open(url)
        except Exception as e:
            print(f"Failed to open browser URL: {e}", flush=True)
            
        # Determine brand color
        brand_colors = {
            "Facebook": (0.2, 0.4, 0.8, 1),
            "Apple": (0.1, 0.1, 0.12, 1),
            "Yahoo": (0.5, 0.2, 0.75, 1)
        }
        brand_color = brand_colors.get(provider, (1.0, 0.42, 0.36, 1))
        
        info_label = MDLabel(
            text=(
                f"We have opened {provider}'s official login page in your browser. "
                "Please sign in there to authorize with PharmaGlobe.\n\n"
                "Once completed, return to the app and click the button below to authorize and log in."
            ),
            font_style="Body2",
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(100)
        )
        
        layout = MDBoxLayout(
            orientation='vertical',
            spacing=dp(10),
            padding=[dp(10), dp(10), dp(10), dp(10)],
            size_hint_y=None,
            height=dp(110)
        )
        layout.add_widget(info_label)
        
        self.social_auth_dialog = MDDialog(
            title=f"🔒 {provider} Secure Authorization",
            type="custom",
            content_cls=layout,
            buttons=[
                MDRaisedButton(
                    text="Authorize & Login",
                    md_bg_color=brand_color,
                    on_release=lambda x: self.process_secure_auth_login()
                ),
                MDRaisedButton(
                    text="Cancel",
                    on_release=lambda x: self.social_auth_dialog.dismiss()
                )
            ]
        )
        self.social_auth_dialog.open()

    def process_secure_auth_login(self):
        provider = getattr(self, "social_provider", "Facebook")
        self.social_auth_dialog.dismiss()
        
        # Create a mock authenticated email/username based on the provider
        email = f"auth_user@{provider.lower()}.com"
        
        print("\n" + "="*50, flush=True)
        print(f"         🔒 {provider.upper()} AUTHENTICATOR AUTHORIZED SUCCESSFUL 🔒         ", flush=True)
        print("="*50, flush=True)
        print(f"Authorized Email: {email}", flush=True)
        print(f"Status          : Token Verified", flush=True)
        print("="*50 + "\n", flush=True)
        
        # Complete login flow
        self.login_method = provider
        self.login_value = email
        self.complete_login_flow(provider, email)


    def show_social_credential_dialog(self, provider):
        from kivymd.uix.textfield import MDTextField
        from kivymd.uix.label import MDLabel
        
        self.social_provider = provider
        
        self.google_email = MDTextField(
            hint_text=f"{provider} Username or Email Address",
            mode="rectangle",
            size_hint_y=None,
            height=dp(48)
        )
        self.google_pass = MDTextField(
            hint_text="Password",
            password=True,
            mode="rectangle",
            size_hint_y=None,
            height=dp(48)
        )
        self.google_info_label = MDLabel(
            text=f"Login to your {provider} account, or register a new one to log in immediately (no OTP code verification required).",
            font_style="Caption",
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(36)
        )
        
        layout = MDBoxLayout(
            orientation='vertical',
            spacing=dp(10),
            padding=[dp(10), dp(10), dp(10), dp(10)],
            size_hint_y=None,
            height=dp(160)
        )
        layout.add_widget(self.google_email)
        layout.add_widget(self.google_pass)
        layout.add_widget(self.google_info_label)
        
        self.login_cred_dialog = MDDialog(
            title=f"🔑 {provider} Login & Register",
            type="custom",
            content_cls=layout,
            buttons=[
                MDRaisedButton(
                    text="Login",
                    md_bg_color=(1.0, 0.42, 0.36, 1),
                    on_release=lambda x: self.process_social_sign_in()
                ),
                MDRaisedButton(
                    text="Create Account",
                    md_bg_color=(0.0, 0.55, 1.0, 1),
                    on_release=lambda x: self.process_social_register()
                ),
                MDRaisedButton(
                    text="Cancel",
                    on_release=lambda x: self.login_cred_dialog.dismiss()
                )
            ]
        )
        self.login_cred_dialog.open()

    def process_social_register(self):
        email = self.google_email.text.strip()
        password = self.google_pass.text.strip()
        
        # Dismiss credentials dialog
        self.login_cred_dialog.dismiss()
        
        # Pre-populate register screen fields if user typed something
        if email:
            self.root.ids.reg_gmail.text = email
        if password:
            self.root.ids.reg_password.text = password
            self.root.ids.reg_confirm_password.text = password
            
        # Direct user to the register screen
        self.root.transition.direction = "left"
        self.root.current = "register_screen"

    def process_social_sign_in(self):
        email = self.google_email.text.strip()
        password = self.google_pass.text.strip()
        provider = getattr(self, "social_provider", "Google")
        
        if not email or not password:
            self.google_info_label.text = "Error: Email and password fields cannot be empty!"
            self.google_info_label.theme_text_color = "Error"
            return
            
        if not hasattr(self, 'registered_accounts'):
            self.registered_accounts = {}
            
        # Pre-seed test account if database is completely empty
        if not self.registered_accounts:
            self.registered_accounts["test@gmail.com"] = {
                "password": "test1234",
                "username": "testuser",
                "first_name": "Test",
                "middle_name": "Not Specified",
                "surname": "User",
                "age": "25",
                "dob": "2001-01-01",
                "height": "175",
                "weight": "70"
            }
            
        # Check if the entered value is a registered gmail address or username
        actual_email = None
        if email in self.registered_accounts:
            actual_email = email
        else:
            for acc_email, acc_details in self.registered_accounts.items():
                if acc_details.get("username") == email:
                    actual_email = acc_email
                    break
                    
        # If the account doesn't exist, notify them
        if not actual_email:
            self.google_info_label.text = "Account not found! Click 'Create Account' to register."
            self.google_info_label.theme_text_color = "Error"
            return
            
        # If password doesn't match
        account_data = self.registered_accounts[actual_email]
        stored_password = account_data["password"] if isinstance(account_data, dict) else account_data
        if stored_password != password:
            self.google_info_label.text = "Incorrect password! Please try again."
            self.google_info_label.theme_text_color = "Error"
            return
            
        # Sign in successful!
        print("\n" + "="*50, flush=True)
        print(f"         🔑 {provider.upper()} USER LOGIN SUCCESSFUL 🔑         ", flush=True)
        print("="*50, flush=True)
        print(f"Username/Email: {actual_email}", flush=True)
        print(f"Password      : {password}", flush=True)
        print("="*50 + "\n", flush=True)
        
        self.login_cred_dialog.dismiss()
        
        # Complete login flow
        self.login_method = provider
        self.login_value = actual_email
        self.complete_login_flow(provider, actual_email)

    def process_new_user_registration(self):
        # Read text fields
        first_name = self.root.ids.reg_first_name.text.strip()
        middle_name = self.root.ids.reg_middle_name.text.strip()
        surname = self.root.ids.reg_surname.text.strip()
        username = self.root.ids.reg_username.text.strip()
        gmail = self.root.ids.reg_gmail.text.strip()
        age = self.root.ids.reg_age.text.strip()
        dob = self.root.ids.reg_dob.text.strip()
        height = self.root.ids.reg_height.text.strip()
        weight = self.root.ids.reg_weight.text.strip()
        password = self.root.ids.reg_password.text.strip()
        confirm_pass = self.root.ids.reg_confirm_password.text.strip()
        
        # Validation
        if not first_name or not surname or not username or not gmail or not age or not dob or not password or not confirm_pass:
            self.show_dialog("Validation Error", "All fields are required except Middle Name, height, and weight.")
            return
            
        if password != confirm_pass:
            self.show_dialog("Validation Error", "Passwords do not match. Please verify your password entry.")
            return
            
        if not hasattr(self, 'registered_accounts'):
            self.registered_accounts = {}
            
        if gmail in self.registered_accounts:
            self.show_dialog("Registration Error", "An account with this gmail/email address already exists!")
            return
            
        # Register the user details
        self.registered_accounts[gmail] = {
            "password": password,
            "username": username,
            "first_name": first_name,
            "middle_name": middle_name if middle_name else "Not Specified",
            "surname": surname,
            "age": age,
            "dob": dob,
            "height": height if height else "Not Specified",
            "weight": weight if weight else "Not Specified"
        }
        
        # Log all credentials to the terminal in real time
        print("\n" + "="*60, flush=True)
        print("        🎉 NEW ACCOUNT REGISTERED SUCCESSFULLY 🎉        ", flush=True)
        print("="*60, flush=True)
        print(f"First Name   : {first_name}", flush=True)
        print(f"Middle Name  : {middle_name if middle_name else 'Not Specified'}", flush=True)
        print(f"Surname      : {surname}", flush=True)
        print(f"Username     : {username}", flush=True)
        print(f"Gmail Address: {gmail}", flush=True)
        print(f"Age          : {age}", flush=True)
        print(f"Date of Birth: {dob}", flush=True)
        print(f"Height (Opt) : {height if height else 'Not Specified'}", flush=True)
        print(f"Weight (Opt) : {weight if weight else 'Not Specified'}", flush=True)
        print(f"Password     : {password}", flush=True)
        print("="*60 + "\n", flush=True)
        
        # Clear fields
        self.root.ids.reg_first_name.text = ""
        self.root.ids.reg_middle_name.text = ""
        self.root.ids.reg_surname.text = ""
        self.root.ids.reg_username.text = ""
        self.root.ids.reg_gmail.text = ""
        self.root.ids.reg_age.text = ""
        self.root.ids.reg_dob.text = ""
        self.root.ids.reg_height.text = ""
        self.root.ids.reg_weight.text = ""
        self.root.ids.reg_password.text = ""
        self.root.ids.reg_confirm_password.text = ""
        
        # Complete login flow directly
        provider = getattr(self, "social_provider", "Google")
        self.login_method = provider
        self.login_value = gmail
        self.complete_login_flow(provider, gmail)

    def show_mobile_otp_dialog(self, phone):
        # Generate 6-digit OTP
        import random
        self.login_otp = str(random.randint(100000, 999999))
        self.login_method = "mobile"
        self.login_value = phone
        
        # Print OTP to terminal
        print("\n" + "="*50, flush=True)
        print("          MOBILE LOGIN ATTEMPT          ", flush=True)
        print("="*50, flush=True)
        print(f"Phone Number: {phone}", flush=True)
        print("-"*50, flush=True)
        print(f"Simulating SMS OTP dispatch to {phone}...", flush=True)
        print(f"--- [SMS OTP Verification Code]: {self.login_otp} ---", flush=True)
        print("="*50 + "\n", flush=True)
        
        self.show_login_otp_dialog(phone)

    def show_login_otp_dialog(self, value):
        from kivymd.uix.textfield import MDTextField
        self.otp_input = MDTextField(
            hint_text="6-Digit Verification Code",
            mode="rectangle",
            size_hint_y=None,
            height=dp(48)
        )
        
        layout = MDBoxLayout(
            orientation='vertical',
            spacing=dp(10),
            padding=[dp(10), dp(10), dp(10), dp(10)],
            size_hint_y=None,
            height=dp(70)
        )
        layout.add_widget(self.otp_input)
        
        self.otp_dialog = MDDialog(
            title="💬 Enter OTP Code",
            text=f"A simulated verification code has been sent to {value}. Please check your terminal logs for the OTP.",
            type="custom",
            content_cls=layout,
            buttons=[
                MDRaisedButton(
                    text="Verify & Login",
                    on_release=lambda x: self.verify_login_otp()
                ),
                MDRaisedButton(
                    text="Cancel",
                    on_release=lambda x: self.otp_dialog.dismiss()
                )
            ]
        )
        self.otp_dialog.open()

    def verify_login_otp(self):
        entered_otp = self.otp_input.text.strip()
        if entered_otp == self.login_otp:
            self.otp_dialog.dismiss()
            # Complete the login
            self.complete_login_flow(self.login_method, self.login_value)
        else:
            self.show_dialog("Invalid OTP", "The verification code you entered is incorrect. Please check the terminal logs for the code.")

    def complete_login_flow(self, method, value=None):
        loader = self.root.ids.login_loader
        loader_text = self.root.ids.loader_text
        
        if method == "mobile":
            loader_text.text = f"Verifying SMS code for {value}..."
        elif method in ["Google", "Facebook", "Apple", "Yahoo"]:
            loader_text.text = f"Verifying {method} OAuth for {value}..."
        elif method == "Guest":
            loader_text.text = "Entering as Guest..."
        else:
            loader_text.text = f"Signing in with {method}..."
            
        loader.opacity = 1
        loader.disabled = False
        
        # Simulate verification latency
        def complete_login(dt):
            loader.opacity = 0
            loader.disabled = True
            
            # Capture selected country and language preferences
            selected_dest = self.root.ids.login_destination_input.text
            selected_language = self.root.ids.login_language_input.text
            
            self.destination_country = selected_dest
            self.current_country = selected_dest
            self.preferred_language = selected_language
            
            # Synchronize Directory location chips and render medicines
            self.populate_location_chips()
            self.render_directory()
            
            self.root.transition.direction = "up"
            self.root.current = "main_screen"
            
        Clock.schedule_once(complete_login, 1.2)

    # ==================== GAME CONTROLLERS ====================
    def play_game(self):
        """Opens a game selection popup letting the user choose between Tic-Tac-Toe and Memory Match."""
        # Create game selection buttons
        layout = MDBoxLayout(
            orientation='vertical',
            spacing=dp(12),
            padding=[dp(10), dp(10), dp(10), dp(10)],
            size_hint_y=None,
            height=dp(110)
        )
        
        btn_ttt = MDRaisedButton(
            text="🎮 Doctor's Tic-Tac-Toe",
            md_bg_color=(1.0, 0.42, 0.36, 1),
            text_color=(1, 1, 1, 1),
            bold=True,
            size_hint_x=1,
            on_release=lambda x: self.start_tic_tac_toe()
        )
        btn_mem = MDRaisedButton(
            text="🧠 Doctor's Memory Match",
            md_bg_color=(0.0, 0.55, 1.0, 1),
            text_color=(1, 1, 1, 1),
            bold=True,
            size_hint_x=1,
            on_release=lambda x: self.start_memory_match()
        )
        
        layout.add_widget(btn_ttt)
        layout.add_widget(btn_mem)
        
        self.game_selection_dialog = MDDialog(
            title="🎮 Choose a Game to Play",
            type="custom",
            content_cls=layout,
            buttons=[
                MDRaisedButton(
                    text="Close",
                    on_release=lambda x: self.game_selection_dialog.dismiss()
                )
            ]
        )
        self.game_selection_dialog.open()

    def start_tic_tac_toe(self):
        """Launches a Tic-Tac-Toe game popup where the user plays against the AI Doctor."""
        if hasattr(self, 'game_selection_dialog') and self.game_selection_dialog:
            self.game_selection_dialog.dismiss()
            
        from kivy.uix.gridlayout import GridLayout
        from kivy.uix.button import Button
        
        # Initialize board state
        self.game_board = [""] * 9
        self.game_buttons = []
        self.game_dialog = None
        
        # Create a grid for the board buttons
        grid = GridLayout(cols=3, spacing=dp(5), size_hint_y=None, height=dp(180))
        
        for i in range(9):
            btn = Button(
                text="",
                font_size="24sp",
                background_color=(0.95, 0.95, 0.95, 1),
                color=(0.1, 0.1, 0.1, 1),
                on_release=lambda x, idx=i: self.make_game_move(idx)
            )
            self.game_buttons.append(btn)
            grid.add_widget(btn)
            
        self.game_status_label = MDLabel(
            text="Your turn (X). Play against the AI Doctor!",
            halign="center",
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(30)
        )
        
        layout = MDBoxLayout(
            orientation='vertical',
            spacing=dp(10),
            padding=[dp(10), dp(10), dp(10), dp(10)],
            size_hint_y=None,
            height=dp(230)
        )
        layout.add_widget(self.game_status_label)
        layout.add_widget(grid)
        
        self.game_dialog = MDDialog(
            title="🎮 Doctor's Tic-Tac-Toe",
            type="custom",
            content_cls=layout,
            buttons=[
                MDRaisedButton(
                    text="Reset Game",
                    on_release=lambda x: self.reset_game()
                ),
                MDRaisedButton(
                    text="Close",
                    on_release=lambda x: self.game_dialog.dismiss()
                )
            ]
        )
        self.game_dialog.open()

    def start_memory_match(self):
        """Launches a Memory Match game popup."""
        if hasattr(self, 'game_selection_dialog') and self.game_selection_dialog:
            self.game_selection_dialog.dismiss()
            
        from kivy.uix.gridlayout import GridLayout
        from kivy.uix.button import Button
        import random
        
        # Game state for memory match
        # 8 pairs of symbols = 16 cards
        symbols = ["🩺", "💊", "🩹", "💉", "🏥", "🧬", "🧪", "🌡️"] * 2
        random.shuffle(symbols)
        
        self.memory_board = symbols
        self.memory_revealed = [False] * 16
        self.memory_selected = []
        self.memory_buttons = []
        self.memory_dialog = None
        self.memory_busy = False # To prevent clicking during mismatch flip delay
        
        # Create a grid for the memory board (4x4)
        grid = GridLayout(cols=4, spacing=dp(6), size_hint_y=None, height=dp(240))
        
        for i in range(16):
            btn = Button(
                text="?",
                font_size="24sp",
                background_color=(0.9, 0.9, 0.9, 1),
                color=(0.3, 0.3, 0.3, 1),
                on_release=lambda x, idx=i: self.make_memory_move(idx)
            )
            self.memory_buttons.append(btn)
            grid.add_widget(btn)
            
        self.memory_status_label = MDLabel(
            text="Tap cards to find the matching medical pairs!",
            halign="center",
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(30)
        )
        
        layout = MDBoxLayout(
            orientation='vertical',
            spacing=dp(10),
            padding=[dp(10), dp(10), dp(10), dp(10)],
            size_hint_y=None,
            height=dp(290)
        )
        layout.add_widget(self.memory_status_label)
        layout.add_widget(grid)
        
        self.memory_dialog = MDDialog(
            title="🧠 Doctor's Memory Match",
            type="custom",
            content_cls=layout,
            buttons=[
                MDRaisedButton(
                    text="Reset Game",
                    on_release=lambda x: self.reset_memory_game()
                ),
                MDRaisedButton(
                    text="Close",
                    on_release=lambda x: self.memory_dialog.dismiss()
                )
            ]
        )
        self.memory_dialog.open()

    def make_memory_move(self, idx):
        if self.memory_busy or self.memory_revealed[idx] or idx in self.memory_selected:
            return
            
        # Reveal card
        self.memory_buttons[idx].text = self.memory_board[idx]
        self.memory_buttons[idx].background_color = (1.0, 0.9, 0.9, 1) # Highlight revealed
        self.memory_buttons[idx].color = (1.0, 0.42, 0.36, 1)
        self.memory_selected.append(idx)
        
        if len(self.memory_selected) == 2:
            self.memory_busy = True
            idx1, idx2 = self.memory_selected
            if self.memory_board[idx1] == self.memory_board[idx2]:
                # Match found!
                self.memory_revealed[idx1] = True
                self.memory_revealed[idx2] = True
                
                # Keep them highlighted green
                self.memory_buttons[idx1].background_color = (0.9, 1.0, 0.9, 1)
                self.memory_buttons[idx1].color = (0.1, 0.7, 0.1, 1)
                self.memory_buttons[idx2].background_color = (0.9, 1.0, 0.9, 1)
                self.memory_buttons[idx2].color = (0.1, 0.7, 0.1, 1)
                
                self.memory_selected = []
                self.memory_busy = False
                
                # Check for win
                if all(self.memory_revealed):
                    self.memory_status_label.text = "🎉 You matched all cards! +50 Health Points!"
                    self.user_points += 50
                else:
                    self.memory_status_label.text = "Nice! You found a match!"
            else:
                # No match
                self.memory_status_label.text = "Not a match! Try again..."
                # Flip back after 0.8 seconds
                Clock.schedule_once(lambda dt: self.flip_back_cards(idx1, idx2), 0.8)

    def flip_back_cards(self, idx1, idx2):
        self.memory_buttons[idx1].text = "?"
        self.memory_buttons[idx1].background_color = (0.9, 0.9, 0.9, 1)
        self.memory_buttons[idx1].color = (0.3, 0.3, 0.3, 1)
        
        self.memory_buttons[idx2].text = "?"
        self.memory_buttons[idx2].background_color = (0.9, 0.9, 0.9, 1)
        self.memory_buttons[idx2].color = (0.3, 0.3, 0.3, 1)
        
        self.memory_selected = []
        self.memory_busy = False
        self.memory_status_label.text = "Tap cards to find matching pairs."

    def reset_memory_game(self):
        import random
        symbols = ["🩺", "💊", "🩹", "💉", "🏥", "🧬", "🧪", "🌡️"] * 2
        random.shuffle(symbols)
        self.memory_board = symbols
        self.memory_revealed = [False] * 16
        self.memory_selected = []
        self.memory_busy = False
        
        for btn in self.memory_buttons:
            btn.text = "?"
            btn.background_color = (0.9, 0.9, 0.9, 1)
            btn.color = (0.3, 0.3, 0.3, 1)
            
        self.memory_status_label.text = "Tap cards to find the matching medical pairs!"

    def make_game_move(self, idx):
        if self.game_board[idx] != "" or self.check_game_winner():
            return
            
        # User move
        self.game_board[idx] = "X"
        self.game_buttons[idx].text = "X"
        self.game_buttons[idx].color = (1.0, 0.42, 0.36, 1) # Red accent for user
        self.game_buttons[idx].background_color = (1.0, 0.9, 0.9, 1)
        
        # Check if user won
        winner = self.check_game_winner()
        if winner == "X":
            self.game_status_label.text = "🎉 You won! +50 Health Points added!"
            self.user_points += 50
            return
        elif "" not in self.game_board:
            self.game_status_label.text = "🤝 It's a draw!"
            return
            
        # AI move (simple random empty spot)
        self.game_status_label.text = "Doctor is thinking..."
        Clock.schedule_once(lambda dt: self.make_ai_move(), 0.5)

    def make_ai_move(self):
        if "" not in self.game_board or self.check_game_winner():
            return
            
        import random
        empty_indices = [i for i, val in enumerate(self.game_board) if val == ""]
        if empty_indices:
            ai_idx = random.choice(empty_indices)
            self.game_board[ai_idx] = "O"
            self.game_buttons[ai_idx].text = "O"
            self.game_buttons[ai_idx].color = (0, 0.55, 1.0, 1) # Blue accent for doctor
            self.game_buttons[ai_idx].background_color = (0.9, 0.95, 1.0, 1)
            
            winner = self.check_game_winner()
            if winner == "O":
                self.game_status_label.text = "🤖 Doctor won! Try again!"
            elif "" not in self.game_board:
                self.game_status_label.text = "🤝 It's a draw!"
            else:
                self.game_status_label.text = "Your turn (X)."

    def check_game_winner(self):
        win_coords = [
            (0, 1, 2), (3, 4, 5), (6, 7, 8), # rows
            (0, 3, 6), (1, 4, 7), (2, 5, 8), # cols
            (0, 4, 8), (2, 4, 6)             # diagonals
        ]
        for c1, c2, c3 in win_coords:
            if self.game_board[c1] != "" and self.game_board[c1] == self.game_board[c2] == self.game_board[c3]:
                return self.game_board[c1]
        return None

    def reset_game(self):
        self.game_board = [""] * 9
        for btn in self.game_buttons:
            btn.text = ""
            btn.background_color = (0.95, 0.95, 0.95, 1)
        self.game_status_label.text = "Your turn (X). Play against the AI Doctor!"

    def handle_logout(self):
        """Logs the user out and slides down back to the login screen."""
        self.root.transition.direction = "down"
        self.root.current = "login_screen"
        self.root.ids.phone_input.text = ""

    # ==================== LOGIN PREFERENCES DROPDOWNS ====================
    def open_detail_comparison_menu(self, button, med):
        """Opens dropdown menu to select home country for comparison inside details view."""
        import med_database
        countries = med_database.get_countries()
        menu_items = [{
            "viewclass": "OneLineListItem",
            "text": c,
            "on_release": lambda x=c: self.set_detail_comparison_country(x, button, med)
        } for c in countries]
        
        self.detail_comp_menu = MDDropdownMenu(
            caller=button,
            items=menu_items,
            width_mult=4
        )
        self.detail_comp_menu.open()

    def set_detail_comparison_country(self, country_name, button, med):
        self.home_country = country_name
        if hasattr(button, 'text'):
            button.text = f"{country_name} ▾"
        self.detail_comp_menu.dismiss()
        self._show_details_dialog(med)

    def open_login_destination_menu(self, text_field):
        """Opens dropdown menu to select destination travel country during login."""
        text_field.focus = False
        countries = ["Global (All)"] + med.get_countries()
        menu_items = [{
            "viewclass": "OneLineListItem",
            "text": c,
            "on_release": lambda x=c: self.set_login_destination_country(x, text_field)
        } for c in countries]
        
        self.login_dest_menu = MDDropdownMenu(
            caller=text_field,
            items=menu_items,
            width_mult=4
        )
        self.login_dest_menu.open()

    def set_login_destination_country(self, country_name, text_field):
        text_field.text = country_name
        self.login_dest_menu.dismiss()

    def open_login_language_menu(self, text_field):
        """Opens dropdown menu to select preferred language during login."""
        text_field.focus = False
        languages = ["English", "Japanese", "Spanish", "French", "German", "Korean", "Hindi", "Nepali", "Chinese"]
        menu_items = [{
            "viewclass": "OneLineListItem",
            "text": l,
            "on_release": lambda x=l: self.set_login_language(x, text_field)
        } for l in languages]
        
        self.login_language_menu = MDDropdownMenu(
            caller=text_field,
            items=menu_items,
            width_mult=4
        )
        self.login_language_menu.open()

    def set_login_language(self, language_name, text_field):
        text_field.text = language_name
        self.login_language_menu.dismiss()

    # ==================== CHIPS GENERATORS & LISTENERS ====================
    def populate_location_chips(self):
        if not hasattr(self.root, 'ids') or 'country_chips_container' not in self.root.ids:
            return
        container = self.root.ids.country_chips_container
        container.clear_widgets()
        
        locations = [
            ("Global (All)", "Global"),
            ("Japan", "Japan"),
            ("France", "France"),
            ("Spain", "Spain"),
            ("Germany", "Germany"),
            ("South Korea", "S. Korea"),
            ("USA", "USA"),
            ("UK", "UK"),
            ("India", "India")
        ]
        
        # If user logged in targeting a specific destination country, only show that country chip
        dest = getattr(self, "destination_country", "Global (All)")
        if dest != "Global (All)":
            locations = [loc for loc in locations if loc[0] == dest]
            
        for name, label in locations:
            is_active = (name == self.current_country)
            chip = CountryChip(
                text=label,
                active=is_active,
                on_select=lambda val, n=name: self.select_location_chip(n)
            )
            container.add_widget(chip)
            
    def select_location_chip(self, country_name):
        self.current_country = country_name
        self.populate_location_chips()
        self.populate_category_chips()
        self.render_directory()

    def populate_category_chips(self):
        if not hasattr(self.root, 'ids') or 'category_chips_container' not in self.root.ids:
            return
        container = self.root.ids.category_chips_container
        container.clear_widgets()
        
        categories = [
            ("All", "border-all"),
            ("Pain Reliever", "pill"),
            ("Cold & Flu", "thermometer"),
            ("Digestive Health", "bottle-tonic-plus"),
            ("Allergy", "flower")
        ]
        
        for name, icon in categories:
            is_active = (name == self.current_category)
            chip = CategoryChip(
                text=name,
                icon_name=icon,
                active=is_active,
                on_select=lambda val, n=name: self.select_category_chip(n)
            )
            container.add_widget(chip)
            
    def select_category_chip(self, category_name):
        self.current_category = category_name
        self.populate_category_chips()
        self.render_directory()

    def populate_popular_searches(self):
        if not hasattr(self.root, 'ids') or 'popular_search_chips' not in self.root.ids:
            return
        container = self.root.ids.popular_search_chips
        container.clear_widgets()
        
        tags = ["Loxonin S", "Tylenol", "Headache", "Fever", "Indigestion", "Allergy"]
        for tag in tags:
            chip = CountryChip(
                text=tag,
                active=False,
                on_select=lambda val: self.trigger_popular_search(val)
            )
            chip.size = (95, 34)
            container.add_widget(chip)
            
    def trigger_popular_search(self, term):
        self.root.ids.search_field.text = term.strip()
        self.execute_search()

    # ==================== NETWORK STATUS CONTROLLERS ====================
    def check_connection(self):
        """Asynchronously tests connection to update UI states in a background thread."""
        def run_check():
            try:
                # Run the blocking network call in a background thread
                res = requests.get("https://api.fda.gov", timeout=1.5)
                online = True
            except Exception:
                online = False
            # Safely set is_online on the main thread
            Clock.schedule_once(lambda dt: setattr(self, 'is_online', online), 0)
        threading.Thread(target=run_check, daemon=True).start()

    def animate_status_led(self, dt):
        if not hasattr(self.root, 'ids') or 'status_led' not in self.root.ids:
            return
        led = self.root.ids.status_led
        if self.is_online:
            # Pulsing Green (toggle opacity between 1.0 and 0.2)
            self.led_state = not getattr(self, 'led_state', True)
            led.md_bg_color = [0.08, 0.94, 0.4, 1.0 if self.led_state else 0.2]
        else:
            # Solid Red
            led.md_bg_color = [0.9, 0.1, 0.1, 1.0]

    # ==================== DIRECTORY VIEW CONTROLLERS ====================
    def render_directory(self):
        """Displays filtered cards list in the directory grid."""
        grid = self.root.ids.directory_grid
        grid.clear_widgets()
        
        country = None if self.current_country == "Global (All)" else self.current_country
        category = None if self.current_category == "All" else self.current_category
        
        meds = med.get_medicines_by_filters(country=country, category=category)
        
        if not meds:
            grid.add_widget(MDLabel(
                text="No curated medicines found in this category/location.",
                halign="center",
                theme_text_color="Secondary",
                size_hint_y=None,
                height=100
            ))
            return
            
        for item in meds:
            grid.add_widget(MobileMedicineCard(item))

    def open_country_menu(self, button):
        """Builds and opens the dropdown selector for countries."""
        countries = ["Global (All)"] + med.get_countries()
        menu_items = [{
            "viewclass": "OneLineListItem",
            "text": c,
            "on_release": lambda x=c: self.set_country(x)
        } for c in countries]
        
        self.country_menu = MDDropdownMenu(
            caller=button,
            items=menu_items,
            width_mult=4
        )
        self.country_menu.open()

    def set_country(self, country_name):
        self.current_country = country_name
        self.root.ids.country_btn.text = f"Location: {country_name}"
        self.country_menu.dismiss()
        self.render_directory()

    def open_category_menu(self, button):
        """Builds and opens the dropdown selector for categories."""
        country = None if self.current_country == "Global (All)" else self.current_country
        categories = ["All"] + med.get_categories(country=country)
        menu_items = [{
            "viewclass": "OneLineListItem",
            "text": cat,
            "on_release": lambda x=cat: self.set_category(x)
        } for cat in categories]
        
        self.category_menu = MDDropdownMenu(
            caller=button,
            items=menu_items,
            width_mult=4
        )
        self.category_menu.open()

    def set_category(self, cat_name):
        self.current_category = cat_name
        self.root.ids.category_btn.text = f"Category: {cat_name}"
        self.category_menu.dismiss()
        self.render_directory()

    # ==================== SEARCH TAB CONTROLLERS ====================
    def toggle_search_source(self):
        if self.search_source == "Local Database":
            self.search_source = "OpenFDA Directory"
        elif self.search_source == "OpenFDA Directory":
            self.search_source = "Global Online Search"
        else:
            self.search_source = "Local Database"
        self.root.ids.search_source_btn.text = self.search_source

    def execute_search(self):
        query = self.root.ids.search_field.text.strip()
        grid = self.root.ids.search_grid
        grid.clear_widgets()
        
        if not query:
            return
            
        if self.search_source == "Local Database":
            results = med.search_local_medicines(query)
            for m in results:
                grid.add_widget(MobileMedicineCard(m))
        elif self.search_source == "OpenFDA Directory":
            if not self.is_online:
                dialog = MDDialog(
                    title="Offline",
                    text="Internet connectivity is required to query live OpenFDA. Switch to Local Database source.",
                    buttons=[MDRaisedButton(text="OK", on_release=lambda x: dialog.dismiss())]
                )
                dialog.open()
                return
                
            # Perform API search in a background thread to prevent UI locking
            threading.Thread(target=self._run_fda_search_thread, args=(query,), daemon=True).start()
        elif self.search_source == "Global Online Search":
            if not self.is_online:
                dialog = MDDialog(
                    title="Offline",
                    text="Internet connectivity is required for Global Online Search. Switch to Local Database source.",
                    buttons=[MDRaisedButton(text="OK", on_release=lambda x: dialog.dismiss())]
                )
                dialog.open()
                return
                
            # Perform API search in a background thread to prevent UI locking
            threading.Thread(target=self._run_global_search_thread, args=(query,), daemon=True).start()

    def _run_fda_search_thread(self, query):
        fda_res = openfda_helper.search_openfda_by_name(query, limit=5)
        Clock.schedule_once(lambda dt: self._update_fda_search_ui(fda_res), 0)

    def _update_fda_search_ui(self, fda_res):
        grid = self.root.ids.search_grid
        grid.clear_widgets()
        if not fda_res:
            grid.add_widget(MDLabel(text="No results found in OpenFDA.", halign="center"))
            return
            
        for m in fda_res:
            m_card = {
                "name": m["brand_name"],
                "generic_name": m["generic_name"],
                "category": m["product_type"],
                "uses": [m["uses"]],
                "dosage": m["dosage"],
                "warnings": [m["warnings"]],
                "precautions": m["precautions"],
                "price": "FDA OTC Product",
                "shop_link": f"https://www.google.com/search?q={m['brand_name']}",
                "resolved_via": "OpenFDA API",
                "country": "USA",
                "image_url": m.get("image_url", "")
            }
            grid.add_widget(MobileMedicineCard(m_card))

    def _run_global_search_thread(self, query):
        import online_resolver
        res = online_resolver.search_medicine_globally_online(query)
        Clock.schedule_once(lambda dt: self._update_global_search_ui(res), 0)

    def _update_global_search_ui(self, res):
        grid = self.root.ids.search_grid
        grid.clear_widgets()
        if not res:
            grid.add_widget(MDLabel(text="No results found in global online databases.", halign="center"))
            return
        grid.add_widget(MobileMedicineCard(res))

    # ==================== BARCODE SCANNER CONTROLLERS ====================
    def init_camera_widget(self):
        """Dynamically instantiates Kivy Camera only on demand to prevent Android permission startup crashes."""
        if hasattr(self.root, "ids") and "scanner_camera" in self.root.ids:
            return self.root.ids.scanner_camera
            
        from kivy.uix.camera import Camera
        cam = Camera(
            resolution=(640, 480),
            play=False,
            keep_ratio=True,
            allow_stretch=True
        )
        self.root.ids.camera_container.add_widget(cam)
        self.root.ids["scanner_camera"] = cam
        return cam

    def start_camera(self):
        """Fires up the camera feed when the user switches to scanner."""
        from kivy.utils import platform
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.CAMERA])
            
        try:
            cam = self.init_camera_widget()
            cam.play = True
        except Exception as e:
            print(f"[Scanner] Failed to initialize camera: {e}")
            self.show_dialog(
                "Camera Permission Required", 
                "PharmaGlobe requires camera access to scan barcodes. Please enable camera permission in your phone settings."
            )
            return
            
        self.scan_paused = False
        self.is_scanning_frame = False
        
        # Start automatic background frame scanning loop (ticks every 0.3s)
        if not self.auto_scan_event:
            self.auto_scan_event = Clock.schedule_interval(self.auto_scan_tick, 0.3)
            print("[Scanner] Automatic live barcode scanning loop started.")

    def stop_camera(self):
        """Stops the camera feed and automatic scanning loop."""
        if hasattr(self.root, "ids") and "scanner_camera" in self.root.ids:
            self.root.ids.scanner_camera.play = False
        if self.auto_scan_event:
            self.auto_scan_event.cancel()
            self.auto_scan_event = None
            print("[Scanner] Automatic live barcode scanning loop stopped.")

    def auto_scan_tick(self, dt):
        """Tick event that captures the current texture frame and decodes it in the background."""
        if not hasattr(self.root, "ids") or "scanner_camera" not in self.root.ids:
            return
            
        if self.scan_paused or not self.root.ids.scanner_camera.play:
            return
            
        if self.is_scanning_frame:
            return
            
        cam = self.root.ids.scanner_camera
        if not cam.texture:
            return
            
        try:
            # Capture frame directly from GPU texture memory (instant, no file writing lags)
            size = cam.texture.size
            pixels = cam.texture.pixels
            colorfmt = cam.texture.colorfmt.upper()
            if colorfmt in ['RGBA', 'BGRA']:
                pil_img = PILImage.frombytes('RGBA', size, pixels)
            else:
                pil_img = PILImage.frombytes('RGB', size, pixels)
                
            self.is_scanning_frame = True
            threading.Thread(target=self._auto_scan_frame_thread, args=(pil_img,), daemon=True).start()
        except Exception as e:
            pass

    def _auto_scan_frame_thread(self, pil_img):
        try:
            code, code_type = barcode_helper.decode_barcode(pil_img)
            if code:
                # Successfully resolved a barcode in the live feed!
                print(f"[AutoScan] Detected barcode: {code} ({code_type})")
                Clock.schedule_once(lambda dt: self.handle_auto_scan_success(code), 0)
            else:
                self.is_scanning_frame = False
        except Exception as e:
            self.is_scanning_frame = False

    def handle_auto_scan_success(self, code):
        self.scan_paused = True  # Pause scanning to show details dialog/page
        self.is_scanning_frame = False
        self.resolve_barcode(code)

    def capture_and_scan(self):
        """Manual capture fallback trigger (keeps button active as an option)."""
        cam = self.root.ids.scanner_camera
        if not cam.play:
            return
            
        self.scan_paused = True
        pil_img = None
        if cam.texture:
            try:
                size = cam.texture.size
                pixels = cam.texture.pixels
                colorfmt = cam.texture.colorfmt.upper()
                if colorfmt in ['RGBA', 'BGRA']:
                    pil_img = PILImage.frombytes('RGBA', size, pixels)
                else:
                    pil_img = PILImage.frombytes('RGB', size, pixels)
            except Exception as e:
                pass
                
        if pil_img:
            threading.Thread(target=self._scan_frame_thread, args=(pil_img,), daemon=True).start()
        else:
            self.show_dialog(
                "Scan Failed", 
                "Could not capture frame from the camera stream.",
                on_dismiss=lambda: setattr(self, "scan_paused", False)
            )

    def _scan_frame_thread(self, pil_img):
        code, code_type = barcode_helper.decode_barcode(pil_img)
        if code:
            Clock.schedule_once(lambda dt: self.resolve_barcode(code), 0)
        else:
            def resume():
                self.scan_paused = False
                self.is_scanning_frame = False
            Clock.schedule_once(lambda dt: self.show_dialog(
                "Scan Failed", 
                "No barcode detected in the frame. Make sure the lighting is bright, the code is close to the lens, and the image is in focus.",
                on_dismiss=resume
            ), 0)

    def execute_manual_scan(self):
        barcode = self.root.ids.manual_barcode_field.text.strip()
        if barcode:
            self.scan_paused = True
            self.resolve_barcode(barcode)

    def resolve_barcode(self, barcode):
        """Searches registries for the barcode in a background thread."""
        threading.Thread(target=self._resolve_barcode_thread, args=(barcode,), daemon=True).start()

    def _resolve_barcode_thread(self, barcode):
        resolved = barcode_helper.lookup_barcode_in_databases(barcode)
        Clock.schedule_once(lambda dt: self._show_barcode_result_ui(resolved, barcode), 0)

    def _show_barcode_result_ui(self, resolved, barcode):
        if resolved:
            card_data = {
                "name": resolved.get("brand_name", resolved.get("name", "Unknown Brand")),
                "generic_name": resolved.get("generic_name", "Unknown Active Ingredient"),
                "category": resolved.get("category", resolved.get("product_type", "OTC Medicine")),
                "country": resolved.get("country", "Global Database"),
                "uses": resolved.get("uses", "No usage details found."),
                "benefits": resolved.get("benefits", []),
                "dosage": resolved.get("dosage", "Refer to package instructions."),
                "warnings": resolved.get("warnings", []),
                "precautions": resolved.get("precautions", ""),
                "price": resolved.get("price", ""),
                "shop_link": resolved.get("shop_link", ""),
                "resolved_via": resolved.get("resolved_via", "Barcode Scan"),
                "image_url": resolved.get("image_url", "")
            }
            self.show_medication_details(card_data)
        else:
            def resume():
                self.scan_paused = False
                self.is_scanning_frame = False
            self.show_dialog(
                "Not Found", 
                f"Barcode `{barcode}` could not be resolved in the registries.",
                on_dismiss=resume
            )

    # ==================== AI CHAT CONTROLLERS ====================
    def toggle_chat_persona(self):
        if self.chat_persona == "🩺 AI Health Consultant":
            self.chat_persona = "💻 Codebase Dev Assistant"
        else:
            self.chat_persona = "🩺 AI Health Consultant"
        self.root.ids.chat_persona_btn.text = self.chat_persona
        self.render_chat_feed()

    def clear_chat(self):
        if self.chat_persona == "🩺 AI Health Consultant":
            self.health_chat_history = [{
                "role": "assistant",
                "content": "Hello! I am your AI Health Consultant. Describe symptoms, ask about health problems, or ask for regional OTC medicine recommendations."
            }]
        else:
            self.dev_chat_history = [{
                "role": "assistant",
                "content": "Hello! I am the lead Developer of PharmaGlobe Mobile. I can explain the KivyMD frontend, Buildozer packaging specs, OpenCV scanners, or help you write code."
            }]
        self.render_chat_feed()

    def render_chat_feed(self):
        """Redraws the chat feed based on active persona's history."""
        feed = self.root.ids.chat_grid
        feed.clear_widgets()
        
        history = self.health_chat_history if self.chat_persona == "🩺 AI Health Consultant" else self.dev_chat_history
        
        for msg in history:
            feed.add_widget(ChatBubble(msg["role"], msg["content"]))
            
        # Scroll to bottom after drawing
        Clock.schedule_once(lambda dt: self.scroll_chat_to_bottom(), 0.1)

    def scroll_chat_to_bottom(self):
        self.root.ids.chat_scroll.scroll_y = 0

    def send_chat_message(self):
        user_text = self.root.ids.chat_input_field.text.strip()
        if not user_text:
            return
            
        # Clear field
        self.root.ids.chat_input_field.text = ""
        
        # Add to local history
        target_history = self.health_chat_history if self.chat_persona == "🩺 AI Health Consultant" else self.dev_chat_history
        target_history.append({"role": "user", "content": user_text})
        
        self.render_chat_feed()
        
        # Trigger response generation
        Clock.schedule_once(lambda dt: self._generate_ai_response(user_text), 0.1)

    def _generate_ai_response(self, user_msg):
        target_history = self.health_chat_history if self.chat_persona == "🩺 AI Health Consultant" else self.dev_chat_history
        
        # Add a visual "Thinking" bubble
        chat_grid = self.root.ids.chat_grid
        thinking_bubble = ChatBubble("assistant", "AI is thinking...")
        chat_grid.add_widget(thinking_bubble)
        Clock.schedule_once(lambda dt: self.scroll_chat_to_bottom(), 0.1)
        
        def run_ai():
            try:
                response = ai_helper.generate_chat_response(
                    persona=self.chat_persona,
                    chat_history=target_history[:-1],  # Exclude current prompt
                    user_message=user_msg,
                    api_key=self.gemini_key,
                    preferred_language=getattr(self, "preferred_language", "English"),
                    current_country=self.current_country,
                    home_country=getattr(self, "home_country", "USA")
                )
            except Exception as e:
                response = f"Error generating response: {e}"
                
            def update_ui(dt):
                chat_grid.remove_widget(thinking_bubble)
                target_history.append({"role": "assistant", "content": response})
                self.render_chat_feed()
            Clock.schedule_once(update_ui, 0)
            
        threading.Thread(target=run_ai, daemon=True).start()

    # ==================== SETTINGS DIALOGS ====================
    def show_key_dialog(self):
        """Displays dialog box to enter Gemini API key securely."""
        from kivymd.uix.textfield import MDTextField
        
        box = MDBoxLayout(orientation='vertical', spacing=10, size_hint_y=None, height=100)
        key_input = MDTextField(
            hint_text="Paste Gemini API Key",
            password=True,
            text=self.gemini_key,
            line_color_focus=(1.0, 0.42, 0.36, 1.0)
        )
        box.add_widget(key_input)
        
        def save_key(x):
            self.gemini_key = key_input.text.strip()
            self.show_dialog("Saved", "Gemini API Key configured successfully.")
            self.key_dialog.dismiss()
            
        self.key_dialog = MDDialog(
            title="🔑 API Configuration",
            type="custom",
            content_cls=box,
            buttons=[
                MDRaisedButton(
                    text="Cancel",
                    md_bg_color=(0.9, 0.91, 0.94, 1.0),
                    text_color=(0.1, 0.1, 0.12, 1.0),
                    on_release=lambda x: self.key_dialog.dismiss()
                ),
                MDRaisedButton(
                    text="Save Key",
                    on_release=save_key,
                    md_bg_color=(1.0, 0.42, 0.36, 1.0),
                    text_color=(1.0, 1.0, 1.0, 1.0)
                )
            ]
        )
        self.key_dialog.open()

    # ==================== UTILITY POPUPS ====================
    def show_dialog(self, title, text, on_dismiss=None):
        def handle_dismiss(x):
            dialog.dismiss()
            if on_dismiss:
                on_dismiss()
        dialog = MDDialog(
            title=title,
            text=text,
            buttons=[MDRaisedButton(text="Close", on_release=handle_dismiss)]
        )
        dialog.open()

    def go_back_to_main(self):
        self.root.transition.direction = "right"
        self.root.current = "main_screen"
        # Resume automatic live scanning
        self.scan_paused = False
        self.is_scanning_frame = False

    def show_medication_details(self, med):
        """Constructs a detailed popup displaying the medicine's specifications."""
        self.current_med = med
        
        # Load user preferred language selected on login
        preferred_lang = getattr(self, "preferred_language", "English")
        self.current_language = preferred_lang
        self.populate_language_chips()
        
        # Immediately transition to details screen
        if self.root.current != "details_screen":
            self.root.transition.direction = "left"
            self.root.current = "details_screen"
            
        # Immediately display local details
        self._show_details_dialog(med)
        
        # Automatically translate in the background if needed
        if self.current_language != "English":
            self.translate_current_medicine(self.current_language)
            
        # If online and no image_url, resolve it in background in parallel
        if self.is_online and not med.get("image_url"):
            threading.Thread(target=self._resolve_med_image_thread, args=(med,), daemon=True).start()

    def populate_language_chips(self):
        if not hasattr(self.root, 'ids') or 'language_chips_container' not in self.root.ids:
            return
        container = self.root.ids.language_chips_container
        container.clear_widgets()
        
        languages = [
            ("English", "English"),
            ("Japanese", "Japanese"),
            ("French", "French"),
            ("Spanish", "Spanish"),
            ("German", "German"),
            ("Korean", "Korean"),
            ("Hindi", "Hindi"),
            ("Nepali", "Nepali"),
            ("Chinese", "Chinese")
        ]
        
        for name, label in languages:
            is_active = (name == self.current_language)
            chip = CountryChip(
                text=label,
                active=is_active,
                on_select=lambda val, n=name: self.select_language_chip(n)
            )
            container.add_widget(chip)

    def select_language_chip(self, lang_name):
        self.current_language = lang_name
        self.populate_language_chips()
        self.translate_current_medicine(lang_name)

    def translate_current_medicine(self, target_lang):
        """Translates the active medicine details to the target language and rerenders."""
        if not hasattr(self, 'current_med') or not self.current_med:
            return
        
        # If English, just restore original and render
        if target_lang == "English":
            self._show_details_dialog(self.current_med)
            return
            
        # Check cache first
        med_id = self.current_med.get("name", "")
        cache_key = f"{med_id}_{target_lang}"
        if hasattr(self, 'translation_cache') and cache_key in self.translation_cache:
            self._show_details_dialog(self.translation_cache[cache_key])
            return
            
        # Show loader in details container
        container = self.root.ids.details_info_container
        container.clear_widgets()
        
        from kivymd.uix.label import MDLabel
        container.add_widget(MDLabel(
            text=f"Translating details to {target_lang} using AI...",
            halign="center",
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(100)
        ))
        
        import threading
        
        def run_translation():
            try:
                med = self.current_med.copy()
                api_key = self.gemini_key
                
                fields_to_translate = []
                idx_map = {}
                current_idx = 1
                
                for field in ["uses", "benefits", "dosage", "warnings", "online_description"]:
                    val = med.get(field)
                    if val:
                        fields_to_translate.append((current_idx, field, val))
                        idx_map[current_idx] = (field, isinstance(val, list))
                        current_idx += 1
                
                if fields_to_translate:
                    combined_lines = []
                    for idx, field, val in fields_to_translate:
                        if isinstance(val, list):
                            val_str = "\n".join(val)
                        else:
                            val_str = str(val)
                        combined_lines.append(f"###{idx}###")
                        combined_lines.append(val_str)
                    
                    combined_text = "\n".join(combined_lines)
                    translated_text = ai_helper.translate_text(combined_text, target_lang, api_key)
                    
                    if not translated_text.startswith("[Translation Offline"):
                        import re
                        parts = re.split(r'###\s*(\d+)\s*###', translated_text)
                        
                        parsed_translations = {}
                        temp_idx = None
                        for part in parts:
                            if not part:
                                continue
                            if part.strip().isdigit():
                                temp_idx = int(part.strip())
                            elif temp_idx is not None:
                                parsed_translations[temp_idx] = part.strip()
                        
                        for idx, (field_name, is_list) in idx_map.items():
                            translated_val = parsed_translations.get(idx)
                            if translated_val:
                                if is_list:
                                    med[field_name] = [line.strip().lstrip('•-* ').strip() for line in translated_val.split("\n") if line.strip()]
                                else:
                                    med[field_name] = translated_val
                
                # Cache it
                if not hasattr(self, 'translation_cache'):
                    self.translation_cache = {}
                self.translation_cache[cache_key] = med
                
                # Render on main thread
                Clock.schedule_once(lambda dt: self._show_details_dialog(med), 0)
            except Exception as e:
                print(f"Error in translation thread: {e}")
                # Fallback to original
                Clock.schedule_once(lambda dt: self._show_details_dialog(self.current_med), 0)
                
        threading.Thread(target=run_translation, daemon=True).start()

    def _resolve_med_image_thread(self, med):
        import online_resolver
        # Try to search globally online for this specific medicine name
        online_data = online_resolver.search_medicine_globally_online(med["name"])
        if online_data and online_data.get("image_url"):
            img_url = online_data["image_url"]
        else:
            img_url = ""
            # Try searching by generic name
            generic = med.get("generic_name", "")
            if generic:
                online_data = online_resolver.search_medicine_globally_online(generic)
                if online_data and online_data.get("image_url"):
                    img_url = online_data["image_url"]
                    
        # Update active medicine reference and cache if found
        if img_url:
            def update_image_ui(dt):
                med["image_url"] = img_url
                cache_key_prefix = f"{med.get('name', '')}_"
                if hasattr(self, 'translation_cache'):
                    for k, cached_med in self.translation_cache.items():
                        if k.startswith(cache_key_prefix):
                            cached_med["image_url"] = img_url
                
                # If the user is still viewing this medicine, update the image widget directly
                if hasattr(self, 'current_med') and self.current_med and self.current_med.get("name") == med.get("name"):
                    self.current_med["image_url"] = img_url
                    img_card = self.root.ids.details_image_card
                    self.root.ids.details_image.source = img_url
                    img_card.height = dp(220)
                    img_card.opacity = 1
                    img_card.disabled = False
            Clock.schedule_once(update_image_ui, 0)

    def _show_details_dialog(self, med):
        # Sync image_url from self.current_med if it was resolved in parallel in the background thread
        if hasattr(self, 'current_med') and self.current_med and self.current_med.get("name") == med.get("name"):
            if "image_url" in self.current_med and self.current_med["image_url"]:
                med["image_url"] = self.current_med["image_url"]

        is_dark = (self.theme_cls.theme_style == "Dark")

        # 1. Update basic text labels
        self.root.ids.details_title.text = med.get("name", "Unknown Medicine")
        self.root.ids.details_subtitle.text = f"Active: {med.get('generic_name', med.get('active_ingredients', 'Not Specified'))}"
        
        country = med.get("country", "")
        category = med.get("category", "General")
        self.root.ids.details_meta.text = f"{country.upper()}   |   {category.upper()}" if country else category.upper()
        
        # 2. Toggle image card visibility
        img_card = self.root.ids.details_image_card
        if med.get("image_url"):
            self.root.ids.details_image.source = med["image_url"]
            img_card.height = 220
            img_card.opacity = 1
            img_card.disabled = False
        else:
            self.root.ids.details_image.source = ""
            img_card.height = 0
            img_card.opacity = 0
            img_card.disabled = True
            
        # 3. Dynamic Section Rendering (removes empty categories and blank spaces)
        container = self.root.ids.details_info_container
        container.clear_widgets()
        
        def add_clean_section(title, icon, content):
            if not content:
                return
            
            # Format list types
            if isinstance(content, list):
                content = "\n".join([f"• {item}" for item in content if item.strip()])
            content = str(content).strip()
            
            # Skip empty placeholders
            if content.lower() in ["", "none listed.", "not specified", "refer to product package for details."]:
                return
                
            # Create a horizontal card container
            card = NonBlockingCard(
                orientation='horizontal',
                size_hint_y=None,
                padding=[0, 0, 14, 0], # flush left edge
                spacing=12,
                radius=[12, 12, 12, 12],
                md_bg_color=(0.13, 0.13, 0.15, 1) if is_dark else (1, 1, 1, 1),
                line_color=(0.2, 0.2, 0.22, 1) if is_dark else (0.9, 0.91, 0.94, 1),
                elevation=1
            )
            card.bind(minimum_height=card.setter('height'))
            
            # Map sections to distinct theme colors
            if is_dark:
                color_map = {
                    "primary indications & uses": (0.85, 0.65, 0.13, 1.0), # Gold
                    "key benefits": (0.76, 0.12, 0.18, 1.0),               # Crimson
                    "dosage & directions": (0.85, 0.65, 0.13, 1.0),        # Gold
                    "precautions": (0.76, 0.12, 0.18, 1.0),               # Crimson
                    "online registry summary": (0.85, 0.65, 0.13, 1.0)     # Gold
                }
            else:
                color_map = {
                    "primary indications & uses": (1.0, 0.42, 0.36, 1.0), # Coral
                    "key benefits": (0.1, 0.45, 0.85, 1.0), # Blue
                    "dosage & directions": (1.0, 0.6, 0.2, 1), # Amber
                    "precautions": (0.15, 0.65, 0.3, 1), # Green
                    "online registry summary": (0.1, 0.45, 0.85, 1.0) # Blue
                }
            accent_color = color_map.get(title.lower(), (0.85, 0.65, 0.13, 1.0) if is_dark else (1.0, 0.42, 0.36, 1.0))
            
            accent_bar = MDBoxLayout(
                size_hint=(None, 1),
                width=dp(4),
                md_bg_color=accent_color,
                radius=[12, 0, 0, 12]
            )
            
            content_layout = MDBoxLayout(
                orientation='vertical',
                padding=[0, 12, 0, 12],
                spacing=6,
                size_hint_y=None
            )
            content_layout.bind(minimum_height=content_layout.setter('height'))
            
            # Create horizontal layout for header with vector icon (no boxes)
            header_layout = MDBoxLayout(
                orientation='horizontal',
                spacing=8,
                size_hint_y=None,
                height=24
            )
            
            from kivymd.uix.label import MDIcon
            icon_widget = MDIcon(
                icon=icon,
                theme_text_color="Custom",
                text_color=accent_color,
                font_size="20sp",
                size_hint=(None, None),
                size=(24, 24)
            )
            
            header_lbl = MDLabel(
                text=title.upper(),
                font_style="Subtitle2",
                theme_text_color="Custom",
                text_color=accent_color,
                bold=True,
                size_hint_y=None,
                height=24,
                valign="middle"
            )
            
            header_layout.add_widget(icon_widget)
            header_layout.add_widget(header_lbl)
            content_layout.add_widget(header_layout)
            
            lbl = MDLabel(
                text=content,
                font_style="Body2",
                theme_text_color="Custom",
                text_color=(0.95, 0.95, 0.98, 1) if is_dark else (0.1, 0.1, 0.12, 1),
                markup=True,
                size_hint_y=None
            )
            lbl.bind(width=lambda inst, val: setattr(inst, 'text_size', (val, None)))
            lbl.bind(texture_size=lambda inst, size: setattr(inst, 'height', size[1]))
            content_layout.add_widget(lbl)
            
            card.add_widget(accent_bar)
            card.add_widget(content_layout)
            
            container.add_widget(card)

        # Build clean segments using KivyMD vector icon names instead of raw Unicode emojis
        add_clean_section("Primary Indications & Uses", "medical-bag", med.get("uses"))
        add_clean_section("Key Benefits", "star-circle", med.get("benefits"))
        add_clean_section("Dosage & Directions", "text-box-check", med.get("dosage"))
        add_clean_section("Precautions", "alert-box", med.get("precautions"))
        
        # Format warnings separately with a warning red outline and light-red background (vector icon, no emoji boxes)
        warnings = med.get("warnings")
        if warnings:
            if isinstance(warnings, list):
                # Clean prefix text instead of emoji
                warnings = "\n".join([f"* {w}" for w in warnings if w.strip()])
            warnings = str(warnings).strip()
            if warnings.lower() not in ["", "none listed.", "not specified"]:
                warn_card = NonBlockingCard(
                    orientation='horizontal',
                    size_hint_y=None,
                    padding=[0, 0, 14, 0],
                    spacing=12,
                    radius=[12, 12, 12, 12],
                    md_bg_color=(0.22, 0.1, 0.1, 1.0) if is_dark else (1.0, 0.94, 0.94, 1.0),
                    line_color=(0.5, 0.2, 0.2, 1) if is_dark else (0.95, 0.8, 0.8, 1),
                    elevation=1
                )
                warn_card.bind(minimum_height=warn_card.setter('height'))
                
                accent_bar = MDBoxLayout(
                    size_hint=(None, 1),
                    width=dp(4),
                    md_bg_color=(0.9, 0.25, 0.25, 1), # warnings red
                    radius=[12, 0, 0, 12]
                )
                
                content_layout = MDBoxLayout(
                    orientation='vertical',
                    padding=[0, 12, 0, 12],
                    spacing=6,
                    size_hint_y=None
                )
                content_layout.bind(minimum_height=content_layout.setter('height'))
                
                # Header layout with vector octagon alert icon
                header_layout = MDBoxLayout(
                    orientation='horizontal',
                    spacing=8,
                    size_hint_y=None,
                    height=24
                )
                
                from kivymd.uix.label import MDIcon
                icon_widget = MDIcon(
                    icon="alert-octagon",
                    theme_text_color="Custom",
                    text_color=(0.9, 0.25, 0.25, 1),
                    font_size="20sp",
                    size_hint=(None, None),
                    size=(24, 24)
                )
                
                header_lbl = MDLabel(
                    text="WARNINGS & PRECAUTIONS",
                    font_style="Subtitle2",
                    theme_text_color="Custom",
                    text_color=(0.9, 0.25, 0.25, 1),
                    bold=True,
                    size_hint_y=None,
                    height=24,
                    valign="middle"
                )
                header_layout.add_widget(icon_widget)
                header_layout.add_widget(header_lbl)
                content_layout.add_widget(header_layout)
                
                lbl = MDLabel(
                    text=warnings,
                    font_style="Body2",
                    theme_text_color="Custom",
                    text_color=(0.98, 0.85, 0.85, 1) if is_dark else (0.1, 0.1, 0.12, 1),
                    markup=True,
                    size_hint_y=None
                )
                lbl.bind(width=lambda inst, val: setattr(inst, 'text_size', (val, None)))
                lbl.bind(texture_size=lambda inst, size: setattr(inst, 'height', size[1]))
                content_layout.add_widget(lbl)
                
                warn_card.add_widget(accent_bar)
                warn_card.add_widget(content_layout)
                
                container.add_widget(warn_card)
                
        # Wikipedia summary panel (using KivyMD vector icon name)
        add_clean_section("Online Registry Summary", "web", med.get("online_description"))

        # Price and shop action panel (clean vector styling, no raw emojis)
        price = med.get("price")
        shop_link = med.get("shop_link")
        if price or shop_link:
            price_card = NonBlockingCard(
                orientation='vertical',
                size_hint_y=None,
                padding=14,
                spacing=10,
                radius=[12, 12, 12, 12],
                md_bg_color=(0.1, 0.18, 0.25, 0.5) if is_dark else (0.93, 0.96, 1.0, 0.5), # blue tint
                line_color=(0.15, 0.3, 0.45, 1.0) if is_dark else (0.8, 0.9, 1.0, 1.0), # light blue border
                elevation=1
            )
            price_card.bind(minimum_height=price_card.setter('height'))
            
            if price:
                price_lbl = MDLabel(
                    text=f"[b]Suggested Price:[/b]  {price}",
                    font_style="Subtitle2",
                    theme_text_color="Custom",
                    text_color=(0.95, 0.95, 0.98, 1) if is_dark else (0.1, 0.1, 0.12, 1),
                    markup=True,
                    size_hint_y=None,
                    height=24
                )
                price_card.add_widget(price_lbl)
                
            if shop_link:
                btn = MDRaisedButton(
                    text="Find / Buy Online",
                    md_bg_color=(0.85, 0.65, 0.13, 1.0) if is_dark else (1.0, 0.42, 0.36, 1.0),
                    text_color=(1, 1, 1, 1),
                    size_hint_x=1,
                    on_release=lambda x: webbrowser.open(shop_link)
                )
                price_card.add_widget(btn)
                
            container.add_widget(price_card)

        # 3.5. Compare with Home Country Alternatives
        # Always build comparison tool to allow on-the-fly comparisons
        med_country = med.get("country", "")
        home_c = getattr(self, "home_country", "USA")
        
        # Create a comparison card container
        comp_card = NonBlockingCard(
            orientation='vertical',
            size_hint_y=None,
            padding=14,
            spacing=12,
            radius=[12, 12, 12, 12],
            md_bg_color=(0.13, 0.13, 0.15, 1) if is_dark else (1, 1, 1, 1),
            line_color=(0.2, 0.2, 0.22, 1) if is_dark else (0.9, 0.91, 0.94, 1),
            elevation=1
        )
        comp_card.bind(minimum_height=comp_card.setter('height'))
        
        # Header layout with vector compare scale icon & selection dropdown button
        header = MDBoxLayout(
            orientation='horizontal',
            spacing=8,
            size_hint_y=None,
            height=32
        )
        
        from kivymd.uix.label import MDIcon
        comp_icon = MDIcon(
            icon="scale-balance",
            theme_text_color="Custom",
            text_color=(0.76, 0.12, 0.18, 1.0) if is_dark else (0.1, 0.45, 0.85, 1.0),
            font_size="20sp",
            size_hint=(None, None),
            size=(24, 24),
            pos_hint={"center_y": 0.5}
        )
        
        comp_title = MDLabel(
            text="COMPARE EQUIVALENTS",
            font_style="Subtitle2",
            theme_text_color="Custom",
            text_color=(0.76, 0.12, 0.18, 1.0) if is_dark else (0.1, 0.45, 0.85, 1.0),
            bold=True,
            size_hint_y=None,
            height=32,
            valign="middle"
        )
        
        header.add_widget(comp_icon)
        header.add_widget(comp_title)
        comp_card.add_widget(header)
        
        # Selector layout: "Compare with:" + [Dropdown Button]
        selector_layout = MDBoxLayout(
            orientation='horizontal',
            spacing=10,
            size_hint_y=None,
            height=36,
            pos_hint={"center_x": 0.5}
        )
        
        selector_lbl = MDLabel(
            text="Compare with country:",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=(0.65, 0.65, 0.7, 1) if is_dark else (0.4, 0.4, 0.45, 1),
            size_hint_x=0.55,
            valign="middle"
        )
        
        dropdown_btn = MDRaisedButton(
            text=f"{home_c} ▾",
            text_color=(1, 1, 1, 1),
            md_bg_color=(0.85, 0.65, 0.13, 1.0) if is_dark else (1.0, 0.42, 0.36, 1.0),
            size_hint_x=0.45,
            pos_hint={"center_y": 0.5}
        )
        dropdown_btn.bind(on_release=lambda x: self.open_detail_comparison_menu(dropdown_btn, med))
        
        selector_layout.add_widget(selector_lbl)
        selector_layout.add_widget(dropdown_btn)
        comp_card.add_widget(selector_layout)
        
        # Map/normalize category to standard ones
        category = med.get("category", "Pain Reliever")
        standard_categories = ["Pain Reliever", "Cold & Flu", "Digestive Health", "Allergy"]
        matched_cat = None
        for cat in standard_categories:
            if cat.lower() in category.lower():
                matched_cat = cat
                break
        
        if not matched_cat:
            desc_text = (str(med.get("uses", "")) + " " + str(med.get("name", "")) + " " + str(med.get("generic_name", ""))).lower()
            if "pain" in desc_text or "fever" in desc_text or "headache" in desc_text or "analgesic" in desc_text or "ロキソニン" in desc_text:
                matched_cat = "Pain Reliever"
            elif "cold" in desc_text or "flu" in desc_text or "cough" in desc_text or "congest" in desc_text or "fever" in desc_text:
                matched_cat = "Cold & Flu"
            elif "stomach" in desc_text or "acid" in desc_text or "digest" in desc_text or "laxative" in desc_text or "diarrhea" in desc_text or "nausea" in desc_text:
                matched_cat = "Digestive Health"
            elif "allergy" in desc_text or "histamine" in desc_text or "allergic" in desc_text or "runny nose" in desc_text:
                matched_cat = "Allergy"
                
        if not matched_cat:
            matched_cat = "Pain Reliever"
            
        import med_database
        equivalents = med_database.get_medicines_by_filters(country=home_c, category=matched_cat)
        
        # Filter out current medicine
        equivalents = [eq for eq in equivalents if eq.get("name") != med.get("name")]
        
        if equivalents:
            intro_lbl = MDLabel(
                text=f"Equivalents in [b]{home_c}[/b] for [i]{matched_cat}[/i]:",
                font_style="Caption",
                theme_text_color="Custom",
                text_color=(0.65, 0.65, 0.7, 1) if is_dark else (0.4, 0.4, 0.45, 1),
                markup=True,
                size_hint_y=None,
                height=18
            )
            comp_card.add_widget(intro_lbl)
            
            for eq in equivalents:
                eq_item = NonBlockingCard(
                    orientation='horizontal',
                    size_hint_y=None,
                    height=dp(50),
                    padding=[10, 6, 10, 6],
                    spacing=10,
                    radius=[8, 8, 8, 8],
                    md_bg_color=(0.18, 0.18, 0.2, 1.0) if is_dark else (0.96, 0.97, 0.98, 1.0),
                    line_color=(0.25, 0.25, 0.28, 1) if is_dark else (0.9, 0.91, 0.94, 1),
                    ripple_behavior=True,
                    on_release=lambda x, m=eq: self.show_medication_details(m)
                )
                
                eq_info = MDBoxLayout(
                    orientation='vertical',
                    size_hint_x=0.75,
                    spacing=2
                )
                eq_name = MDLabel(
                    text=eq.get("name"),
                    font_style="Subtitle2",
                    bold=True,
                    theme_text_color="Custom",
                    text_color=(0.95, 0.95, 0.98, 1) if is_dark else (0.1, 0.1, 0.12, 1)
                )
                eq_generic = MDLabel(
                    text=eq.get("generic_name"),
                    font_style="Caption",
                    theme_text_color="Custom",
                    text_color=(0.65, 0.65, 0.7, 1) if is_dark else (0.4, 0.4, 0.45, 1)
                )
                eq_info.add_widget(eq_name)
                eq_info.add_widget(eq_generic)
                
                chevron_box = MDBoxLayout(
                    size_hint_x=0.25,
                    pos_hint={"center_y": 0.5}
                )
                from kivymd.uix.label import MDIcon
                chevron = MDIcon(
                    icon="chevron-right",
                    theme_text_color="Custom",
                    text_color=(0.85, 0.65, 0.13, 1.0) if is_dark else (1.0, 0.42, 0.36, 1.0),
                    font_size="24sp",
                    pos_hint={"center_y": 0.5}
                )
                chevron_box.add_widget(chevron)
                
                eq_item.add_widget(eq_info)
                eq_item.add_widget(chevron_box)
                comp_card.add_widget(eq_item)
        else:
            no_eq_lbl = MDLabel(
                text=f"No equivalent medicines found in [b]{home_c}[/b] for category [i]{matched_cat}[/i].",
                font_style="Caption",
                theme_text_color="Custom",
                text_color=(0.65, 0.65, 0.7, 1) if is_dark else (0.4, 0.4, 0.45, 1),
                markup=True,
                size_hint_y=None,
                height=36
            )
            no_eq_lbl.bind(width=lambda inst, val: setattr(inst, 'text_size', (val, None)))
            no_eq_lbl.bind(texture_size=lambda inst, size: setattr(inst, 'height', size[1]))
            comp_card.add_widget(no_eq_lbl)
            
        container.add_widget(comp_card)

        # 4. Transition screen manager
        if self.root.current != "details_screen":
            self.root.transition.direction = "left"
            self.root.current = "details_screen"


if __name__ == '__main__':
    PharmaGlobeApp().run()
