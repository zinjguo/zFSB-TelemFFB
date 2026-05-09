#
# zFSB/OpenFFB HID backend for TelemFFB.
#

"""
USB HID direct access for zFSB/OpenFFB force feedback devices.

This module intentionally keeps the same public surface as ffb_rhino.py so the
sim/effect layers can keep using HapticEffect and the FFBReport_* helpers.
"""

import ctypes
import inspect
import logging
import os
import time
import weakref
from dataclasses import dataclass
from typing import List, Self

from PyQt6.QtCore import QObject, QTimer, QTimerEvent, pyqtSignal

from telemffb.utils import Destroyable, DirectionModulator, clamp, millis, overrides

paths = ["hidapi.dll", "dll/hidapi.dll", os.path.join(os.path.dirname(os.path.abspath(__file__)), "dll", "hidapi.dll")]
for p in paths:
    try:
        ctypes.cdll.LoadLibrary(p)
        break
    except Exception:
        pass

import telemffb.hw.hid as hid


# OpenFFB report IDs, matching context/openffb_ffb.h.
HID_REPORT_ID_INPUT = 0x01
HID_REPORT_ID_PID_STATE_REPORT = 0x02
HID_REPORT_ID_SET_EFFECT = 0x01
HID_REPORT_ID_SET_ENVELOPE = 0x02
HID_REPORT_ID_SET_CONDITION = 0x03
HID_REPORT_ID_SET_PERIODIC = 0x04
HID_REPORT_ID_SET_CONSTANT_FORCE = 0x05
HID_REPORT_ID_SET_RAMP_FORCE = 0x06
HID_REPORT_ID_SET_CUSTOM_FORCE = 0x0E
HID_REPORT_ID_SET_DOWNLOAD_SAMPLE = 0x08
HID_REPORT_ID_EFFECT_OPERATION = 0x0A
HID_REPORT_ID_BLOCK_FREE = 0x0B
HID_REPORT_ID_DEVICE_CONTROL = 0x0C
HID_REPORT_ID_DEVICE_GAIN = 0x0D
HID_REPORT_ID_SET_CUSTOM_FORCE_OUTPUT_DATA = 0x07
HID_REPORT_ID_CREATE_EFFECT = 0x05
HID_REPORT_ID_PID_BLOCK_LOAD = 0x06
HID_REPORT_ID_PID_POOL_REPORT = 0x07

# VPForce-only feature reports are not present in the OpenFFB descriptor.
HID_REPORT_FEATURE_ID_GET_GAINS = 0x56
HID_REPORT_FEATURE_ID_SET_GAIN = 0x57

EFFECT_CONSTANT = 1
EFFECT_RAMP = 2
EFFECT_SQUARE = 3
EFFECT_SINE = 4
EFFECT_TRIANGLE = 5
EFFECT_SAWTOOTHUP = 6
EFFECT_SAWTOOTHDOWN = 7
EFFECT_SPRING = 8
EFFECT_DAMPER = 9
EFFECT_INERTIA = 10
EFFECT_FRICTION = 11
EFFECT_CUSTOM = 12

# TelemFFB uses these as extension effect types. Detent is mapped onto a normal
# spring for now; SpringAdjuster is handled natively by zFSB firmware.
EFFECT_DETENT = 13
EFFECT_SPRING_ADJUSTER = 14

PERIODIC_EFFECTS = [EFFECT_SQUARE, EFFECT_SINE, EFFECT_TRIANGLE, EFFECT_SAWTOOTHUP, EFFECT_SAWTOOTHDOWN]

CONTROL_ENABLE_ACTUATORS = 0x01
CONTROL_DISABLE_ACTUATORS = 0x02
CONTROL_STOP_ALL_EFFECTS = 0x04
CONTROL_RESET = 0x08
CONTROL_PAUSE = 0x10
CONTROL_CONTINUE = 0x20

LOAD_SUCCESS = 1
LOAD_FULL = 2
LOAD_ERROR = 3

OP_START = 1
OP_START_SOLO = 2
OP_STOP = 3
OP_START_OVERRIDE = 4

AXIS_ENABLE_X = 1
AXIS_ENABLE_Y = 2
AXIS_ENABLE_DIR = 4

FFB_GAIN_MASTER = 1
FFB_GAIN_PERIODIC = 2
FFB_GAIN_SPRING = 3
FFB_GAIN_DAMPER = 4
FFB_GAIN_INERTIA = 5
FFB_GAIN_FRICTION = 6
FFB_GAIN_CONSTANT = 7

effect_names = {
    0: "Invalid",
    1: "Constant",
    2: "Ramp",
    3: "Square",
    4: "Sine",
    5: "Triangle",
    6: "Sawtooth Up",
    7: "Sawtooth Down",
    8: "Spring",
    9: "Damper",
    10: "Inertia",
    11: "Friction",
    12: "Custom",
    13: "Detent",
    14: "SpringAdjuster",
}


def _scale_4096_to_255(value: int | float) -> int:
    return int(clamp(round(float(value) * 255 / 4096), 0, 255))


def _scale_percent_to_255(value: int | float) -> int:
    return int(clamp(round(float(value) * 255 / 100), 0, 255))


def _scale_cp_offset_to_u8(value: int | float) -> int:
    if isinstance(value, float):
        value = round(value * 4096)
    value = int(clamp(value, -32768, 32512))
    return int(clamp(round(value / 256 + 128), 0, 255))


class BaseStructure(ctypes.LittleEndianStructure):
    def __init__(self, **kwargs):
        values = type(self)._defaults_.copy()
        values.update(kwargs)
        super().__init__(**values)

    def __repr__(self):
        out = []
        for f in self._fields_:
            if f[0]:
                out.append(f"{f[0]}={getattr(self, f[0])}")
        return f"{self.__class__.__name__}(0x{id(self):X}): " + ",".join(out)


class FFBReport_SetEffect(BaseStructure):
    _pack_ = 1
    _fields_ = [
        ("reportId", ctypes.c_uint8),
        ("effectBlockIndex", ctypes.c_uint8),
        ("effectType", ctypes.c_uint8),
        ("duration", ctypes.c_uint16),
        ("triggerRepeatInterval", ctypes.c_uint16),
        ("samplePeriod", ctypes.c_uint16),
        ("startDelay", ctypes.c_uint16),
        ("gain", ctypes.c_uint8),
        ("triggerButton", ctypes.c_uint8),
        ("axesEnable", ctypes.c_uint8),
        ("directionX", ctypes.c_uint16),
        ("directionY", ctypes.c_uint16),
    ]
    _defaults_ = {"reportId": HID_REPORT_ID_SET_EFFECT, "gain": 255}

    def __init__(self, **kwargs):
        if "gain" in kwargs and kwargs["gain"] > 255:
            kwargs["gain"] = _scale_4096_to_255(kwargs["gain"])
        super().__init__(**kwargs)


class FFBReport_EffectOperation(BaseStructure):
    _pack_ = 1
    _fields_ = [
        ("reportId", ctypes.c_uint8),
        ("effectBlockIndex", ctypes.c_uint8),
        ("operation", ctypes.c_uint8),
        ("loopCount", ctypes.c_uint8),
    ]
    _defaults_ = {"reportId": HID_REPORT_ID_EFFECT_OPERATION}


class FFBReport_SetPeriodic(BaseStructure):
    _pack_ = 1
    _fields_ = [
        ("reportId", ctypes.c_uint8),
        ("effectBlockIndex", ctypes.c_uint8),
        ("magnitude", ctypes.c_int16),
        ("offset", ctypes.c_int16),
        ("phase", ctypes.c_uint16),
        ("period", ctypes.c_uint32),
    ]
    _defaults_ = {"reportId": HID_REPORT_ID_SET_PERIODIC}


class FFBReport_SetConstantForce(BaseStructure):
    _pack_ = 1
    _fields_ = [
        ("reportId", ctypes.c_uint8),
        ("effectBlockIndex", ctypes.c_uint8),
        ("magnitude", ctypes.c_int16),
    ]
    _defaults_ = {"reportId": HID_REPORT_ID_SET_CONSTANT_FORCE}


class FFBReport_SetCondition(BaseStructure):
    _pack_ = 1
    _fields_ = [
        ("reportId", ctypes.c_uint8),
        ("effectBlockIndex", ctypes.c_uint8),
        ("parameterBlockOffset", ctypes.c_uint8),
        ("cpOffsetRaw", ctypes.c_uint8),
        ("positiveCoefficient", ctypes.c_int16),
        ("negativeCoefficient", ctypes.c_int16),
        ("positiveSaturation", ctypes.c_uint16),
        ("negativeSaturation", ctypes.c_uint16),
        ("deadBand", ctypes.c_uint16),
    ]
    _defaults_ = {"reportId": HID_REPORT_ID_SET_CONDITION, "cpOffsetRaw": 128}

    def __init__(self, **kwargs):
        cp_offset = kwargs.pop("cpOffset", None)
        super().__init__(**kwargs)
        if cp_offset is not None:
            self.cpOffset = cp_offset

    @property
    def cpOffset(self) -> int:
        return int((self.cpOffsetRaw - 128) * 256)

    @cpOffset.setter
    def cpOffset(self, offset: int | float) -> None:
        self.cpOffsetRaw = _scale_cp_offset_to_u8(offset)

    def set_offset(self, offset: int | float) -> None:
        self.cpOffset = offset

    def set_saturation(self, saturation: int | float, do_clamp: bool = True) -> None:
        if isinstance(saturation, float):
            saturation = round(saturation * 4096)
        if do_clamp:
            saturation = clamp(saturation, 0, 4096)
        self.positiveSaturation = saturation
        self.negativeSaturation = saturation

    def set_coefficient(self, coefficient: int | float, do_clamp: bool = True) -> None:
        if isinstance(coefficient, float):
            coefficient = round(coefficient * 4096)
        if do_clamp:
            coefficient = clamp(coefficient, 0, 4096)
        self.positiveCoefficient = coefficient
        self.negativeCoefficient = coefficient

    def set_coefficients(self, positive, negative):
        self.positiveCoefficient = positive
        self.negativeCoefficient = negative


class FFBReport_SetEnvelope(BaseStructure):
    _pack_ = 1
    _fields_ = [
        ("reportId", ctypes.c_uint8),
        ("effectBlockIndex", ctypes.c_uint8),
        ("attackLevel", ctypes.c_uint16),
        ("fadeLevel", ctypes.c_uint16),
        ("attackTime", ctypes.c_uint32),
        ("fadeTime", ctypes.c_uint32),
    ]
    _defaults_ = {"reportId": HID_REPORT_ID_SET_ENVELOPE}


class FFBReport_BlockFree(BaseStructure):
    _pack_ = 1
    _fields_ = [
        ("reportId", ctypes.c_uint8),
        ("effectBlockIndex", ctypes.c_uint8),
    ]
    _defaults_ = {"reportId": HID_REPORT_ID_BLOCK_FREE}


class FFBReport_DeviceGain(BaseStructure):
    _pack_ = 1
    _fields_ = [
        ("reportId", ctypes.c_uint8),
        ("gain", ctypes.c_uint8),
    ]
    _defaults_ = {"reportId": HID_REPORT_ID_DEVICE_GAIN, "gain": 255}


class FFBReport_Input(BaseStructure):
    _pack_ = 1
    _fields_ = [
        ("reportId", ctypes.c_uint8),
        ("Button0_63", ctypes.c_uint64),
        ("hat", ctypes.c_uint8),
        ("padding", ctypes.c_uint8),
        ("X", ctypes.c_int16),
        ("Y", ctypes.c_int16),
        ("Z", ctypes.c_int16),
        ("Rx", ctypes.c_int16),
        ("Ry", ctypes.c_int16),
        ("Rz", ctypes.c_int16),
        ("Dial", ctypes.c_int16),
        ("Slider", ctypes.c_int16),
    ]
    _defaults_ = {}

    def _hat_position(self) -> int:
        return 0x0F if self.hat == 0 else (self.hat - 1) & 0x0F

    def isButtonPressed(self, button_number) -> bool:
        assert button_number > 0
        if self.buttons & (1 << (button_number - 1)):
            return True
        hat = self._hat_position()
        if hat != 0x0F:
            return button_number == (0x80 | hat)
        return False

    def getPressedButtons(self) -> List[int]:
        pressed = [i + 1 for i in range(64) if self.buttons & (1 << i)]
        hat = self._hat_position()
        if hat != 0x0F:
            pressed.append(0x80 | hat)
        return pressed

    @property
    def buttons(self) -> int:
        return self.Button0_63

    @property
    def hats(self) -> int:
        return self._hat_position()

    def axisXY(self) -> tuple[float, float]:
        return (self.X / 32767.0, self.Y / 32767.0)

    def CP_XY(self) -> tuple[float | None, float | None]:
        return (None, None)

    def forceXY(self) -> tuple[float, float]:
        return (0.0, 0.0)

    def CP_scaled_axisXY(self) -> tuple[float, float]:
        return self.axisXY()


class FFBReport_PIDStatus_Input(BaseStructure):
    _pack_ = 1
    _fields_ = [
        ("reportId", ctypes.c_uint8),
        ("devicePaused", ctypes.c_uint8, 1),
        ("actuatorsEnabled", ctypes.c_uint8, 1),
        ("safetySwitch", ctypes.c_uint8, 1),
        ("actuatorOverride", ctypes.c_uint8, 1),
        ("actuatorPower", ctypes.c_uint8, 1),
        ("deviceResetEvent", ctypes.c_uint8, 1),
        ("", ctypes.c_uint8, 2),
    ]
    _defaults_ = {}

    @property
    def effectPlaying(self) -> int:
        return 1

    @property
    def effectBlockIndex(self) -> int:
        return 0


class FFBReport_Get_Gains_Feature_Data(BaseStructure):
    _pack_ = 1
    _fields_ = [
        ("reportId", ctypes.c_uint8),
        ("master_gain", ctypes.c_uint8),
        ("periodic_gain", ctypes.c_uint8),
        ("spring_gain", ctypes.c_uint8),
        ("damper_gain", ctypes.c_uint8),
        ("inertia_gain", ctypes.c_uint8),
        ("friction_gain", ctypes.c_uint8),
        ("constant_gain", ctypes.c_uint8),
    ]
    _defaults_ = {
        "reportId": HID_REPORT_FEATURE_ID_GET_GAINS,
        "master_gain": 100,
        "periodic_gain": 100,
        "spring_gain": 100,
        "damper_gain": 100,
        "inertia_gain": 100,
        "friction_gain": 100,
        "constant_gain": 100,
    }


class FFBReport_Set_Gain_Feature_Data_t(BaseStructure):
    _pack_ = 1
    _fields_ = [
        ("reportId", ctypes.c_uint8),
        ("gain_id", ctypes.c_uint8),
        ("gain_value", ctypes.c_uint8),
    ]
    _defaults_ = {"reportId": HID_REPORT_FEATURE_ID_SET_GAIN}


input_report_handlers = {
    HID_REPORT_ID_INPUT: FFBReport_Input,
    HID_REPORT_ID_PID_STATE_REPORT: FFBReport_PIDStatus_Input,
}


class FFBEffectHandle:
    def __init__(self, device, effect_id, effect_type) -> None:
        self.ffb: FFBZfsb = device
        self.effect_id = effect_id
        self.type = effect_type
        self._finalizer = weakref.finalize(self, lambda ref: ref() and ref().destroy(), weakref.ref(self))
        self._cache = {}
        self._started = False
        self._override_started = False

    def invalidate(self):
        self.effect_id = 0

    def _data_changed(self, key, data) -> bool:
        h = hash(data)
        if not self._cache.get(key):
            self._cache[key] = h
            return True
        changed = self._cache[key] != h
        self._cache[key] = h
        return changed

    def __del__(self):
        self.destroy()

    def __bool__(self) -> bool:
        return bool(self.effect_id and self.type)

    @property
    def started(self):
        return self._started

    @property
    def override_started(self):
        return self._override_started

    @property
    def name(self):
        return effect_names.get(self.type)

    def __repr__(self):
        return f"FFBEffectHandle({self.effect_id}, {self.name})"

    def start(self, loopCount=1, override=False):
        op = OP_START_OVERRIDE if override else OP_START
        data = FFBReport_EffectOperation(effectBlockIndex=self.effect_id, operation=op, loopCount=loopCount)
        logging.info(
            "zFSB effect op report id=0x%02X effect=%s op=%s%s loops=%s bytes=%s",
            HID_REPORT_ID_EFFECT_OPERATION,
            self.effect_id,
            op,
            " OVERRIDE" if override else "",
            loopCount,
            bytes(data).hex(" "),
        )
        self.ffb.write(bytes(data))
        self._started = True
        self._override_started = override
        return self

    def stop(self):
        data = FFBReport_EffectOperation(effectBlockIndex=self.effect_id, operation=OP_STOP)
        self.ffb.write(bytes(data))
        self._started = False
        self._override_started = False
        return self

    def destroy(self):
        if self.effect_id:
            logging.debug(f"Destroying effect {self.effect_id} ({effect_names[self.type]})")
            data = FFBReport_BlockFree(effectBlockIndex=self.effect_id)
            self.ffb.write(bytes(data))
            self.type = 0
            self.effect_id = None
            self._started = False
            self._override_started = False

    def _openffb_effect_type(self) -> int:
        if self.type == EFFECT_DETENT:
            return EFFECT_SPRING
        return self.type

    def setConstantForce(self, magnitude, direction, **kwargs):
        if self.effect_id is None:
            logging.warning("setConstantForce on an invalidated effect")
            return
        assert self.type == EFFECT_CONSTANT
        assert -1.0 <= magnitude <= 1.0

        self.setEffect(axesEnable=AXIS_ENABLE_DIR, directionX=round(direction % 360 * 100))
        data = bytes(FFBReport_SetConstantForce(magnitude=round(4096 * magnitude), effectBlockIndex=self.effect_id))
        if self._data_changed("SetConstantForce", data):
            self.ffb.write(data)
        return self

    def setEffect(self, **kwargs):
        args = {
            "effectBlockIndex": self.effect_id,
            "effectType": self._openffb_effect_type(),
            "axesEnable": AXIS_ENABLE_X | AXIS_ENABLE_Y,
            "gain": 4096,
        }
        args.update(kwargs)
        allowed = {name for name, _type in FFBReport_SetEffect._fields_}
        args = {key: value for key, value in args.items() if key in allowed}
        data = bytes(FFBReport_SetEffect(**args))
        if self._data_changed("setEffect", data):
            self.ffb.write(data)

    def setCondition(self, cond: FFBReport_SetCondition):
        cond.effectBlockIndex = self.effect_id
        if self.type == EFFECT_SPRING_ADJUSTER:
            cond.positiveCoefficient = clamp(cond.positiveCoefficient, -32768, 32767)
            cond.negativeCoefficient = clamp(cond.negativeCoefficient, -32768, 32767)
        else:
            cond.positiveCoefficient = clamp(cond.positiveCoefficient, -4096, 4096)
            cond.negativeCoefficient = clamp(cond.negativeCoefficient, -4096, 4096)
        data = bytes(cond)
        if self._data_changed(f"setCondition{cond.parameterBlockOffset}", data):
            self.ffb.write(data)

    def setPeriodic(self, freq, magnitude, direction, duration=0, **kwargs):
        assert self.type in PERIODIC_EFFECTS
        assert 0 <= magnitude <= 1.0
        effect_kwargs = {key: value for key, value in kwargs.items() if key in {name for name, _type in FFBReport_SetEffect._fields_}}
        self.setEffect(axesEnable=AXIS_ENABLE_DIR, directionX=round(direction % 360 * 100), duration=duration, **effect_kwargs)

        period = 0 if freq == 0 else round(1000.0 / freq)
        periodic_kwargs = {key: value for key, value in kwargs.items() if key in {name for name, _type in FFBReport_SetPeriodic._fields_}}
        data = bytes(
            FFBReport_SetPeriodic(
                magnitude=round(4096 * magnitude),
                effectBlockIndex=self.effect_id,
                period=period,
                **periodic_kwargs,
            )
        )
        if self._data_changed("SetPeriodic", data):
            self.ffb.write(data)
        return self


@dataclass
class DeviceInfo:
    interface_number: int
    manufacturer_string: str
    path: bytes
    product_id: int
    product_string: str
    release_number: int
    serial_number: str
    usage: int
    usage_page: int
    vendor_id: int

    @property
    def ident(self) -> str:
        return (self.product_string or "zFSB").replace("zFSB ", "").strip()


class FFBZfsb(QObject):
    buttonPressed = pyqtSignal(int)
    buttonReleased = pyqtSignal(int)
    deviceConnected = pyqtSignal(bool)

    def __init__(self, vid=0x2E8A, pid=0xFFB2, serial=None, path=None) -> None:
        self.vid = vid
        self.pid = pid
        self.info: DeviceInfo = None
        self.firmware_version: str = None
        self._button_state: int = 0
        self._prev_hat = 0x0F
        self._gains = FFBReport_Get_Gains_Feature_Data()

        devs = FFBZfsb.enumerate(vid, pid)
        if serial:
            devs = list(filter(lambda x: x.serial_number == serial, devs))
        if path:
            path_bytes = path if isinstance(path, bytes) else path.encode("utf-8")
            devs = list(filter(lambda x: x.path == path_bytes, devs))
        if not devs:
            raise hid.HIDException("unable to open device")
        self.info = devs[0]

        self._in_reports = {}
        self._effect_handles: List[FFBEffectHandle] = []
        self._dev = None

        QObject.__init__(self)
        self.startTimer(1)
        self.reconnect()

    def reconnect(self):
        if self._dev:
            self._dev.close()
            self._dev = None
        self._dev = hid.Device(path=self.info.path)
        self._dev.nonblocking = True

    @property
    def serial(self):
        return self._dev.serial

    @property
    def product(self):
        return self._dev.product

    @property
    def manufacturer(self):
        return self._dev.manufacturer

    @staticmethod
    def enumerate(vid=0, pid=0) -> List[DeviceInfo]:
        devs = hid.enumerate(vid=vid, pid=pid)
        devs = [DeviceInfo(**dev) for dev in devs]
        joystick_devs = list(filter(lambda x: x.usage_page == 1 and x.usage == 4, devs))
        return joystick_devs or devs

    @staticmethod
    def enumerate_raw(vid=0, pid=0) -> List[DeviceInfo]:
        return [DeviceInfo(**dev) for dev in hid.enumerate(vid=vid, pid=pid)]

    def get_gains(self) -> FFBReport_Get_Gains_Feature_Data:
        return self._gains

    def set_gain(self, slider_id, value):
        assert 0 <= value <= 100
        names = {
            FFB_GAIN_MASTER: "master_gain",
            FFB_GAIN_PERIODIC: "periodic_gain",
            FFB_GAIN_SPRING: "spring_gain",
            FFB_GAIN_DAMPER: "damper_gain",
            FFB_GAIN_INERTIA: "inertia_gain",
            FFB_GAIN_FRICTION: "friction_gain",
            FFB_GAIN_CONSTANT: "constant_gain",
        }
        if slider_id in names:
            setattr(self._gains, names[slider_id], int(value))
        if slider_id == FFB_GAIN_MASTER:
            self.write(bytes(FFBReport_DeviceGain(gain=_scale_percent_to_255(value))))

    def set_deadzone(self, deadzone: int):
        assert 0 <= deadzone <= 4096
        logging.debug("zFSB/OpenFFB backend ignoring VPForce-only deadzone report")

    @overrides(QObject)
    def timerEvent(self, a0: QTimerEvent) -> None:
        try:
            self.read_reports()
        except Exception:
            logging.exception("Exception")
            self._dev.close()
            self._dev = None

            logging.warning("Reconnecting HID device in 1s")

            def do_reconnect():
                try:
                    self.reconnect()
                    logging.info("HID connected!")
                    self.deviceConnected.emit(True)
                except Exception:
                    self.deviceConnected.emit(False)
                    logging.warning("Reconnecting HID device in 1s")
                    QTimer.singleShot(1000, do_reconnect)

            QTimer.singleShot(1000, do_reconnect)

    def _process_hat(self, hat):
        if hat == self._prev_hat:
            return
        if self._prev_hat != 0x0F:
            self.buttonReleased.emit(0x80 | self._prev_hat)
        if hat != 0x0F:
            self.buttonPressed.emit(0x80 | hat)
        self._prev_hat = hat

    def on_hid_report_received(self, report_id):
        if report_id == HID_REPORT_ID_INPUT:
            report: FFBReport_Input = self.get_input()
            if not report:
                return
            btns: int = report.buttons
            prev = self._button_state
            self._button_state = btns

            diff = btns ^ prev
            i = 0
            while diff:
                if diff & 1:
                    if (~prev & btns) & 1:
                        self.buttonPressed.emit(i)
                    if (prev & ~btns) & 1:
                        self.buttonReleased.emit(i)
                i += 1
                diff >>= 1
                btns >>= 1
                prev >>= 1
            self._process_hat(report.hats)

        elif report_id == HID_REPORT_ID_PID_STATE_REPORT:
            report = self.get_report(HID_REPORT_ID_PID_STATE_REPORT)
            if report and report.deviceResetEvent:
                logging.info("Device FFB reset event: Invalidating all effects")
                for ref in self._effect_handles:
                    effect: FFBEffectHandle = ref()
                    if effect:
                        effect.invalidate()

    def get_firmware_version(self, cached=True):
        if self.firmware_version and cached:
            return self.firmware_version
        self.firmware_version = "v1.0.18-zFSB"
        return self.firmware_version

    def reset_effects(self):
        logging.info("FFB: Reset device effects")
        self._dev.write(bytes([HID_REPORT_ID_DEVICE_CONTROL, CONTROL_RESET]))
        time.sleep(0.01)

    def create_effect(self, type) -> FFBEffectHandle:
        openffb_type = EFFECT_SPRING if type == EFFECT_DETENT else type
        logging.info("zFSB create effect type=%s device_type=0x%02X", effect_names.get(type, type), openffb_type)
        self._dev.send_feature_report(bytes([HID_REPORT_ID_CREATE_EFFECT, openffb_type, 0, 0]))
        r = bytearray(self._dev.get_feature_report(HID_REPORT_ID_PID_BLOCK_LOAD, 5))

        assert r[0] == HID_REPORT_ID_PID_BLOCK_LOAD
        effect_id = r[1]
        status = r[2]

        if status != LOAD_SUCCESS:
            logging.warning("Effects pool full, cannot create new effect")
            return None

        handle = FFBEffectHandle(self, effect_id, type)
        self._effect_handles.append(weakref.ref(handle, lambda x: self._effect_handles.remove(x)))
        return handle

    def write(self, data):
        if self._dev.write(data) < 0:
            raise IOError("HID Write")

    def read_reports(self):
        if not self._dev:
            return
        while True:
            tmp = self._dev.read(64)
            if tmp:
                report_id = tmp[0]
                self._in_reports[report_id] = tmp
                self.on_hid_report_received(report_id)
            else:
                break

    def get_report(self, report_id):
        data = self._in_reports.get(report_id, None)
        if data:
            try:
                return input_report_handlers[report_id].from_buffer_copy(data)
            except KeyError as err:
                logging.exception(f"ERROR GETTING HID REPORT: {err}")
                return data
        return data

    def get_input(self) -> FFBReport_Input:
        return self.get_report(HID_REPORT_ID_INPUT)


class HapticEffect(Destroyable):
    device: FFBZfsb = None

    def __init__(self):
        self.name = None
        self._stopped_time: int = 0
        self._h_effect: FFBEffectHandle = None
        self.modulator = None
        self.effect_type = None
        self._conds = {}

    def __repr__(self):
        return f"HapticEffect({self._h_effect})"

    @property
    def id(self):
        return self._h_effect.effect_id if self._h_effect else None

    @classmethod
    def open(cls, vid=0x2E8A, pid=0xFFB2, serial=None, path=None) -> FFBZfsb:
        logging.info(f"Open zFSB/OpenFFB HID {vid:04X}:{pid:04X}")
        cls.device = FFBZfsb(vid, pid, serial, path)
        logging.info(f"Successfully opened HID '{cls.device.info.path.decode('utf-8')}'")
        return cls.device

    def setCondition(self, cond: FFBReport_SetCondition) -> Self:
        assert self.effect_type in [
            EFFECT_SPRING,
            EFFECT_DAMPER,
            EFFECT_INERTIA,
            EFFECT_FRICTION,
            EFFECT_SPRING_ADJUSTER,
        ]
        if not self._h_effect:
            self._conditional_effect(self.effect_type)
        self._h_effect.setCondition(cond)
        return self

    def _conditional_effect(self, effect_type, coef_x=None, coef_y=None) -> Self:
        if not self._h_effect:
            self._h_effect = self.device.create_effect(effect_type)
            self.effect_type = effect_type
            if not self._h_effect:
                return self
            self._h_effect.setEffect()

        if coef_x is not None:
            cond_x = FFBReport_SetCondition(
                parameterBlockOffset=0,
                positiveCoefficient=int(coef_x),
                negativeCoefficient=int(coef_x),
            )
            self._h_effect.setCondition(cond_x)

        if coef_y is not None:
            cond_y = FFBReport_SetCondition(
                parameterBlockOffset=1,
                positiveCoefficient=int(coef_y),
                negativeCoefficient=int(coef_y),
            )
            self._h_effect.setCondition(cond_y)
        return self

    def inertia(self, coef_x=None, coef_y=None):
        return self._conditional_effect(EFFECT_INERTIA, coef_x, coef_y)

    def damper(self, coef_x=None, coef_y=None):
        return self._conditional_effect(EFFECT_DAMPER, coef_x, coef_y)

    def friction(self, coef_x=None, coef_y=None):
        return self._conditional_effect(EFFECT_FRICTION, coef_x, coef_y)

    def spring(self, coef_x=None, coef_y=None):
        return self._conditional_effect(EFFECT_SPRING, coef_x, coef_y)

    def spring_adjuster(self, coef_x=4096, coef_y=4096):
        return self._conditional_effect(EFFECT_SPRING_ADJUSTER, coef_x, coef_y)

    def periodic(self, frequency, magnitude: float, direction: float, *args, effect_type=EFFECT_SINE, duration=0, **kwargs):
        if not self._h_effect:
            self._h_effect = self.device.create_effect(effect_type)
            self.effect_type = effect_type
            if not self._h_effect:
                return self

        if isinstance(direction, type) and issubclass(direction, DirectionModulator):
            if not self.modulator:
                self.modulator = direction(*args, **kwargs)
            direction = self.modulator.update()

        self._h_effect.setPeriodic(frequency, magnitude, direction, duration=duration, **kwargs)
        return self

    def constant(self, magnitude: float, direction: float, *args, **kwargs):
        if not self._h_effect:
            self._h_effect = self.device.create_effect(EFFECT_CONSTANT)
            self.effect_type = EFFECT_CONSTANT
            if not self._h_effect:
                return self

        if isinstance(direction, type) and issubclass(direction, DirectionModulator):
            if not self.modulator:
                self.modulator = direction(*args, **kwargs)
            direction = self.modulator.update()

        self._h_effect.setConstantForce(magnitude, direction, **kwargs)
        return self

    @property
    def started(self) -> bool:
        return self._h_effect and self._h_effect.started

    def start(self, force=False, **kw):
        override = bool(kw.get("override"))
        if self._h_effect and (not self.started or force or override):
            caller_frame = inspect.currentframe().f_back
            caller_name = caller_frame.f_code.co_name
            logging.debug(f"The function {caller_name} is starting effect {self._h_effect.effect_id}")
            name = f" (\"{self.name}\")" if self.name else ""
            logging.info(f"Start effect {self._h_effect.effect_id} ({self._h_effect.name}){name}")
            self._h_effect.start(**kw)
            self._stopped_time = 0
        return self

    def stop(self, destroy_after: int = 10000):
        if self._h_effect and self._h_effect.started:
            caller_frame = inspect.currentframe().f_back
            caller_name = caller_frame.f_code.co_name
            logging.debug(f"The function {caller_name} is stopping effect {self._h_effect.effect_id}")
            name = f" (\"{self.name}\")" if self.name else ""
            logging.info(f"Stop effect {self._h_effect.effect_id} ({self._h_effect.name}){name}")
            self._h_effect.stop()
            if destroy_after and not self._stopped_time:
                self._stopped_time = millis()

        if self._stopped_time and destroy_after and millis() - self._stopped_time > destroy_after:
            self._stopped_time = 0
            self.destroy()
        return self

    def destroy(self):
        if self._h_effect:
            caller_frame = inspect.currentframe().f_back
            caller_name = caller_frame.f_code.co_name
            logging.debug(f"The function {caller_name} is destroying effect {self._h_effect.effect_id}")
            name = f" (\"{self.name}\")" if self.name else ""
            logging.info(f"Destroying effect {self._h_effect.effect_id} ({self._h_effect.name}){name}")
            self._h_effect.destroy()
            self._h_effect = None

    def __del__(self):
        self.destroy()


FFBRhino = FFBZfsb
