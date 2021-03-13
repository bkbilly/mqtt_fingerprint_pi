# MQTT Fingerprint PI
Exposes fingerprint sensor R503 to an MQTT broker to control it through Home Assistant. 

This works with the GPIO of Raspberry PI or even a USB serial connected to PC. For Raspberry GPIO, you need to **Disable linux serial console** following the official guide [https://www.raspberrypi.org/documentation/configuration/uart.md](here).

# Installation
```bash
git clone git@github.com:bkbilly/mqtt_fingerprint_pi.git /opt/mqtt_fingerprint_pi
cd /opt/mqtt_fingerprint_pi/
vi config.yaml

sudo pip install -r requirements.txt
sudo cp mqtt_fingerprint_pi.service /etc/systemd/system/mqtt_fingerprint_pi.service
sudo systemctl enable mqtt_fingerprint_pi.service
sudo systemctl start mqtt_fingerprint_pi.service
```
