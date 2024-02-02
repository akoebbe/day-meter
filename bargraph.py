import board
import math
import asyncio

from ulab import numpy as np
from adafruit_ht16k33.bargraph import Bicolor24


i2c = board.STEMMA_I2C()
bc24 = Bicolor24(i2c, auto_write=False)

current_display = np.full(24, bc24.LED_OFF, dtype=np.uint8)
color_map = {'g': bc24.LED_GREEN, 'r': bc24.LED_RED, 'y': bc24.LED_YELLOW, '': bc24.LED_OFF}

wifi_animation = False

reverse = False  

def set_frame_from_text(frame):
    next_frame = np.full(24, bc24.LED_OFF, dtype=np.uint8)

    for i, c in enumerate(frame):
        next_frame[i] = color_map[c]
    
    set_frame(next_frame)

def set_led(index, color):
    bc24[index] = color
    current_display[index] = color

def progress(pct=.5, color="g", justified="left", commit:bool=False):
  percent_range = np.array([0,1])
  led_range = np.array([1,24])
  led_count = math.floor(24 * pct)
  next_frame = np.full(24, bc24.LED_OFF, dtype=np.uint8)
  
  next_frame[:led_count] = color_map[color]

  if justified == "right":
    next_frame = np.flip(next_frame)

  if commit:
     set_frame(next_frame)
     commit_frame()

  return next_frame

def set_frame(next_frame):
  if reverse:
     next_frame = np.flip(next_frame) 
  if current_display != next_frame:
    for i, color in enumerate(next_frame):
      set_led(i, color)

def commit_frame():
  print("".join(str(i) if i > 0 else '.' for i in current_display))
  bc24.show()

class WifiAnimation:
  def __init__(self):
    self.current_step = 0
  
  def reset(self):
     self.current_step = 0

  def tick(self):
    next_frame = np.full(24, bc24.LED_OFF, dtype=np.uint8)
    next_frame[self.current_step] = bc24.LED_GREEN
    next_frame[12:24] = next_frame[0:12]
    next_frame[0:12] = next_frame[23:11:-1]

    self.current_step = (self.current_step + 1) % 12

    set_frame(next_frame)
    commit_frame()

async def animation_runner():
    wifi = WifiAnimation()
    while True:
      if wifi_animation == True:
          WifiAnimation.tick()
      await asyncio.sleep(0.1)
