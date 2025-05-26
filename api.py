from __future__ import annotations
from enum import IntEnum
from typing import Any

import requests
import json
import logging

class ResponseCode(IntEnum):
    """
    Enum representing common HTTP status codes and their meanings.
    """
    OK = 200  # The request was successfully processed.
    NO_CONTENT = 204  # The request was successful, but there is no content to return.
    BAD_REQUEST = 400  # The request contains errors or invalid parameters.
    UNAUTHORIZED = 401  # Authentication is required or has failed.
    NOT_FOUND = 404  # The requested resource could not be found.
    TOO_MANY_REQUESTS = 429  # The client has sent too many requests (rate limiting).
    INTERNAL_SERVER_ERROR = 500  # The server encountered an unexpected condition.
    SERVICE_UNAVAILABLE = 503  # The server is temporarily unable to process the request.

    @classmethod
    def description(cls, code: int) -> str:
        """
        Returns a description for the given HTTP status code.

        :param code: The HTTP status code.
        :return: A description of the code as a string.
        """
        descriptions = {
            cls.OK: "The request was successfully processed.",
            cls.NO_CONTENT: "The request was successful, but there is no content to return.",
            cls.BAD_REQUEST: "The request contains errors or invalid parameters.",
            cls.UNAUTHORIZED: "Authentication is required or has failed.",
            cls.NOT_FOUND: "The requested resource could not be found.",
            cls.TOO_MANY_REQUESTS: "The client has sent too many requests (rate limiting).",
            cls.INTERNAL_SERVER_ERROR: "The server encountered an unexpected condition.",
            cls.SERVICE_UNAVAILABLE: "The server is temporarily unable to process the request.",
        }
        try:
            status_code = cls(code)
            return descriptions.get(status_code, "Unknown status code.")
        except ValueError:
            return "Unknown status code."

class API:
    """
    API class to handle authentication and communication with the backend.

    Disclaimer: getAir does NOT provide any service or warranty for the content provided! 
    We assume no liability for any damage caused by the provided content! 
    Furthermore, we make no claim to update this API in case of system updates - and thereby arising incompatibilities - or security holes.
    """
    def __init__(self:API, credentials_path: str = '.credentials'):
        """
        Initializes the API class.

        :param credentials_path: Path to the credentials file
        """
        self.AUTO_RECONNECT = True
        self._credentials_path = credentials_path
        self._session_token = None
        self._api_token = None
        self._auth_url = None
        self._api_url = None
        self._devices = []

        self._logger = logging.getLogger("CC-API").getChild("API")
        self.set_logging_level(logging.WARNING)

    def set_logging_level(self:API, level:int=logging.INFO) -> None:
        """
        Sets the logging level.

        :param level: logging level
        """
        logging.basicConfig(level=level)
    
    def _load_credentials(self:API) -> dict:
        """
        Load credentials from a JSON file.

        :return: A dictionary with username and password.
        """
        try:
            with open(self._credentials_path, "r") as file:
                credentials = json.load(file)
                for key in ['auth_url','api_url','username','password']:
                    if key not in credentials.keys():
                        self._logger.error(f"Key {key} not found in credentials")
                        return {}
                self._auth_url = credentials['auth_url']
                self._api_url = credentials['api_url']
                return credentials
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self._logger.error(f"Can't load credentials: {e}")
            return {}

    def _get_session_token(self:API) -> str | None:
        """
        Retrieve a session token by sending authentication credentials to the server.

        :return: Session token if successful, otherwise None.
        """

        credentials = self._load_credentials()

        payload = {"username": credentials['username'], "password": credentials['password']}
        headers = {'Content-Type': 'application/json'}

        try:
            response = requests.post(f"{self._auth_url}",
                                     data=json.dumps(payload), headers=headers)
            if response.status_code == ResponseCode.OK:
                response_data = response.json()
                if response_data.get('status') == 'SUCCESS':
                    self._session_token = response_data['sessionToken']
                    return self._session_token
                else:
                    print("Authentication failed:", response_data.get('status'))
            else:
                print(f"Error: {ResponseCode.description(response.status_code)}")
        except requests.RequestException as e:
            print(f"Request error: {e}")
        return None

    def _get_api_token(self:API):
        """
        Retrieve an api token by sending a session token to the server.

        :return: API token if successful, otherwise None.
        """
        params = {'issuer': 'GETAIR_API','sessionToken': self._session_token}
        headers = {'Content-Type': 'application/json'}

        try:
            response = requests.get(f'{self._api_url + "iam/token/"}', params=params, headers=headers)

            if response.status_code == ResponseCode.OK:
                response_data = response.json()
                if response_data.get('token'):
                    self._api_token = response_data['token']
                    return self._session_token
                else:
                    print("Authentication failed:", response_data.get('status'))
            else:
                print(f"Error: {ResponseCode.description(response.status_code)}")
        except requests.RequestException as e:
            print(f"Request error: {e}")
        return None

    def _request_get(self:API,path:str="") -> Any | None:
        """
        Sending a get request to the given path including authorization header.

        :param path: URL path of the get request
        :return: JSON decoded object or None on failure
        """
        try:
            headers = {'Authorization': f'Bearer {self._api_token}','Content-Type': 'application/json'}
            response = requests.get(f'{self._api_url}{path}', headers=headers)
            if response.status_code == ResponseCode.OK:
                self._logger.debug("Get request succeeded")
                return response.json()
            elif response.status_code == ResponseCode.UNAUTHORIZED and self.AUTO_RECONNECT:
                self._logger.info("Reconnecting")
                if self.connect():
                    return self._request_get(path=path)
            else:
                self._logger.error(f"Error: {ResponseCode.description(response.status_code)}")
        except requests.RequestException as e:
            self._logger.error(f"Request error (GET): {e}")

        return None

    def _request_put(self:API,path:str="",data:dict | None = None) -> Any | None:
        """
        Sending a put request to the given path including authorization header.

        :param path: URL path of the get request
        :param data: payload of the put request
        :return: JSON decoded object or None on failure
        """
        try:
            headers = {'Authorization': f'Bearer {self._api_token}','Content-Type': 'application/json'}
            payload = json.dumps(data)
            response = requests.put(f'{self._api_url}{path}', data=payload, headers=headers)
            if response.status_code == ResponseCode.OK:
                self._logger.debug("Put request succeeded")
                return response.json()
            elif response.status_code == ResponseCode.NO_CONTENT:
                self._logger.debug("Put request succeeded with no answer")
                return
            elif response.status_code == ResponseCode.UNAUTHORIZED and self.AUTO_RECONNECT:
                self._logger.info("Reconnecting")
                if self.connect():
                    return self._request_put(path=path,data=data)
            else:
                self._logger.error(f"Error: {ResponseCode.description(response.status_code)}")

        except requests.RequestException as e:
            self._logger.error(f"Request error (PUT): {e}")
        return None
    
    def connect(self:API = None) -> API | None:
        """
        (Re-) Connect the API with the configured credentials
        
        :return: API if the connection was successfull, else None
        """
        if not self:
            return API().connect()
        if not self._get_session_token() or not self._get_api_token():
            self._logger.info("Unable to connect.")
            return None
        return self


    def get_devices(self:API) -> list[Device]:
        """
        List all connected devices to the account.

        :return: List of device objects, connected to the account
        """
        response = self._request_get("devices/")

        self._logger.debug(f"Active devices found: {response}")

        if not response:
            return []

        for entry in response:
            mac = entry.get("deviceIdentifier","")
            if len(mac) != 12:
                pass
            else:
                self._devices.append(Device(device_id=mac,api=self))

        if not self._devices:
            self._logger.debug("Could not find any device")
        return self._devices.copy()

    def get_device(self:API,deviceID:str) -> Device | None:
        """
        Try to get an connected devices with given deviceID.

        :param deviceID: Unique ID of the device (MAC address)
        :return: Device object
        """
        deviceID = deviceID.replace(":","").upper()
        for device in self.get_devices():
            if device.device_id == deviceID:
                return device
        self._logger.info(f"Could not find device {deviceID}")
        return None


class Device:
    """
    Represents a physical device managing system and zone services.

    Provides access to system-wide attributes such as
    speed, temperature, humidity, modes and runtime.
    Supports efficient state updates by tracking attribute changes internally.

    Attributes are exposed via Pythonic properties and methods to get or set
    configurations, including time profiles, fan speeds, and environmental settings.

    Typical usage includes fetching latest data from the backend, pushing updates,
    and serializing state as JSON for communication or logging purposes.

    Use the update() method to send data, or enable the AUTOSET function for automatic real-time updates.

    Disclaimer: getAir does NOT provide any service or warranty for the content provided! 
    We assume no liability for any damage caused by the provided content! 
    Furthermore, we make no claim to update this API in case of system updates - and thereby arising incompatibilities - or security holes.
    """

    class _System:
        def __init__(self):
            self.system_type:str = None
            self.system_version = None
            self.system_id:str = None
            self.num_zones = None
            self.runtime = None
            self.modelock = None
            self.notification = None
            self.notify_time = None
            self.humidity = None
            self.air_pressure = None
            self.temperature = None
            self.indoor_air_quality = None
            self.iaq_accuracy = None
            self.fw_app_version = None
            self.fw_app_version_str = None
            self.boot_time = None
            # Time Profiles
            for i in range(1,11):
                setattr(self,f"time_profile_{i}_name", None)
                setattr(self,f"time_profile_{i}_data", None)
    
    class _Zone:
        def __init__(self):
            self.name = None
            self.runtime = None
            self.last_filter_change = None
            self.speed = None
            self.zone_index = None
            self.mode = None
            self.mode_deadline = None
            self.target_temp = None
            self.target_hmdty_level = None
            self.auto_mode_voc = None
            self.auto_mode_silent = None
            self.humidity = None
            self.temperature = None
            self.hmdty_outdoors = None
            self.temp_outdoors = None
            self.time_profile = None
    
    def __init__(self:Device, device_id: str, api: API = None):
        """
        Initializes the Device class with a unique device ID.

        :param device_id: Unique identifier for the device.
        :param api: API for communication with the backend
        """

        self.AUTOSET = False

        self._system = Device._System()
        self._zone = Device._Zone()
        self._system_changed = {}
        self._zone_changed = {}

        self._system.system_id = {'type':'Buffer','data':[int(device_id[i:i+2],16) for i in range(0,len(device_id),2)]}
        self._api = api if api else API()

        self._logger = self._api._logger.getChild("Device")

        self.fetch()

    def fetch(self:Device) -> bool:
        """
        Attempts to retrieve the latest data from the backend.

        :return: True if the fetch was successful, False otherwise.
        """
        try:
            system_data = self._api._request_get(f"devices/{self.device_id}/services/System")
            if not system_data:
                self._logger.debug("Empty System data")
                return False

            for attr in self._system.__dict__:
                key = attr.replace("_","-")
                try:
                    if key in system_data:
                        self._system.__setattr__(attr,system_data[key])
                except Exception as e:
                    self._logger.warning(f"Can't update value {key}. {e}")
                    return False

            zone_data = self._api._request_get(f"devices/1.{self.device_id}/services/Zone")
            if not zone_data:
                self._logger.debug("Empty Zone data")
                return False

            for attr in self._zone.__dict__:
                key = attr.replace("_","-")
                try:
                    if key in zone_data:
                        self._zone.__setattr__(attr,zone_data[key])
                except Exception as e:
                    self._logger.warning(f"Can't update value {key}. {e}")
                    return False

        except Exception as e:
            self._logger.error(f"Error on updating values. {e}")
            return False
        
        return True

    def push(self:Device) -> bool:
        """
        Sends the current data to the backend.

        :return: True if the push was successful, False otherwise.
        """
        try:
            if len(self._system_changed):
                resp1 = self._api._request_put(f"devices/{self.device_id}/services/System",self._system_changed)
                self._system_changed.clear()
            if len(self._zone_changed):
                resp2 = self._api._request_put(f"devices/{self.device_id}/services/Zone",self._zone_changed)
                self._zone_changed.clear()
        except Exception as e:
            self._logger.error(f"Error on pushing values. {e}")
            return False
        #ToDo check resp code
        return True
    
    def update(self:Device) -> bool:
        """
        Synchronizes data by pushing the current state to the backend 
        and then fetching the latest updates.

        :return: True if the update was successful, False otherwise.
        """
        return self.push() and self.fetch()

    def json(self:Device) -> dict[str,dict]:
        """
        Serializes the current device state into a nested dictionary.

        :return: A dictionary with 'System' and 'Zone' keys containing 
                the respective attributes and their values.
        """
        res = {"System":{},"Zone":{}}
        for attr in self._system.__dict__:
            res["System"][attr] = getattr(self._system,attr)
        for attr in self._zone.__dict__:
            res["Zone"][attr] = getattr(self._zone,attr)
        return res

    def _key_changed(self:Device, service: _System | _Zone, key: str,value) -> bool:
        """
        Internal method to mark a changed attribute for efficient update tracking.

        :param service: The service type (either _System or _Zone) where the change occurred.
        :param key: The name of the changed attribute.
        :param value: The new value of the attribute.
        :return: True if the change was recorded successfully, otherwise False.
        """
        if service == Device._System:
            self._system_changed[key] = value
        elif service == Device._Zone:
            self._zone_changed[key] = value
        else:
            return False
        if self.AUTOSET:
            return self.push()
        return True
    
    @property
    def device_id(self: Device) -> str:
        """
        Returns the unique device ID (typically the MAC address).

        :return: Device ID as a string (e.g., '001A2B3C4D5E').
        """
        system_id = self._system.system_id
        if isinstance(system_id, str):
            return system_id
        elif isinstance(system_id, dict) and "data" in system_id:
            return ''.join(f'{b:02x}' for b in system_id['data']).upper()
        return None

    @property
    def system_type(self: Device) -> str:
        """
        Returns the system type.

        :return: Either 'ComfortControlProBT' or 'ComfortControlPro'.
        """
        return self._system.system_type

    @property
    def fw_app_version_str(self: Device) -> str:
        """
        Returns the firmware version of the device.

        :return: Firmware version string.
        """
        return self._system.fw_app_version_str

    @property
    def boot_time(self: Device) -> int:
        """
        Returns the system boot time.

        :return: Unix timestamp in seconds.
        """
        return self._system.boot_time

    @property
    def runtime(self: Device) -> int:
        """
        Retrieves the total runtime of the zone in hours.

        :return: Runtime in hours.
        """
        return self._zone.runtime

    @property
    def name(self: Device) -> str:
        """
        Retrieves the zone name.

        :return: Zone name as a string.
        """
        return self._zone.name
    
    @name.setter
    def name(self: Device, value: str):
        """
        Sets the name of the zone.

        :param value: Zone name (max 64 characters).
        """
        self._zone.name = value
        self._key_changed(Device._Zone, "name", value)

    @property
    def air_pressure(self: Device) -> int:
        """
        Returns the current air pressure.

        :return: Air pressure in hPa.
        """
        return self._system.air_pressure

    @property
    def air_quality(self: Device) -> int:
        """
        Returns the measured indoor air quality level.

        :return: Value from 0 to 200 (0 = excellent air quality, fewer VOCs).
        """
        return self._system.indoor_air_quality

    @property
    def humidity(self: Device) -> float:
        """
        Retrieves the current indoor humidity.

        :return: Humidity percentage.
        """
        return self._zone.humidity

    @property
    def temperature(self: Device) -> float:
        """
        Retrieves the current indoor temperature.

        :return: Temperature in °C.
        """
        return self._zone.temperature

    @property
    def outdoor_humidity(self: Device) -> float:
        """
        Retrieves the current outdoor humidity.

        :return: Humidity percentage.
        """
        return self._zone.hmdty_outdoors

    @property
    def outdoor_temperature(self: Device) -> float:
        """
        Retrieves the current outdoor temperature.

        :return: Temperature in °C.
        """
        return self._zone.temp_outdoors
 
    @property
    def indoor_humidity(self: Device) -> int:
        """
        Retrieves the current outdoor humidity.

        :return: Humidity percentage.
        """
        return self._system.humidity

    @property
    def indoor_temperature(self: Device) -> int:
        """
        Retrieves the current outdoor temperature.

        :return: Temperature in °C.
        """
        return self._system.temperature
    
    @property
    def speed(self: Device) -> float:
        """
        Retrieves the current fan speed level.

        :return: Speed level as a float (e.g., 0.0 to 4.0).
        """
        return self._zone.speed
        
    @speed.setter
    def speed(self: Device, value):
        """
        Sets the fan speed level.

        :param value: Speed level (0 to 4).
        """
        self._zone.speed = value
        self._key_changed(Device._Zone, "speed", value)

    @property
    def mode(self: Device) -> str:
        """
        Retrieves the currently active ventilation mode.

        :return: Mode as a string.
        """
        return self._zone.mode
        
    @mode.setter
    def mode(self: Device, value: str):
        """
        Sets the ventilation mode.

        :param value: One of 'ventilate', 'ventilate_hr', 'ventilate_inv', 'night', 'auto', or 'rush'.
        """
        self._zone.mode = value
        self._key_changed(Device._Zone, "mode", value)

    @property
    def mode_deadline(self: Device) -> int:
        """
        Retrieves the end time for the current mode.

        :return: Unix timestamp (in seconds).
        """
        return self._zone.mode_deadline
    
    @mode_deadline.setter
    def mode_deadline(self: Device, value: int):
        """
        Defines when the current mode should end.

        :param value: Unix timestamp (in seconds).
        """
        self._zone.mode_deadline = value
        self._key_changed(Device._Zone, "mode-deadline", value)

    @property
    def target_temp(self: Device) -> float:
        """
        Retrieves the target indoor temperature.

        :return: Target temperature in °C.
        """
        return self._zone.target_temp
    
    @target_temp.setter
    def target_temp(self: Device, value: float):
        """
        Sets the target indoor temperature for climate control.

        :param value: Desired temperature in °C.
        """
        self._zone.target_temp = value
        self._key_changed(Device._Zone, "target-temp", value)

    @property
    def target_hmdty_level(self: Device) -> str:
        """
        Retrieves the selected target humidity range.

        :return: Humidity level setting as a string.
        """
        return self._zone.target_hmdty_level

    @target_hmdty_level.setter
    def target_hmdty_level(self: Device, value: str):
        """
        Sets the preferred humidity range for automated fan control.
        Recommended indoor range: 40%–60%.

        :param value: One of 'thirty-fifty', 'fourty-sixty', or 'fifty-seventy'.
        """
        self._zone.target_hmdty_level = value
        self._key_changed(Device._Zone, "target-hmdty-level", value)

    @property
    def auto_mode_voc(self: Device) -> bool:
        """
        Retrieves the status of VOC-based auto mode.

        :return: True if enabled, False otherwise.
        """
        return self._zone.auto_mode_voc
        
    @auto_mode_voc.setter
    def auto_mode_voc(self: Device, value: bool):
        """
        Enables or disables VOC-based auto mode for air quality optimization.

        :param value: True to enable, False to disable.
        """
        self._zone.auto_mode_voc = value
        self._key_changed(Device._Zone, "auto-mode-voc", value)

    @property
    def auto_mode_silent(self: Device) -> bool:
        """
        Retrieves the status of silent mode.

        :return: True if silent mode is enabled, False otherwise.
        """
        return self._zone.auto_mode_silent
    
    @auto_mode_silent.setter
    def auto_mode_silent(self: Device, value: bool):
        """
        Enables or disables silent mode to reduce fan noise.

        :param value: True to enable silent mode, False to disable.
        """
        self._zone.auto_mode_silent = value
        self._key_changed(Device._Zone, "auto-mode-silent", value)

    @property
    def active_time_profile(self: Device) -> int:
        """
        Retrieves the ID of the active time profile.

        :return: Profile ID (0 = inactive, 1–10 = active profile).
        """
        return self._zone.time_profile
    
    @active_time_profile.setter
    def active_time_profile(self: Device, value: int):
        """
        Sets the active time profile ID.

        :param value: 0 to deactivate, or 1–10 to select a profile.
        """
        self._zone.time_profile = value
        self._key_changed(Device._Zone, "time-profile", value)

    @property
    def last_filter_change(self: Device) -> int:
        """
        Returns the current runtime of the last filter change.

        :return: runtime in hour
        """
        return self._zone.last_filter_change
    
    @last_filter_change.setter
    def last_filter_change(self: Device, value: int):
        """
        Updates the timestamp of the last filter change.

        :param value: Unix timestamp (in seconds).
        """
        self._zone.last_filter_change = value
        self._key_changed(Device._Zone, "last-filter-change", value)

    def get_time_profile_name(self:Device,number: int) -> str:
        """
        Get the name of the specified time profile (1–10).

        :param number: Time profile index.
        :return: Profile name or empty string if out of range.
        """
        if number < 1 or number > 10:
            self._logger.error("Index of time-profile is out of range")
            return ""
        return self._system.__getattribute__(f"time_profile_{number}_name")

    def set_time_profile_name(self:Device,number: int, value: str):
        """
        Set the name for the specified time profile (1–10). The name must not exceed 15 characters.

        :param number: Time profile index.
        :param value: New profile name.
        """
        if number < 1 or number > 10:
            self._logger.error("Index of time-profile is out of range")
            return
        self._system.__setattr__(f"time_profile_{number}_name",value)
        self._key_changed(Device._System,f"time_profile_{number}_name",value)

    def get_time_profile_data(self:Device,number: int) -> list[bytes]:
        """
        Get the raw data of the specified time profile (1–10).

        :param number: Time profile index.
        :return: Profile data or empty list if out of range.
        """
        if number < 1 or number > 10:
            self._logger.error("Index of time-profile is out of range")
            return []
        return self._system.__getattribute__(f"time_profile_{number}_data")

    def set_time_profile_data(self:Device,number: int, value: list[bytes]):
        """
        Updates the raw byte data of the specified time profile.

        Use with caution, as incorrect values may lead to unintended system behavior.

        :param number: Index of the time profile (1–10).
        :param value: List of bytes representing the time profile configuration.
        """

        if number < 1 or number > 10:
            self._logger.error("Index of time-profile is out of range")
            return
        if len(list) % 4 != 0:
            self._logger.warning("The length of the list must be a multiple of four")
        self._system.__setattr__(f"time_profile_{number}_data",{"type":"Buffer","data":value})
        self._key_changed(Device._System,f"time_profile_{number}_data",{"type":"Buffer","data":value})


# Example usage
if __name__ == "__main__":
    # Initialize API and authenticate
    api = API.connect()

    
