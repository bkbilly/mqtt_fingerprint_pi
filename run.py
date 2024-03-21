import os
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
        self.updated_templates = lambda: None
        self.unauthorized = lambda: None
        self.mode = "scan"
        self.get_info()
        threading.Thread(target=self.get_fingerprint, daemon=True).start()

    def set_mode(self, mode, args=-1):
        if args == "" or args is None:
            args = -1
        args = int(args)
        if self.mode != mode:
            print("changed mode to", mode)
            self.mode = mode
            if mode == "enroll":
                self.enroll_new(args)
                self.mode = "scan"
            elif mode == "delete":
                self.delete_model(args)
                self.mode = "scan"
            elif mode == "empty":
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
            self.updated_templates()
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
            self.updated_templates()
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
                    time.sleep(0.2)
                    if self.finger.image_2_tz(1) == adafruit_fingerprint.OK:
                        print("Searching...")
                        if self.finger.finger_search() == adafruit_fingerprint.OK:
                            print("Detected #", self.finger.finger_id, "with confidence", self.finger.confidence)
                            self.set_ledcolor(self.LEDCOLOR_BLUE, self.LEDMODE_STILL)
                            self.found_finger(self.finger.finger_id, self.finger.confidence)
                            time.sleep(1)
                            self.set_ledcolor(action="reset")
                        else:
                            self.unauthorized()
                            self.set_ledcolor(action="error")
                    else:
                        self.unauthorized()
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
        self.updated_templates()
        return True

    def enroll_new(self, position):
        if position < 0:
            empty_positions = list(set(range(0, self.finger.library_size - 1)) - set(self.finger.templates))
            position = empty_positions[0]
        print('ID of the new enlyst:', position)
        fingerprint.enroll_finger(position)
        return position


def read_devices():
    devices = []
    if os.path.exists('devices.yaml'):
        with open('devices.yaml') as f:
            devices = yaml.load(f, Loader=yaml.FullLoader)
    if devices is None:
        devices = []
    devices_dict = {i['id']: i for i in devices}
    return devices_dict


def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    client.publish("fingerprint/mode", "scan")
    client.subscribe("fingerprint/set/#")
    updatedtemplates()


def on_message(client, userdata, msg):
    mode = msg.topic.split("/")[-1]
    payload_arg = str(msg.payload.decode("utf-8"))
    print(msg.topic + " " + payload_arg)
    if "name_" in mode:
        f_id = int(mode.split("_")[-1])
        renamefinger(f_id, payload_arg)
    else:
        client.publish("fingerprint/mode", mode)
        fingerprint.set_mode(mode, payload_arg)
        client.publish("fingerprint/mode", "scan")

def renamefinger(f_id, name):
    print(f_id, name)
    devices_dict = read_devices()
    devices_dict[f_id]['name'] = name
    devices_list = []
    for d_id, device in devices_dict.items():
        devices_list.append(device)
    with open('devices.yaml', 'w') as f:
        yaml.dump(devices_list, f)

def foundfinger(f_id, confidence):
    print(f_id, confidence)
    devices_dict = read_devices()
    devices_dict[f_id]['count'] += 1
    device_publish = devices_dict[f_id]
    device_publish['confidence'] = confidence
    if config['timeout'] > 0:
        if device_publish['id'] == device_publish['name']:
            if (time.time() - device_publish['time']) > config['timeout']:
                fingerprint.set_ledcolor(action="error")
                device_publish['action'] = "timeout"
    client.publish("fingerprint/finger", json.dumps(device_publish))
    devices_list = []
    for d_id, device in devices_dict.items():
        devices_list.append(device)
    with open('devices.yaml', 'w') as f:
        yaml.dump(devices_list, f)

def unauthorized():
    to_publish = {
        'id': -1,
        'name': "unauthorized",
        'action': "unauthorized",
        'time': int(time.time()),
        'confidence': 0,
    }
    client.publish("fingerprint/finger", json.dumps(to_publish))

def updatedtemplates():
    devices_list = []
    devices_dict = read_devices()
    for template in fingerprint.finger.templates:
        if template in devices_dict:
            devices_list.append({
                'id': template,
                'name': devices_dict[template]['name'],
                'action': devices_dict[template]['action'],
                'time': devices_dict[template]['time'],
                'count': devices_dict[template]['count'],
            })
        else:
            devices_list.append({
                'id': template,
                'name': template,
                'action': "unlock",
                'time': int(time.time()),
                'count': 0,
            })
    with open('devices.yaml', 'w') as f:
        yaml.dump(devices_list, f)
    templates = json.dumps(fingerprint.finger.templates)
    client.publish("fingerprint/templates", json.dumps(devices_list))


with open('config.yaml') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

fingerprint = Fingerprint(config['serial'])
client = mqtt.Client()
fingerprint.found_finger = foundfinger
fingerprint.updated_templates = updatedtemplates
fingerprint.unauthorized = unauthorized
client.on_connect = on_connect
client.on_message = on_message

client.username_pw_set(config['mqtt']['user'], config['mqtt']['pass'])
client.connect(config['mqtt']['host'], 1883, 60)
client.loop_forever()

