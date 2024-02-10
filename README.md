# Day Meter 🚥

Day Meter is a project created to provide a non-distracting, but unavoidable, view of your day using a simple addressable LED bar graph and ESP32 microcontroller running CircuitPython.

- Non-distracting
- Unavoidable
- Self-contained no need for a server or connection to a computer for normal operation
- Easy to understand at a glance
- Gives a day view of your calendar
- Counts down 10min to next meeting
- Tracks remaining time in the current meeting

This repository contains the CircuitPython code that runs on the microcontroller.

## Hardware Requirements

1. ESP32 or ESP32-S3 board with 2mb PSRAM and (recommended) native USB support.
   1. [Adafruit QT Py ESP32-S3 with 2mb PSRAM](https://www.adafruit.com/product/5700) will work  best and is strongly recommended
   2. [Adafruit QT Py ESP32 Pico](https://www.adafruit.com/product/5395) will also work, but doesn't have native USB support. This will make development and configuration cumbersome, since it has to be done over serial.
2. [Adafruit Bi-Color (Red/Green) 24-Bar Bargraph w/I2C Backpack Kit](https://www.adafruit.com/product/1721).
   1. This is currently the only display supported.
   2. Soldering required
   3. I'm hoping to see other displays supported if a community develops around this.
3. [STEMMA QT/Qwiic cable](https://www.adafruit.com/product/4397) to connect the microcontroller to the display.

All in all, the parts are around $26 (USD), at the time of this commit.

## Development

To develop on Day Meter, you will need python and pip installed.

1. Clone this repository 
2. Install [circup](https://github.com/adafruit/circup) for CircuitPython library dependency management
   ```
   pip install circup
   ```
3. Install dependent libraries to the /lib direcotry
   ```
   circup --path . install
   ```
4. Copy all files and directories from the root of the repo to the root of the CIRCUITPY drive
