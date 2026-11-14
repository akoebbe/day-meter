"""Bicolor 24-bar adapter -- the first concrete Display (roadmap F1)."""
import asyncio
import board

from adafruit_ht16k33.bargraph import Bicolor24

from . import frame_math
from .base import Display


class Bicolor24Adapter(Display):
    LED_COUNT = 24

    def __init__(self, reverse=False):
        self._i2c = board.STEMMA_I2C()
        self._driver = Bicolor24(self._i2c, auto_write=False)
        self.PALETTE = {
            'g': self._driver.LED_GREEN,
            'r': self._driver.LED_RED,
            'y': self._driver.LED_YELLOW,
            '': self._driver.LED_OFF,
        }
        self._reverse = reverse
        self.wifi_animation = False
        self._current = [self.PALETTE[""]] * self.LED_COUNT

    def set_frame(self, frame):
        frame = list(frame)
        if len(frame) != self.LED_COUNT:
            raise ValueError("frame must be exactly {0} LEDs, got {1}".format(
                self.LED_COUNT, len(frame)))
        if self._reverse:
            frame = frame[::-1]
        for i in frame_math.diff(self._current, frame):
            self._driver[i] = frame[i]
            self._current[i] = frame[i]

    def commit(self):
        print("".join(str(i) if i > 0 else '.' for i in self._current))
        self._driver.show()


wifi_animation = False


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
