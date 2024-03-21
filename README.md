# MQTT Fingerprint PI
Exposes fingerprint sensor R503 to an MQTT broker to control it through Home Assistant. The main purpose is to be used with a smart lock. If you want to create your own, check out the one I created [here](https://community.home-assistant.io/t/smart-lock-with-gears).


# Installation
This works with the GPIO of Raspberry PI or even a USB serial connected to PC. For Raspberry GPIO, you need to **Disable linux serial console** following the official guide [here](https://www.raspberrypi.org/documentation/configuration/uart.md), or with this command `sudo raspi-config nonint do_serial 2`.

```bash
git clone https://github.com/bkbilly/mqtt_fingerprint_pi /opt/mqtt_fingerprint_pi
cd /opt/mqtt_fingerprint_pi/
vi config.yaml

sudo pip install -r requirements.txt
sudo cp mqtt_fingerprint_pi.service /etc/systemd/system/mqtt_fingerprint_pi.service
sudo systemctl enable mqtt_fingerprint_pi.service
sudo systemctl start mqtt_fingerprint_pi.service
```

## Connection diagram
|     R503 Sensor      |     Raspberry PI     |
| -------------------- | ------------------------- |
| RED (Power 3V)       | [3.3V](https://pinout.xyz/pinout/3v3_power)  |
| BLACK (GND)          | [Ground](https://pinout.xyz/pinout/ground)  |
| YELLOW (TXD)         | [UART RX](https://pinout.xyz/pinout/pin10_gpio15)  |
| GREEN (RXD)          | [UART TX](https://pinout.xyz/pinout/pin8_gpio14)  |
| BLUE (Wakeup)        | Not connected  |
| WHITE (3.3VT)        | Not connected  |


# Configuration
Edit the config.yaml file with the following info:
```yaml
serial: "/dev/serial0"  # Default serial for Raspberry
timeout: 0              # Expiration time for each fingerprint (0=deactivate)
mqtt:
  host: "192.168.x.x"   # MQTT Broker IP
  user: "myuser"        # MQTT Username
  pass: "mypass"        # MQTT Password
```
## Temporary fingerprints
To enable the temporary fingerprints, you will have to change the timeout to any integer value other than zero.
Each fingerprint is stored on the `devices.yaml` file with the time they were enrolled.
If you change their **name**, they are considered **permanent** users, but if you don't change them, they will be considered **temporary**.
The user works normally until the timeout is reached which will show send a timeout on mqtt instance.

# Home Assistant Integration
This automation will check the action of the finger and it will call the appropriate service of the lock.
```yaml
alias: Fingerprint scanned successfully
trigger:
  - platform: mqtt
    topic: fingerprint/finger
action:
  - choose:
      - conditions:
          - condition: template
            value_template: '{{ trigger.payload_json.action == "unlock" }}'
        sequence:
          - service: lock.unlock
            target:
              entity_id: lock.frontdoor
      - conditions:
          - condition: template
            value_template: '{{ trigger.payload_json.action == "lock" }}'
        sequence:
          - service: lock.lock
            target:
              entity_id: lock.frontdoor
```

You can have a sensor to keep track of the fingeprint usage.
```yaml
sensor:
  - platform: mqtt
    name: "Fingerprint"
    state_topic: "fingerprint/finger"
    value_template: "{{ value_json.name }}"
    json_attributes_topic: "fingerprint/finger"
    json_attributes_template: "{{ value_json | tojson }}"
```


# MQTT Commands

## fingerprint/finger
This is published when a finger is scanned by the sensor. It contains the following:
```python
{
  "id": 0,             # The id in the fingerprint sensor. (-1 means unauthorized user)
  "action": "unlock",  # Default action is unlock, but supports "timeout, unauthorized, unlock, lock"
  "name": "bkbilly",   # The user defined in devices.yaml
  "confidence": 76     # How close the finger is to the original scan
}
```

## fingerprint/templates
This is published everytime a change is occured on the database like deleting or enrolling fingerprints.
It contains a list of each fingerprint.
```python
[
  {
    "id": 0,            # The id in the fingerprint sensor
    "name": "bkbilly",  # The custom name of the finger, defaults to ID value
    "action": "unlock", # The action to perform, defaults to "unlock"
    "time": 1615721723  # The timestamp the finger was enrolled
  }
]
```

## fingerprint/mode
The default mode is scan which is constantly looking for new fingerprint inputs. It can support the following: 
  - enroll (scans finger twice and saves it into the fingerprint sensor)
  - scan (look for new fingerprint inputs)
  - delete (deletes a fingerprint based on it's ID)
  - empty (deletes all fingerprints)

## "fingerprint/set/mode"
Changes the mode "enroll, delete, empty, name_xx". Most of them don't need any value, except delete which requires the id of the fingerprint.

### Enroll
```yaml
service: mqtt.publish
data:
  topic: fingerprint/set/mode/enroll
  payload: "-1"
```

### Rename
```yaml
service: mqtt.publish
metadata: {}
data:
  topic: fingerprint/set/mode/name_{{ finger_id }}
  payload: "{{ name }}"
```

### Delete
```yaml
service: mqtt.publish
data:
  topic: fingerprint/set/mode/delete
  payload: "{{ finger_id }}"
```

### Delete All
```yaml
service: mqtt.publish
data:
  topic: fingerprint/set/mode/empty
```

