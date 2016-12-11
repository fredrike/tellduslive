#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Communicate with Telldus Live server."""

import logging
from datetime import timedelta

import requests
from requests.compat import urljoin
from requests_oauthlib import OAuth1

_LOGGER = logging.getLogger(__name__)

API_URL = 'https://api.telldus.com/json/'
TIMEOUT = timedelta(seconds=5)

UNNAMED_DEVICE = 'NO NAME'

# Tellstick methods
# pylint:disable=invalid-name
TURNON = 1
TURNOFF = 2
BELL = 4
TOGGLE = 8
DIM = 16
LEARN = 32
UP = 128
DOWN = 256
STOP = 512
RGBW = 1024
THERMOSTAT = 2048

# Supported by this client
SUPPORTED_METHODS = (
    TURNON |
    TURNOFF |
    DIM |
    UP |
    DOWN |
    STOP)

STR_METHODS = {
    TURNON: "TURNON",
    TURNOFF: "TURNOFF",
    BELL: "BELL",
    TOGGLE: "TOGGLE",
    DIM: "DIM",
    LEARN: "LEARN",
    UP: "UP",
    DOWN: "DOWN",
    STOP: "STOP",
    RGBW: "RGBW",
    THERMOSTAT: "THERMOSTAT"
}

# Corresponding API methods
API_METHODS = {
    TURNON: 'device/turnOn',
    TURNOFF: 'device/turnOff',
    DIM: 'device/dim',
    UP: 'device/up',
    DOWN: 'device/down',
    STOP: 'device/stop',
}


# sensor types

TEMPERATURE = 'temperature',
HUMIDITY = 'humidity',
RAINRATE = 'rrate',
RAINTOTAL = 'rtot',
WINDDIRECTION = 'wdir',
WINDAVERAGE = 'wavg',
WINDGUST = 'wgust',
UV = 'uv',
WATT = 'watt',
LUMINANCE = 'lum',
DEW_POINT = 'dew',  # ?
BAROMETRIC_PRESSURE = '?',


class Client:
    """Tellduslive client."""

    def __init__(self,
                 public_key,
                 private_key,
                 token,
                 token_secret):
        """Initialize a client."""
        self._session = requests.Session()
        self._session.auth = OAuth1(
            public_key,
            private_key,
            token,
            token_secret)
        self._devices = {}
        self._sensors = {}

    def device(self, device_id):
        """Return the raw representaion of a device."""
        return self._devices[device_id]

    def sensor(self, sensor_id):
        """Return the raw representaion of a sensor."""
        return self._sensors[sensor_id]

    def request(self, url, **params):
        """Send a request to the Tellstick Live API."""
        try:
            url = urljoin(API_URL, url)
            _LOGGER.debug('Request %s %s', url, params)
            response = self._session.get(url,
                                         params=params,
                                         timeout=TIMEOUT.seconds)
            response.raise_for_status()
            _LOGGER.debug('Response %s %s',
                          response.status_code,
                          response.json())
            response = response.json()
            if 'error' in response:
                raise IOError(response['error'])
            return response
        except (OSError, IOError) as error:
            _LOGGER.error('Failed request: %s', error)

    def execute(self, method, **params):
        """Make request, check result if successful."""
        response = self.request(method, **params)
        return response and response.get('status') == 'success'

    def request_user(self):
        """Request user details."""
        return self.request('user/profile')

    def request_devices(self):
        """Request list of devices from server."""
        res = self.request('devices/list',
                           supportedMethods=SUPPORTED_METHODS,
                           includeIgnored=0)
        return res.get('device') if res else []

    def request_sensors(self):
        """Request list of sensors from server."""
        res = self.request('sensors/list',
                           includeValues=1,
                           includeScale=1,
                           includeIgnored=0)
        return res.get('sensor') if res else []

    def update(self):
        """Updates all devices and sensors from server."""
        self._devices = {device['id']: device
                         for device in self.request_devices()}
        self._sensors = {sensor['id']: sensor
                         for sensor in self.request_sensors()}

    @property
    def devices(self):
        """Request representations of all devices."""
        return (Device(self, device_id) for device_id in self._devices)

    @property
    def sensors(self):
        """Request representations of all sensors."""
        return (Sensor(self, sensor_id) for sensor_id in self._sensors)

    @property
    def sensor_data_items(self):
        """Collect and return all data items for all sensors."""
        return sum([sensor.data_items for sensor in self.sensors], [])


class Device:
    """Tellduslive device."""

    def __init__(self, client, device_id):
        """Initialize a device."""
        self._client = client
        self._device_id = device_id

    def __str__(self):
        """String representation."""
        return "%s@%s:%s(%s:%s)(%s)" % (
            "Device",
            self.device_id,
            self.name or UNNAMED_DEVICE,
            self.str_methods(self.state),
            self.statevalue,
            self.str_methods(self.methods))

    @staticmethod
    def str_methods(val):
        """String representation of methods or state."""
        res = []
        for method in STR_METHODS:
            if val & method:
                res.append(STR_METHODS[method])
        return "|".join(res)

    @property
    def _device(self):
        """Return the raw representation of the device."""
        return self._client.device(self._device_id)

    def _execute(self, command, **params):
        """Send command to server and update local state."""
        params.update(id=self._device_id)
        api_method = API_METHODS[command]
        if self._client.execute(api_method, **params):
            self._device['state'] = command
            return True

    @property
    def device_id(self):
        """Id of device."""
        return self._device_id

    @property
    def name(self):
        """Name of device."""
        return self._device['name']

    @property
    def state(self):
        """State of device."""
        return self._device['state']

    @property
    def statevalue(self):
        """State value of device."""
        return self._device['statevalue']

    @property
    def methods(self):
        """Supported methods by device."""
        return self._device['methods']

    @property
    def is_on(self):
        """Return true if device is on."""
        return (self.state == TURNON or
                self.state == DIM)

    @property
    def dim_level(self):
        """Return current dim level."""
        try:
            return int(self.statevalue)
        except ValueError:
            return None

    def turn_on(self):
        """Turn device on."""
        return self._execute(TURNON)

    def turn_off(self):
        """Turn device off."""
        return self._execute(TURNOFF)

    def dim(self, level):
        """Dim device."""
        return self._execute(DIM, level=level)

    def up(self):
        """Pull device up."""
        return self._execute(UP)

    def down(self):
        """Pull device down."""
        return self._execute(DOWN)

    def stop(self):
        """Stop device."""
        return self._execute(STOP)


class Sensor:
    """Tellduslive device."""

    def __init__(self, client, sensor_id):
        """Initialize sensor."""
        self._client = client
        self._sensor_id = sensor_id

    def __str__(self):
        """String representation."""
        items = ",".join("%s=%s" % (d.name, d.value)
                         for d in self.data_items)
        return ("%s@%s:%s(%s)" % (
            "Sensor",
            self.sensor_id,
            self.name or UNNAMED_DEVICE,
            items)).encode('utf-8')

    @property
    def _sensor(self):
        """Return raw sensor data."""
        return self._client.sensor(self._sensor_id)

    @property
    def name(self):
        """Return name of sensor."""
        return self._sensor['name']

    @property
    def sensor_id(self):
        """Return unique id for sensor."""
        return self._sensor_id

    @property
    def data(self):
        """Return data field."""
        return self._sensor['data']

    @property
    def data_items(self):
        """Return data items for sensor."""
        return [DataItem(self._client, (self._sensor_id,
                                        item['name'],
                                        item['scale']))
                for item in self.data]


class DataItem:
    """A Tellduslive Sensor data item."""

    def __init__(self, client, item_id):
        """Initialize."""
        self._client = client
        self._item_id = item_id

    def __str__(self):
        """String representaion."""
        return ("%s@%s:%s(%s=%s)" % (
            "DataItem",
            self.sensor.sensor_id,
            self.sensor.name or UNNAMED_DEVICE,
            self.name or UNNAMED_DEVICE,
            self.value)).encode('utf-8')

    @property
    def sensor_id(self):
        """Return id of corresponding sensor."""
        return self._item_id[0]

    @property
    def name(self):
        """Return name."""
        return self._item_id[1]

    @property
    def scale(self):
        """Return scale."""
        return self._item_id[2]

    @property
    def item_id(self):
        """Unique identifier for a data item."""
        return self._item_id

    @property
    def sensor(self):
        """Return corresponding sensor."""
        return Sensor(self._client, self.sensor_id)

    @property
    def value(self):
        """Return value of sensordataitem."""
        return next((
            item['value']
            for item in self.sensor.data
            if (item['name'] == self.name and
                item['scale'] == self.scale)), None)


def main():
    """Dump configured devices and sensors."""
    from os import path
    from sys import argv
    logging.basicConfig(level=logging.INFO)
    try:
        with open(path.join(path.dirname(argv[0]),
                            ".credentials.conf")) as config:
            credentials = dict(
                x.split(": ")
                for x in config.read().strip().splitlines())
    except (IOError, OSError):
        print("Could not read configuration")
        exit(-1)

    client = Client(**credentials)
    client.update()
    print("Devices\n"
          "-------")
    for device in client.devices:
        print(device)

    print("\n"
          "Sensors\n"
          "-------")
    for sensor in client.sensors:
        print(sensor)

    print("\n"
          "Data items\n"
          "----------")
    for item in client.sensor_data_items:
        print(item)


if __name__ == '__main__':
    main()