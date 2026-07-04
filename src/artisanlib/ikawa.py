#
# ABOUT
# IKAWA BLE device support for Artisan
#
# LICENSE
# This program or module is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 2 of the License, or
# version 3 of the License, or (at your option) any later version.
#
# AUTHOR
# Marko Luther (import logic removed; BLE retained)

import logging
from collections.abc import Callable, Generator
from typing import override, Final, Any

from PyQt6.QtCore import QMutex, QWaitCondition

from artisanlib.ble_port import ClientBLE
from proto import IkawaCmd_pb2  # type: ignore[unused-ignore]

_log: Final[logging.Logger] = logging.getLogger(__name__)


try: # BLE not available on some platforms
    class IKAWA_BLE(ClientBLE):

        ###CmdType
        BOOTLOADER_GET_VERSION:      Final[int] = 0
        MACH_PROP_GET_TYPE:          Final[int] = 2
        MACH_PROP_GET_ID:            Final[int] = 3
        MACH_STATUS_GET_ERROR_VALUE: Final[int] = 10
        MACH_STATUS_GET_ALL_VALUE:   Final[int] = 11
        HIST_GET_TOTAL_ROAST_COUNT:  Final[int] = 13
        PROFILE_GET:                 Final[int] = 15
        PROFILE_SET:                 Final[int] = 16
        SETTING_GET:                 Final[int] = 17
        MACH_PROP_GET_SUPPORT_INFO:  Final[int] = 23


        # IKAWA BLE name prefix
        DEVICE_NAME_IKAWA:   Final[str] = 'IKAWA'
        # IKAWA BLE service and characteristics UUIDs
        IKAWA_SERVICE_UUID:  Final[str] = 'C92A6046-6C8D-4116-9D1D-D20A8F6A245F'
        IKAWA_NOTIFY_UUID:   Final[str] = '948C5059-7F00-46D9-AC55-BF090AE066E3'
        IKAWA_WRITE_UUID:    Final[str] = '851A4582-19C1-4E6C-AB37-E7A03766BA16'

        def __init__(self,
                    connected_handler:Callable[[], None]|None = None,
                    disconnected_handler:Callable[[], None]|None = None) -> None:
            super().__init__()

            # register IKAWA UUIDs
            self.add_device_description(self.IKAWA_SERVICE_UUID, self.DEVICE_NAME_IKAWA)
            self.add_notify(self.IKAWA_NOTIFY_UUID, self.notify_callback)
            self.add_write(self.IKAWA_SERVICE_UUID, self.IKAWA_WRITE_UUID)

            # handlers
            self.connected_handler:Callable[[], None]|None = connected_handler
            self.disconnected_handler:Callable[[], None]|None = disconnected_handler

            self.receiveMutex:QMutex = QMutex()
            self.dataReceived:QWaitCondition = QWaitCondition()
            self.receiveTimeout:int = 400

            self.connected_state:bool = False

            self.TX:float = 0
            self.ET:float = -1
            self.BT:float = -1
            self.SP:float = -1
            self.RPM:float = -1 # fan speed in RPM
            self.heater:int = -1
            self.fan:int = -1
            self.state:int = -1
            self.absolute_humidity:float = -1
            self.humidity_roc:float = -1
            self.humidity_roc_dir:int = -1
            self.ambient_pressure:float = -1
            self.board_temp:float = -1
            # state is one of
            #  0: on-roaster (IDLE)
            #  1: pre-heating (START)
            #  2: ready-to-roast
            #  3: roasting
            #  4: roaster-is-busy (BUSY)
            #  5: cooling (DROP)
            #  6: doser-open (CHARGE)
            #  7: unexpected-problem (ERROR)
            #  8: ready-to-blow
            #  9: test-mode
            # 10: detecting
            # 11: development

            self.seq:Generator[int] = self.seqNum() # message sequence number generator
            self.frame_char:Final[int]          = 126 # b'\x7e'
            self.escape_char:Final[int]         = 125 # b'\x7d'
            self.escape_offset:Final[int]       = 32
            self.frame_char_escaped:Final[int]  = self.frame_char - self.escape_offset # 94 = b'\x5e'
            self.escape_char_escaped:Final[int] = self.escape_char - self.escape_offset # 93 = b'\x5d'

            # either empty, or contains a partial payload incl. the beginning frame_char or contains the full payload incl. the beginning and ending frame_char
            self.rcv_buffer:bytes|None = None

        @staticmethod
        def seqNum() -> Generator[int]:
            num = 1
            while True:
                yield num
                num = (num + 1) % 32767

        @staticmethod
        def crc16(bArr:bytes, i:int) -> bytes:
            for i2 in bArr:
                i3 = (i2 & 255) ^ (i & 255)
                i4 = i3 ^ ((i3 << 4) & 255)
                i = ((((i >> 8) & 255) | ((i4 << 8) & 65535)) ^ (i4 >> 4)) ^ ((i4 << 3) & 65535)
            return int(i & 65535).to_bytes(2, byteorder='big')

        def escape(self, msg:bytes) -> bytes:
            message:bytes = b''
            for i,_ in enumerate(msg):
                if msg[i] == self.escape_char:
                    message += self.escape_char.to_bytes(length=1, byteorder='big')
                    message += self.escape_char_escaped.to_bytes(length=1, byteorder='big')
                elif msg[i] == self.frame_char:
                    message += self.escape_char.to_bytes(length=1, byteorder='big')
                    message += self.frame_char_escaped.to_bytes(length=1, byteorder='big')
                else:
                    message += msg[i:i+1]
            return message

        def unescape(self, msg:bytes) -> bytes:
            unescaped_message = bytearray()
            i = 0
            while i < len(msg):
                if msg[i] == self.escape_char and len(msg)>i+1:
                    unescaped_message.append(msg[i + 1] + self.escape_offset)
                    i += 1 # skip one
                else:
                    unescaped_message.append(msg[i])
                i += 1
            return bytes(unescaped_message)

    #-----
        def clearData(self) -> None:
            self.ET = -1
            self.BT = -1
            self.SP = -1
            self.RPM = -1
            self.heater = -1
            self.fan = -1
            self.state = -1
            self.absolute_humidity = -1
            self.humidity_roc = -1
            self.humidity_roc_dir = -1
            self.ambient_pressure = -1
            self.board_temp = -1

        def reset(self) -> None:
            self.rcv_buffer = None

        def start_sampling(self) -> None:
            self.reset()
            # start BLE loop
            self.start()

        def stop_sampling(self) -> None:
            self.stop()

        def notify_callback(self, _characteristic:Any, data:bytearray) -> None:
            _log.debug('notify: %s', data)
            if self._logging:
                _log.info('received: %s',data)
            self.processData(bytes(data))

        def processData(self, data:bytes) -> None:
            if len(data) > 0:
                try:
                    if self.rcv_buffer is None and data[0] == self.frame_char:
                        # we received the frame start
                        self.rcv_buffer = b''
                    if self.rcv_buffer is not None:
                        # add new data
                        self.rcv_buffer += data
                        if len(self.rcv_buffer)>3 and self.rcv_buffer[0] == self.frame_char and self.rcv_buffer[-1] == self.frame_char:
                            # we received a full frame
                            message = self.unescape(self.rcv_buffer[1:-1])
                            crc = message[-2:]
                            payload = message[:-2]
                            # clear the buffer
                            self.rcv_buffer = None
                            # log payload
                            if self._logging:
                                _log.info('ikawa payload: %s',payload)
                            # verify CRC
                            if crc == self.crc16(payload, 65535):
                                try:
                                    decoded_message = IkawaCmd_pb2.IkawaResponse().FromString(payload) # pylint: disable=no-member
                                    if decoded_message.HasField('resp_mach_status_get_all'):
                                        _log.debug('IKAWA response.resp: %s (%s)', decoded_message.resp, decoded_message.MACH_STATUS_GET_ALL)
                                        status_get_all = decoded_message.resp_mach_status_get_all
                                        # temp below is Inlet Temperature on PRO machines and Exaust Temperature on HOME machines
                                        if status_get_all.HasField('temp_below'):
                                            self.ET = status_get_all.temp_below / 10
                                        elif status_get_all.HasField('temp_below_filtered'):
                                            self.ET = status_get_all.temp_below_filtered / 10
                                        else:
                                            self.ET = -1
                                        if status_get_all.HasField('temp_above'):
                                            self.BT = status_get_all.temp_above / 10
                                        elif status_get_all.HasField('temp_above_filtered'):
                                            self.BT = status_get_all.temp_above_filtered / 10
                                        else:
                                            self.BT = -1
                                        if status_get_all.HasField('setpoint'):
                                            self.SP = status_get_all.setpoint / 10
                                        else:
                                            self.SP = -1
                                        if status_get_all.HasField('fan_measured'):
                                            self.RPM = (status_get_all.fan_measured / 12)*60 # RPM
                                        else:
                                            self.RPM = -1
                                        self.heater = status_get_all.heater * 2
                                        self.fan = int(round(status_get_all.fan / 2.55))
                                        self.state = status_get_all.state
                                        # compute the average of all received ambient pressure readings (in mbar)
                                        if status_get_all.HasField('pressure_amb'):
                                            self.ambient_pressure = (status_get_all.pressure_amb if self.ambient_pressure == -1 else (self.ambient_pressure + status_get_all.pressure_amb)/2)
                                        # add absolute humidity in g/m^3
                                        if status_get_all.HasField('humidity_abs'):
                                            self.absolute_humidity = status_get_all.humidity_abs / 100
                                        else:
                                            self.absolute_humidity = -1
                                        # add humidity RoC in (g/m^3)/min
                                        if status_get_all.HasField('humidity_roc'):
                                            self.humidity_roc = status_get_all.humidity_roc / 10
                                        else:
                                            self.humidity_roc = -1
                                        # add humidity RoC direction (1: down, 2: up)
                                        if status_get_all.HasField('humidity_roc_direction'):
                                            self.humidity_roc_dir = int(status_get_all.humidity_roc_direction)
                                        else:
                                            self.humidity_roc_dir = -1
                                        # add board temperature in C
                                        if status_get_all.HasField('board_temp'):
                                            self.board_temp = status_get_all.board_temp / 10
                                        else:
                                            self.board_temp = -1
                                        # add data received and registered, enable delivery
                                        self.dataReceived.wakeAll()
                                except Exception as e: # pylint: disable=broad-except
                                    _log.error(e)
                            else:
                                _log.debug('processData() CRC check failed')
                except Exception as e:  # pylint: disable=broad-except
                    _log.error(e)

        @override
        def on_connect(self) -> None:
            self.connected_state = True
            if self.connected_handler is not None:
                self.connected_handler()

        @override
        def on_disconnect(self) -> None:
            self.connected_state = False
            if self.disconnected_handler is not None:
                self.disconnected_handler()

    #-----

        def requestDataMessage(self) -> bytes:
            message = IkawaCmd_pb2.Message() # pylint: disable=no-member
            message.cmd_type = IKAWA_BLE.MACH_STATUS_GET_ALL_VALUE
            message.seq = next(self.seq)
            msg = message.SerializeToString()
            crc = self.crc16(msg, 65535)
            return self.frame_char.to_bytes(length=1, byteorder='big') + self.escape(msg + crc) + self.frame_char.to_bytes(length=1, byteorder='big')

        def getData(self) -> None:
            if self.connected_state:
                request_data = self.requestDataMessage()
                self.send(request_data, response=True)
                # wait for data to be delivered
                self.receiveMutex.lock()
                res = self.dataReceived.wait(self.receiveMutex, self.receiveTimeout)
                if not res:
                    _log.debug('receive timeout')
                    # timeout, no data received
                    self.clearData()
                self.receiveMutex.unlock()
except Exception:  # pylint: disable=broad-except
    pass
