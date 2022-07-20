import rp2
import network
import machine
import ubinascii
import time
from secrets import secrets
from umqtt.simple import MQTTClient
from machine import Pin

#define and store relay and switch pin assignments
#switch pins can be altered but refer to relay documentation for availablility
#DO NOT CHANGE THE RELAY PINS

relays = {}
relays[1] = {  "relay": Pin(21, Pin.OUT), 
              "switch": Pin(12, Pin.IN) }
relays[2] = {  "relay": Pin(20, Pin.OUT),  
              "switch": Pin(11, Pin.IN) }
relays[3] = {  "relay": Pin(19, Pin.OUT), 
              "switch": Pin(10, Pin.IN)  }
relays[4] = {  "relay": Pin(18, Pin.OUT), 
              "switch": Pin(9,  Pin.IN)  }
relays[5] = {  "relay": Pin(17, Pin.OUT), 
              "switch": Pin(8,  Pin.IN)  }
relays[6] = {  "relay": Pin(16, Pin.OUT), 
              "switch": Pin(7,  Pin.IN)  }
relays[7] = {  "relay": Pin(15, Pin.OUT), 
              "switch": Pin(5,  Pin.IN)  }
relays[8] = {  "relay": Pin(14, Pin.OUT), 
              "switch": Pin(4,  Pin.IN)  }

#set onboard led and buzzer pins
led = Pin(13, Pin.OUT, value=0)
buz = Pin(6, Pin.OUT)

#change to your country code as applicable
rp2.country('GB')

#MQTT server details
MQTT_BROKER = secrets["MQTT_BROKER"]
MQTT_USER   = secrets["MQTT_USER"]
MQTT_PWD    = secrets["MQTT_PWD"]
MQTT_PORT   = secrets["MQTT_PORT"]

#MQTT topic details
MQTT_DEVICE_NAME   = secrets["MQTT_DEVICE_NAME"]
MQTT_DEVICE_ID     = "0x00" + ubinascii.hexlify(machine.unique_id()).decode()
MQTT_BASE          = MQTT_DEVICE_NAME + "/"
MQTT_COMMAND_TOPIC = MQTT_BASE + "command/relay/#"
MQTT_STATUS_TOPIC  = MQTT_BASE + "status"
MQTT_DISC_TOPIC    = "homeassistant/switch/" + MQTT_DEVICE_ID

#Device details
DEV_INFO_MANUFACTURER = "Waveshare"
DEV_INFO_MODEL        = "Pico Relay B"

#WiFi credentials
WLAN_SSID = secrets["WLAN_SSID"]
WLAN_PWD  = secrets["WLAN_PWD"]

#keepalive timer
ka_count = 0
ka_threshold = 30 #status update interval (10 = 1 second)

wlan = network.WLAN(network.STA_IF)

def activate_wlan():
    #activates WLAN connection
    wlan.active(True)
    wlan.config(pm = 0xa11140) # Disable power-save mode
    wlan.connect(WLAN_SSID, WLAN_PWD)

    max_wait = 10
    while max_wait > 0:
        if wlan.status() < 0 or wlan.status() >= 3:
            break
        max_wait -= 1
        print('Waiting for ' + WLAN_SSID)
        time.sleep(1)

    if wlan.status() != 3:
        raise RuntimeError('Unable to connect to ' + WLAN_SSID)
    else:
        print('connected')
        status = wlan.ifconfig()
        print('ip = ' + status[0])

def msg_in(topic, msg):
  target = int(topic[-1:])
  mode = int(msg)

  if mode == 1:
    state = "ON"
  elif mode == 0:
    state = "OFF"
  else:
    state = "ERR"

  print("Channel " + str(target) + ": " + str(state))

  #set target relay to requested mode
  relays[target]["relay"](mode)

def setup_mqtt():
  mqtt_client = MQTTClient(MQTT_DEVICE_NAME, MQTT_BROKER, port=MQTT_PORT, user=MQTT_USER, password=MQTT_PWD, keepalive=10, ssl=False)
  mqtt_client.set_callback(msg_in)
  mqtt_client.set_last_will(MQTT_DEVICE_NAME + "/status", "offline", qos=0, retain=False)
  mqtt_client.connect()
  mqtt_client.subscribe(MQTT_COMMAND_TOPIC)
  print('MQTT connection sucessful!')
  return mqtt_client

def re_initialise():
  print('Error connecting to broker, retrying..')
  time.sleep(5)
  machine.reset()

def update_relay_states(mqtt_client):
    for i in range(1,9):
        len(relays[i])
        if len(relays[i]) == 3:
            if str(relays[i]['relay'].value()) != str(relays[i]['last_state']):
                #state has changed, update mqtt
                MQTT_MSG = MQTT_STATUS_TOPIC + '/relay/' + str(i)
                mqtt_client.publish(MQTT_MSG,str(relays[i]['relay'].value()))
                relays[i]['last_state'] = relays[i]["relay"].value()
        else:
            #first run, set last_state to current state & send mqtt update for all relays
            MQTT_MSG = MQTT_STATUS_TOPIC + '/relay/' + str(i)
            mqtt_client.publish(MQTT_MSG,str(relays[i]['relay'].value()))
            relays[i]["last_state"] = relays[i]["relay"].value()

def update_state():
  MQTT_MSG = 'online'
  mqtt_client.publish(MQTT_STATUS_TOPIC, MQTT_MSG)

#activate WiFi connection
activate_wlan()

#connect to MQTT broker
try:
  mqtt_client = setup_mqtt()
except OSError as e:
  re_initialise()

#publish home assistant discovery topics
for i in range(1,9):
    MQTT_MSG = '{"command_topic": "' + MQTT_DEVICE_NAME + '/command/relay/' + str(i) + '",{"availability": [{"topic": "' + MQTT_STATUS_TOPIC +'"}],"device": {"identifiers": ["' + MQTT_DEVICE_NAME + '"], "manufacturer": "' + DEV_INFO_MANUFACTURER +'", "model": "' + DEV_INFO_MODEL + '", "name": "' + MQTT_DEVICE_NAME + '"}, "name": "' + MQTT_DEVICE_NAME + '_ch_' + str(i) + '", "payload_off": 0, "payload_on": 1, "state_topic": "'+ MQTT_DEVICE_NAME +'/status/relay/' + str(i) + '", "unique_id": "'+MQTT_DEVICE_NAME + '_relay_' + str(i) + '_pico"}'
    mqtt_client.publish(MQTT_DISC_TOPIC + '/switch/' + str(i) + '/config', MQTT_MSG, retain=True)

#set initial statusa
update_state()

#main loop
while True:
  try:
    #check for incoming commands
    mqtt_client.check_msg()
    
    #check for changes and update state(s) if needed
    update_relay_states(mqtt_client)
    
    #increment keepalive counter and send status update if threshold reached/breached
    ka_count +=1
    if ka_count >= ka_threshold:
      update_state()
      ka_count = 0

    #wait before looping again
    time.sleep(0.1)

  except OSError as e:
    re_initialise()
