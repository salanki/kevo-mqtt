#!/usr/bin/env python

import os
import json
import time
from threading import Thread
from pykevoplus import KevoLock
import paho.mqtt.client as mqtt
import sys
import signal

locks = {}
quiet = False

def get_lock(lock_id):
    if locks.get(lock_id, None) is None:
        lock = KevoLock.FromLockID(lock_id, os.environ['KEVO_USERNAME'], os.environ['KEVO_PASSWORD'])
        locks[lock_id] = lock

        return lock
    else:
        return locks[lock_id]

def on_connect(client, userdata, flags, rc):
    if not quiet: print("Connected to MQTT with result code "+str(rc))

    client.subscribe(os.environ['MQTT_TOPIC'])

def on_message(client, userdata, msg):
    try:
        splits = msg.payload.split(' ')
        command = splits[0].lower()

        if command == 'unlock':
            data = { 'type': 'unlock', 'lock_id': splits[1] }
        elif command == 'lock':
            data = { 'type': 'lock', 'lock_id': splits[1] }
        else:
            data = json.loads(msg.payload)

        lock = get_lock(data['lock_id'])

        if data['type'].lower() == 'unlock':
            if not quiet: print "Unlocking: %s" % (data['lock_id'])
            lock.Unlock()
            publish_state(client, data['lock_id'], lock.state)
        elif data['type'].lower() == 'lock':
            if not quiet: print "Locking: %s" % (data['lock_id'])
            lock.Lock()
            publish_state(client, data['lock_id'], lock.state)
        elif data['type'].lower() == 'refresh':
            refresh(client, data['lock_id'])

    except Exception, e:
            print >> sys.stderr, "Exception: %s" % str(e)
            os.kill(os.getpid(), signal.SIGKILL)

def publish_state(client, lock_id, state):
    data = { "type": "lockState", "lock_id": lock_id, "state": state }
    msg = json.dumps(data)

    if not quiet: print msg
    client.publish(os.environ['MQTT_TOPIC'], msg)

def refresh(client, lock_id):
    state = get_lock(lock_id).GetBoltState()
    publish_state(client, lock_id, state)

def refresh_loop(client):
    while True:
        try:
            lockstring = os.environ.get('KEVO_LOCK_ID', '')
            lockids = lockstring.split(':')
            for lockid in lockids:
                refresh(client, lockid)
        except Exception, e:
            print >> sys.stderr, "Exception: %s" % str(e)
            os.kill(os.getpid(), signal.SIGKILL)

        time.sleep(int(os.environ['KEVO_REFRESH_INTERVAL']))

if os.environ.get('MQTT_PORT', None) is None:
    port = 1883
else:
    port = int(os.environ['MQTT_PORT'])

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

user = os.environ.get('MQTT_USERNAME', None)
if user is not None:
    password = os.environ.get('MQTT_PASSWORD', None)
    client.username_pw_set(user, password)
    
client.connect(os.environ['MQTT_BROKER'], port, 60)

t = Thread(target=refresh_loop, args=(client,))
t.start()

client.loop_forever()
