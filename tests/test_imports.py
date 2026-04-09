"""Verify shared library imports work from enviroplus scripts."""


def test_import_config_service():
    from shared.config_service import load_env, require, get, ConfigError
    assert callable(load_env)
    assert callable(require)
    assert callable(get)


def test_import_db_service():
    from shared.db_service import connect, write_row
    assert callable(connect)
    assert callable(write_row)


def test_import_logging_service():
    from shared.logging_service import setup_logger
    assert callable(setup_logger)


def test_import_signal_handler():
    from shared.signal_handler import install_shutdown_handler
    assert callable(install_shutdown_handler)


def test_import_utils():
    from shared.utils import utc_now, _f
    assert callable(utc_now)
    assert callable(_f)
