[app]

# (str) Title of your application
title = PharmaGlobe Mobile

# (str) Package name
package.name = pharmaglobe

# (str) Package domain (needed for android packaging)
package.domain = org.pz48hce

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,json

# (str) Application versioning
version = 1.0.0

# (list) Application requirements
# comma separated e.g. requirements = sqlite3,kivy
requirements = python3==3.11.15,hostpython3==3.11.15,kivy==2.2.0,kivymd==1.1.1,pillow,requests,numpy,opencv,legacy-cgi

# (str) Custom source folders for requirements
# (list) Permissions
android.permissions = INTERNET, CAMERA, WRITE_EXTERNAL_STORAGE

# (int) Target Android API, should be as high as possible.
android.api = 33

# (bool) If True, then automatically accept SDK license agreements.
android.accept_sdk_license = True

# (int) Minimum API your APK will support.
android.minapi = 24

# (str) Android NDK version to use
# android.ndk = 25b

# (bool) Use private data directory (True) or global storage (False)
android.private_storage = True

# (list) Screen orientations
# Possible values: portrait, landscape, all
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Permissions for iOS (kivy-ios)
ios.kivy_ios_url = https://github.com/kivy/kivy-ios
ios.kivy_ios_branch = master

# (str) python-for-android directory to use, or clone url if not set
p4a.dir = ./python-for-android

[buildozer]
# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = false, 1 = true)
warn_on_root = 0
