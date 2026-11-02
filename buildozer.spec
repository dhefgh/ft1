[app]
title = Fare Tracker
package.name = faretracker
package.domain = org.fares
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1
requirements = python3,kivy==2.3.0,requests,urllib3,idna,charset-normalizer,certifi,plyer,android
orientation = portrait
fullscreen = 0
services = Fares:service.py:foreground:sticky

android.api = 33
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
android.permissions = INTERNET,FOREGROUND_SERVICE,POST_NOTIFICATIONS,WAKE_LOCK

[buildozer]
log_level = 2
warn_on_root = 1
