import json
from .const import DOMAIN, SIGNAL_CALL_ENDED, SIGNAL_CALL_STARTED
from .ConfigEntryOAuthTokenStorage import ConfigFolderOAuthTokenStorage
from .ConfigEntryNotificationInfoStorage import ConfigFolderNotificationInfoStorage
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.helpers.dispatcher import dispatcher_send
from bluecon import BlueConAPI, INotification, CallNotification, CallEndNotification, IOAuthTokenStorage, INotificationInfoStorage, OAuthToken
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry


PLATFORMS: list[str] = [Platform.BINARY_SENSOR, Platform.LOCK, Platform.CAMERA, Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    def notification_callback(notification: INotification):
        if type(notification) is CallNotification:
            dispatcher_send(hass, SIGNAL_CALL_STARTED.format(notification.deviceId, notification.accessDoorKey))
        elif type(notification) is CallEndNotification:
            dispatcher_send(hass, SIGNAL_CALL_ENDED.format(notification.deviceId))

    hass.data[DOMAIN] = {
        "bluecon": None
    }

    bluecon = BlueConAPI.create_already_authed(notification_callback, ConfigFolderOAuthTokenStorage(hass, entry), ConfigFolderNotificationInfoStorage(hass, entry))
    await hass.async_add_executor_job(bluecon.startNotificationListener)

    @callback
    async def cleanup(event):
        await bluecon.stopNotificationListener()
    
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)
    hass.data[DOMAIN][entry.entry_id] = bluecon

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok

async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    tempNotificationInfoStorage: INotificationInfoStorage = ConfigEntryNotificationInfoStorage(hass, config_entry)
    tempOAuthTokenStorage: IOAuthTokenStorage = ConfigEntryOAuthTokenStorage(hass, config_entry)

    if config_entry.version == 1:
        try:
            with open("credentials.json", "r") as f:
                credentials = json.load(f)
        except FileNotFoundError:
            credentials = None
        
        try:
            with open("persistent_ids.txt", "r") as f:
                persistentIds = [x.strip() for x in f]
        except FileNotFoundError:
            persistentIds = None
        
        tempOAuthTokenStorage.storeOAuthToken(OAuthToken.fromJson(config_entry.data["token"]))
        tempNotificationInfoStorage.storeCredentials(credentials)
        for persistentId in persistentIds:
            tempNotificationInfoStorage.storePersistentId(persistentId)

        config_entry.version = 4
        hass.config_entries.async_update_entry(config_entry, data={}, options={})
    if config_entry.version == 2:
        
        tempOAuthTokenStorage.storeOAuthToken(OAuthToken.fromJson(config_entry.data["token"]))
        tempNotificationInfoStorage.storeCredentials(config_entry.data["credentials"])
        for persistentId in config_entry.data["persistentIds"]:
            tempNotificationInfoStorage.storePersistentId(persistentId)

        config_entry.version = 3
        hass.config_entries.async_update_entry(config_entry, data={}, options={})
    if config_entry.version == 3:
        tempOAuthTokenStorage.storeOAuthToken(OAuthToken.fromJson(config_entry.options["token"]))
        tempNotificationInfoStorage.storeCredentials(config_entry.options["credentials"])
        for persistentId in config_entry.options["persistentIds"]:
            tempNotificationInfoStorage.storePersistentId(persistentId)

        config_entry.version = 4
        hass.config_entries.async_update_entry(config_entry, data = {}, options = {})
    
    return True
