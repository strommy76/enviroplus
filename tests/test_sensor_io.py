"""Resource lifetime under actual installed I2C drivers and persistent I/O failure."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("lane", ["bme280", "ltr559_lux", "mics6814_ohms", "scd41"])
def test_failed_sensor_initialization_keeps_file_descriptors_bounded(tmp_path, lane):
    device = tmp_path / "i2c-device"
    device.touch()
    code = """
import logging, os, sys
from unittest.mock import patch
import smbus2
from sensor_io import SensorIO

real_open = os.open
def open_device(path, *args, **kwargs):
    if isinstance(path, str) and path.startswith('/dev/i2c-'):
        path = sys.argv[1]
    return real_open(path, *args, **kwargs)

log = logging.getLogger('sensor-fd-check')
log.addHandler(logging.NullHandler())
log.propagate = False
with patch('os.open', open_device), patch.object(
    smbus2.SMBus, '_get_funcs', lambda self: smbus2.I2cFunc.I2C
):
    # A controller can open successfully while a sensor fails I/O. Only that
    # external controller-capability response is substituted; actual driver
    # allocation, native fds, errors, ownership and close() remain real.
    io = SensorIO({'bme280_addr': 0x76}, 1, '/unused', '/unused', log)
    read = {
        'bme280': io._bme,
        'ltr559_lux': lambda: io._ltr().get_lux(),
        'mics6814_ohms': io._gas,
        'scd41': lambda: io._scd({}),
    }[sys.argv[2]]
    sample = {}
    io._observe(sample, sys.argv[2], read)
    before = len(os.listdir('/proc/self/fd'))
    for _ in range(200):
        io._observe(sample, sys.argv[2], read)
    after = len(os.listdir('/proc/self/fd'))
    assert sys.argv[2] + '_error' in sample
    assert after == before, (before, after, sample)
"""
    subprocess.run(
        [sys.executable, "-c", code, str(device), lane],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )
