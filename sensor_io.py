"""Independent hardware I/O; capture, retention and projection own no drivers."""

import importlib
from pathlib import Path

import bme280
import smbus2
import st7735
from adafruit_extended_bus import ExtendedI2C
from adafruit_tmp117 import TMP117
from enviroplus import gas
from ltr559 import LTR559
from pms5003 import PMS5003, ChecksumMismatchError, ReadTimeoutError, SerialTimeoutError
from sensirion_driver_adapters.i2c_adapter.i2c_channel import I2cChannel
from sensirion_i2c_driver import CrcCalculator, I2cConnection, LinuxI2cTransceiver
from sensirion_i2c_scd4x.device import Scd4xDevice


class SensorIO:
    def __init__(self, hardware, i2c_bus, pms_device, cpu_temp_path, log):
        self.hardware = hardware
        self.i2c_bus = i2c_bus
        self.pms_device = pms_device
        self.cpu_temp_path = cpu_temp_path
        self.log = log
        self.devices = {}
        self.pms = None
        self.pms_restart = False
        self.proximity_error = None
        self.gas_ready = False
        self.bus = smbus2.SMBus()
        self.scd_connection = None

    def _bus(self):
        if self.bus.fd is None:
            try:
                self.bus.open(self.i2c_bus)
            except OSError:
                self.bus.close()
                raise
        return self.bus

    def _device(self, key, create):
        if key not in self.devices:
            self.devices[key] = create()
        return self.devices[key]

    def _observe(
        self, sample, key, read, errors=(OSError, RuntimeError, SystemExit), error_key=None
    ):
        try:
            value = read()
            if value is not None:
                sample[key] = value
        except errors as error:
            self.devices.pop(key, None)
            sample[error_key or key + "_error"] = repr(error)
            self.log.warning("%s acquisition failed: %s", key, error)

    def read(self, read_utc):
        sample = {"read_utc": read_utc}
        self._observe(sample, "bme280", self._bme)
        self._observe(sample, "tmp119", self._tmp, (OSError, ValueError, AttributeError))
        self._observe(sample, "cpu_temp_milli_c", lambda: int(Path(self.cpu_temp_path).read_text()))
        self._observe(sample, "ltr559_lux", lambda: self._ltr().get_lux())
        self._observe(
            sample, "mics6814_ohms", self._gas, (OSError, RuntimeError, SystemExit, AttributeError)
        )
        self._observe(sample, "pi", self._pi)
        self._observe(
            sample,
            "pms5003_frame_hex",
            self._pms,
            (
                OSError,
                RuntimeError,
                SystemExit,
                ReadTimeoutError,
                SerialTimeoutError,
                ChecksumMismatchError,
            ),
            error_key="pms5003_error",
        )
        self._observe(sample, "scd41", lambda: self._scd(sample))
        if self.proximity_error is not None:
            sample["ltr559_proximity_error"] = self.proximity_error
            self.proximity_error = None
        return sample

    def _bme(self):
        sensor = self._device(
            "bme280",
            lambda: bme280.BME280(i2c_addr=self.hardware["bme280_addr"], i2c_dev=self._bus()),
        )
        sensor.update_sensor()
        return [
            {
                "temperature": sensor.temperature,
                "humidity": sensor.humidity,
                "pressure": sensor.pressure,
            }
        ]

    def _tmp(self):
        sensor = self._device(
            "tmp119",
            lambda: TMP117(ExtendedI2C(self.i2c_bus), address=self.hardware["tmp119_addr"]),
        )
        return {"temperature_c": sensor.temperature}

    def _ltr(self):
        return self._device("ltr559_lux", lambda: LTR559(i2c_dev=self._bus()))

    def proximity(self):
        try:
            return self._ltr().get_proximity()
        except (OSError, RuntimeError) as error:
            self.devices.pop("ltr559_lux", None)
            self.proximity_error = repr(error)
            self.log.warning("LTR559 proximity failed: %s", error)
            return None

    def _gas(self):
        if not self.gas_ready:
            try:
                gas.setup()
                if not gas.available():
                    raise RuntimeError("Gas sensor not connected.")
            except (OSError, RuntimeError, SystemExit):
                # The driver latches setup/availability before configuration
                # completes. Reset only incomplete setup; retain an established
                # heater/GPIO handle through transient measurement failures.
                gas.cleanup()
                if hasattr(gas, "adc"):
                    # This driver has no ADC close API. Each Device owns its
                    # own SMBus; close both before discarding incomplete setup.
                    gas.adc._ads1015._i2c.close()
                    gas.adc._ads1115._i2c.close()
                importlib.reload(gas)
                raise
            self.gas_ready = True
        value = gas.read_all()
        return {"oxidising": value.oxidising, "reducing": value.reducing, "nh3": value.nh3}

    @staticmethod
    def _pi():
        load = float(Path("/proc/loadavg").read_text().split()[0])
        mem = next(
            int(line.split()[1])
            for line in Path("/proc/meminfo").read_text().splitlines()
            if line.startswith("MemAvailable")
        )
        uptime = float(Path("/proc/uptime").read_text().split()[0])
        return {"loadavg_1m": load, "mem_available_kb": mem, "uptime_s": uptime}

    def _pms(self):
        if self.pms is None:
            self.pms = PMS5003(device=self.pms_device)
        try:
            if self.pms_restart:
                self.pms.setup()  # Preserve claimed GPIO lines; reopen serial.
                self.pms_restart = False
            return bytes(self.pms.read().raw_data).hex()
        except (OSError, RuntimeError, ReadTimeoutError, SerialTimeoutError, ChecksumMismatchError):
            self.pms_restart = True
            raise

    def _scd(self, sample):
        def create():
            if self.scd_connection is None:
                self.scd_connection = I2cConnection(LinuxI2cTransceiver(f"/dev/i2c-{self.i2c_bus}"))
            # SCD41 fixed address and datasheet CRC-8; driver owns command timing.
            sensor = Scd4xDevice(
                I2cChannel(
                    self.scd_connection,
                    slave_address=0x62,
                    crc=CrcCalculator(8, 0x31, 0xFF, 0x0),
                )
            )
            sensor.stop_periodic_measurement()
            sensor.start_periodic_measurement()
            return sensor

        sensor = self._device("scd41", create)
        if sensor.get_data_ready_status():
            if "bme280" in sample:
                sensor.set_ambient_pressure(sample["bme280"][-1]["pressure"] * 100)
            co2, temperature, rh = sensor.read_measurement()
            return {"co2_ppm": co2.value, "temperature_c": temperature.value, "rh": rh.value}
        return None

    def display(self, image):
        def create():
            hw = self.hardware
            display = st7735.ST7735(
                port=hw["spi_port"],
                cs=hw["spi_cs"],
                dc=hw["display_dc"],
                backlight=hw["display_backlight"],
                rotation=hw["display_rotation"],
                spi_speed_hz=hw["spi_speed_hz"],
            )
            display.begin()
            return display

        try:
            self._device("display", create).display(image)
        except (OSError, RuntimeError, SystemExit) as error:
            self.devices.pop("display", None)
            self.log.warning("Display failed; capture continues: %s", error)
