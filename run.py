import time
import serial

import adafruit_fingerprint
import paho.mqtt.client as mqtt
import threading
import json

import yaml


class Fingerprint():
    """docstring for Fingerprint"""
    LEDCOLOR_RED = 1
    LEDCOLOR_BLUE = 2
    LEDCOLOR_PURPLE = 3

    LEDMODE_BREATH = 1
    LEDMODE_BLINK = 2
    LEDMODE_STILL = 3
    LEDMODE_OFF = 4

    def __init__(self, myserial="/dev/serial0"):
        uart = serial.Serial(myserial, baudrate=57600, timeout=1)
        self.finger = adafruit_fingerprint.Adafruit_Fingerprint(uart)
        self.found_finger = lambda x, y: None
        self.updated_templates = lambda x: None
        self.mode = "scan"
        self.get_info()
        threading.Thread(target=self.get_fingerprint, daemon=True).start()

    def set_mode(self, mode, args=None):
        if self.mode != mode:
            print("changed mode to", mode)
            self.mode = mode
            if mode == "enroll":
                self.enroll_new()
                self.mode = "scan"
            if mode == "delete":
                self.delete_model(args)
                self.mode = "scan"
            if mode == "empty":
                self.empty_library()

    def get_info(self):
        if self.finger.read_templates() != adafruit_fingerprint.OK:
            raise RuntimeError("Failed to read templates")
        # print("Fingerprint templates: ", self.finger.templates)
        if self.finger.count_templates() != adafruit_fingerprint.OK:
            raise RuntimeError("Failed to read templates")
        # print("Number of templates found: ", self.finger.template_count)
        if self.finger.read_sysparam() != adafruit_fingerprint.OK:
            raise RuntimeError("Failed to get system parameters")
        # print("Size of template library: ", self.finger.library_size)
        return {
            "templates": self.finger.templates,
            "size": self.finger.library_size
        }

    def set_ledcolor(self, led_color=None, led_mode=None, action=None):
        if action == "reset":
            self.finger.set_led(color=self.LEDCOLOR_RED, mode=self.LEDMODE_OFF)
        elif action == "error":
            self.finger.set_led(color=self.LEDCOLOR_RED, mode=self.LEDMODE_STILL)
            time.sleep(1)
            self.set_ledcolor(action="reset")
        elif action == "enroll":
            self.finger.set_led(color=self.LEDCOLOR_PURPLE, mode=self.LEDMODE_BREATH)
        elif action == "success":
            self.finger.set_led(color=self.LEDCOLOR_BLUE, mode=self.LEDMODE_STILL)
            time.sleep(1)
            self.set_ledcolor(action="reset")

        led_mode = self.LEDMODE_STILL
        if led_color is not None and led_mode is not None:
            self.finger.set_led(color=led_color, mode=led_mode)

    def delete_model(self, location):
        time.sleep(1)
        if self.finger.delete_model(location) == adafruit_fingerprint.OK:
            print("Deleted!")
            self.finger.read_templates()
            self.finger.read_sysparam()
            self.updated_templates(fingerprint.finger.templates)
            return True
        else:
            print("Failed to delete")
            self.set_ledcolor(action="error")
            return False

    def empty_library(self):
        time.sleep(1)
        if self.finger.empty_library() == adafruit_fingerprint.OK:
            print("Library emptied!")
            self.finger.read_templates()
            self.finger.read_sysparam()
            self.updated_templates(fingerprint.finger.templates)
            return True
        else:
            print("Failed to empty library")
            self.set_ledcolor(action="error")
            return False

    def get_fingerprint(self):
        """Get a finger print image, template it, and see if it matches!"""
        while True:
            if self.mode == "scan":
                if self.finger.get_image() == adafruit_fingerprint.OK:
                    self.set_ledcolor(self.LEDCOLOR_PURPLE, self.LEDMODE_BLINK)
                    print("Templating...")
                    if self.finger.image_2_tz(1) == adafruit_fingerprint.OK:
                        print("Searching...")
                        if self.finger.finger_search() == adafruit_fingerprint.OK:
                            print("Detected #", self.finger.finger_id, "with confidence", self.finger.confidence)
                            self.set_ledcolor(self.LEDCOLOR_BLUE, self.LEDMODE_STILL)
                            self.found_finger(self.finger.finger_id, self.finger.confidence)
                            time.sleep(1)
                            self.set_ledcolor(action="reset")
                        else:
                            self.set_ledcolor(action="error")
                    else:
                        self.set_ledcolor(action="error")

    def enroll_finger(self, location, timeout=10):
        """Take a 2 finger images and template it, then store in 'location'"""
        time.sleep(1)
        for fingerimg in range(1, 3):
            self.set_ledcolor(action="enroll")
            if fingerimg == 1:
                print("Place finger on sensor...", end="", flush=True)
            else:
                print("Place same finger again...", end="", flush=True)

            start = time.time()
            while True:
                i = self.finger.get_image()
                if i == adafruit_fingerprint.OK:
                    print("Image taken")
                    break
                if i == adafruit_fingerprint.NOFINGER:
                    print(".", end="", flush=True)
                    if (time.time() - start) > timeout:
                        self.set_ledcolor(action="error")
                        return False
                elif i == adafruit_fingerprint.IMAGEFAIL:
                    print("Imaging error")
                    self.set_ledcolor(action="error")
                    return False
                else:
                    print("Other error")
                    self.set_ledcolor(action="error")
                    return False

            print("Templating...", end="", flush=True)
            i = self.finger.image_2_tz(fingerimg)
            if i == adafruit_fingerprint.OK:
                self.set_ledcolor(action="success")
                print("Templated")
            else:
                if i == adafruit_fingerprint.IMAGEMESS:
                    print("Image too messy")
                elif i == adafruit_fingerprint.FEATUREFAIL:
                    print("Could not identify features")
                elif i == adafruit_fingerprint.INVALIDIMAGE:
                    print("Image invalid")
                else:
                    print("Other error")
                self.set_ledcolor(action="error")
                return False

            if fingerimg == 1:
                print("Remove finger")
                time.sleep(1)
                while i != adafruit_fingerprint.NOFINGER:
                    i = self.finger.get_image()

        print("Creating model...", end="", flush=True)
        i = self.finger.create_model()
        if i == adafruit_fingerprint.OK:
            print("Created")
        else:
            if i == adafruit_fingerprint.ENROLLMISMATCH:
                print("Prints did not match")
            else:
                print("Other error")
            self.set_ledcolor(action="error")
            return False

        print("Storing model #%d..." % location, end="", flush=True)
        i = self.finger.store_model(location)
        if i == adafruit_fingerprint.OK:
            print("Stored")
        else:
            if i == adafruit_fingerprint.BADLOCATION:
                print("Bad storage location")
            elif i == adafruit_fingerprint.FLASHERR:
                print("Flash storage error")
            else:
                print("Other error")
            self.set_ledcolor(action="error")
            return False

        self.finger.read_templates()
        self.finger.read_sysparam()
        self.updated_templates(fingerprint.finger.templates)
        return True

    def enroll_new(self):
        empty_positions = list(set(range(0, self.finger.library_size - 1)) - set(self.finger.templates))
        print('ID of the new enlyst:', empty_positions[0])
        fingerprint.enroll_finger(empty_positions[0])
        return empty_positions[0]


def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    client.subscribe("fingerprint/set/#")
    client.subscribe("fingerprint/get/#")
    updatedtemplates()


def on_message(client, userdata, msg):
    print(msg.topic + " " + str(msg.payload.decode("utf-8")))
    if msg.topic == "fingerprint/set/mode":
        fingerprint.set_mode(str(msg.payload.decode("utf-8")))
    elif msg.topic == "fingerprint/set/delete":
        fingerprint.set_mode("delete", int(msg.payload.decode("utf-8")))
    elif msg.topic == "fingerprint/set/empty":
        fingerprint.set_mode("empty")
    elif msg.topic == "fingerprint/get/templates":
        templates = json.dumps(fingerprint.finger.templates)
        client.publish("fingerprint/templates", templates)


def foundfinger(f_id, confidence):
    print(f_id, confidence)
    client.publish("fingerprint/finger", f_id)


def updatedtemplates(temp=None):
    templates = json.dumps(fingerprint.finger.templates)
    client.publish("fingerprint/templates", templates)


with open('/opt/mqtt_fingerprint_pi/config.yaml') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

fingerprint = Fingerprint(config['serial'])
client = mqtt.Client()
fingerprint.found_finger = foundfinger
fingerprint.updated_templates = updatedtemplates
client.on_connect = on_connect
client.on_message = on_message

client.username_pw_set(config['mqtt']['user'], config['mqtt']['pass'])
client.connect(config['mqtt']['host'], 1883, 60)
client.loop_forever()

