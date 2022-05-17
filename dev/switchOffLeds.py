# switchOffLeds.py: switches off the illuminations leds on the GY-31 board
# Copyright (c) U. Raich May 2022

from machine import Pin

illum = Pin(23,Pin.OUT)
illum.off()
