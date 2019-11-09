import time

import Adafruit_GPIO.SPI as SPI
import Adafruit_SSD1306

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

import subprocess

from gpiozero import Button
import sys
import os
from datetime import datetime
import random
import threading
import pyHS100

# Raspberry Pi pin configuration:
RST = None     # on the PiOLED this pin isnt used

# 128x64 display with hardware I2C:
disp = Adafruit_SSD1306.SSD1306_128_64(rst=RST)

# Initialize library.
disp.begin()

# Clear display.
disp.clear()
disp.display()

# Create blank image for drawing.
# Make sure to create image with mode '1' for 1-bit color.
width = disp.width
height = disp.height
image = Image.new('1', (width, height))

# Get drawing object to draw on image.
draw = ImageDraw.Draw(image)

# Draw a black filled box to clear the image.
draw.rectangle((0,0,width,height), outline=0, fill=0)

# Draw some shapes.
# First define some constants to allow easy resizing of shapes.
padding = -2
top = padding
bottom = height-padding
# Move left to right keeping track of the current x position for drawing shapes.
x = 0

# load a TTF font. Make sure the .ttf font file is in the same directory as the python script!
font = ImageFont.truetype('04b30font.ttf', 16)

button = Button(4) # GPIO 4 and Ground next to it

plugIP = "IPADDRESS" 
plug = pyHS100.SmartPlug(plugIP)

screenOffTime = time.time() + 60
screenOn = True

lightsOn = False
lightsOffTime = 0

fishFedMorning = False
fishFedNight = False
fishFeedingTimeMorning = 9
fishFeedingTimeNight = 22

scriptStartTime = time.time()
debug = False

def logger(msg):
    print(datetime.now().strftime("%y-%m-%d %H:%M:%S") + " " + str(msg))

def feedFish():
    global fishFedMorning
    global fishFedNight
    global lightsOffTime

    if getCurrentTimeRange() == "morning":
        fishFedMorning = True
        logger("<Fish Feeder> Fish are now fed")
    elif getCurrentTimeRange() == "night":
        fishFedNight = True
        lightsOffTime = time.time() + (60 * 15)
        logger("<Fish Feeder> Fish are now fed")
   

def sendHungryMessage(feedingTime=""):
    logger("<Fish Texter> Sending fish hungry text")
    if debug:
        return
    fish = random.randint(1,5)
    ID = ""
    if fish == 1:
        ID = "TelegramBotAPIKEY1"
    elif fish == 2:
        ID = "TelegramBotAPIKEY2"
    elif fish == 3:
        ID = "TelegramBotAPIKEY3"
    elif fish == 4:
        ID = "TelegramBotAPIKEY4"
    elif fish == 5:
        ID = "TelegramBotAPIKEY5"
    else:
        logger("<ERROR> Invalid fish ID")

    textChoices = ["Help! I\'m hungry!",
            "Feed meeeeeeee",
            "Ack! Where's all the food?",
            "Wot in tarnation? We weren\'t fed!",
            "Eeeeeek hungry!",
            "Shweta! I want food!"]

    textChoice = random.randint(0,len(textChoices)-1)

    command = "curl -i -X GET \"https://api.telegram.org/bot" + ID + "/sendMessage?chat_id=USERID&text=" + textChoices[textChoice] + "\""
    process = subprocess.run([command], check=True, stdout=subprocess.PIPE, universal_newlines=True, shell=True)
    output = process.stdout
    

def watchFedStatus():
    global fishFedMorning
    global fishFedNight
    global fishFeedingTimeNight
    global fishFeedingTimeMorning

    while True:
        if time.time() < scriptStartTime + (60 * 5):
            time.sleep(60 * 5)

        currentHour = int(datetime.now().strftime("%H"))

        if currentHour > 4 and currentHour < 6:
            fishFedMorning = False
            fishFedNight = False
        
        elif getCurrentTimeRange() == "morning" and fishFedMorning == False and currentHour >= fishFeedingTimeMorning + 1:
                sendHungryMessage("morning")

        elif getCurrentTimeRange() == "night" and fishFedNight == False and (currentHour >= fishFeedingTimeNight + 1 or currentHour < 2):
                sendHungryMessage("night")
            
        time.sleep(60 * 60)


def watchForButton():
    global screenOn
    global screenOffTime

    logger("<Button> Watching for button press...")
    while True:
        button.wait_for_press()
        logger("<Button> Button Pressed")
        if screenOn:
            feedFish()
            time.sleep(5)
        else:
            screenOn = True
            logger("<Button> Turning on screen")
        screenOffTime = time.time() + 60
        logger("<Button> Refreshing screen off timer")
        time.sleep(1)


def sleepTimer():
    global screenOn

    while True:
        if screenOn and time.time() > screenOffTime:
            screenOn = False
            logger("<Sleep Timer> Turning off screen")
        time.sleep(1)


def getCurrentTimeRange():
    global fishFeedingTimeMorning
    global fishFeedingTimeNight

    currentTime = int(datetime.now().strftime("%H"))
    
    if currentTime > fishFeedingTimeMorning - 3 and currentTime < fishFeedingTimeMorning + 6:
        return "morning"
    elif currentTime > fishFeedingTimeNight - 3 or currentTime < 4:
        return "night"
    else:
        return "none"


def getFedStatusForCurrentTimeRange():
    global fishFedMorning
    global fishFedNight
    
    if getCurrentTimeRange() == "morning":
        return fishFedMorning
    elif getCurrentTimeRange() == "night":
        return fishFedNight
    else:
        return "Null"


def toggleLights(mode):
    global plug
    global lightsOn
    logger("<Light Toggle> Turning lights " + mode)
    while True:
        try:
            if mode == "on":
                plug.turn_on()
                lightsOn = True
            elif mode == "off":
                plug.turn_off()
                lightsOn = False
            else:
                logger("<ERROR> Unknown plug mode")
            logger("<Light Toggle> Turned lights " + mode)
            return
        except:
            logger("<Light Toggle> Error occurred, retrying in 60 seconds")
            time.sleep(60)


def lightingController():
    global lightsOn
    global lightsOffTime
    global fishFedNight

    while True: 
        currentTimeH = int(datetime.now().strftime("%H"))
    
        if lightsOn and currentTimeH < 8:
            if lightsOffTime != 0 and time.time() > lightsOffTime:
                # turn off lights
                logger("<Lighting Controller> Turning off lights")
                toggleLights("off")

        elif (not lightsOn and currentTimeH >= 8) or (not lightsOn and currentTimeH < 2 and fishFedNight == False):
            # turn on lights
            logger("<Lighting Controller> Turning on lights")
            lightsOffTime = 0
            toggleLights("on")

        time.sleep(60)


def screenController():
    while True:

        # Draw a black filled box to clear the image
        draw.rectangle((0,0,width,height), outline=0, fill=0)

        if time.time() < screenOffTime:

            # Write lines of text
            draw.text((x, top+4), "Fish are",  font=font, fill=255)
            if getFedStatusForCurrentTimeRange():
                draw.text((x, top+20), "fed!",  font=font, fill=255)
            else:
                draw.text((x, top+20), "not fed!",  font=font, fill=255)

        # Display image
        disp.image(image)
        disp.display()
        time.sleep(1)


threading.Thread(target=watchFedStatus).start()
threading.Thread(target=watchForButton).start()
threading.Thread(target=sleepTimer).start()
threading.Thread(target=lightingController).start()
threading.Thread(target=screenController).start()


if __name__ == "__main__":

    while True:
        commandIn = input("")
        if commandIn == "lights on":
            toggleLights("on")

        elif commandIn == "lights off":
            toggleLights("off")

        elif commandIn == "screen on":
            screenOn = True
            logger("<Screen> Turning on screen")
            screenOffTime = time.time() + 60

        elif commandIn == "screen off":
            screenOn = False
            logger("<Screen> Turning off screen")
            screenOffTime = 0
        
        elif commandIn == "feed fish":
            feedFish()

        elif commandIn == "getTimeRange":
            print(getCurrentTimeRange())

        elif commandIn == "getFedStatus":
            print(getFedStatusForCurrentTimeRange())

        elif commandIn == "getLightStatus":
            print(lightsOn)

        elif commandIn == "getLightOffTime":
            print(lightsOffTime)

        elif commandIn == "getCurrentTime":
            print(time.time())

        else:
            print("Invalid Command")













    
