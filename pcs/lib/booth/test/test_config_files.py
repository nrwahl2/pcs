from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from os.path import join
from unittest import TestCase

from pcs.common import report_codes
from pcs.lib.booth import config_files
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.settings import booth_config_dir as BOOTH_CONFIG_DIR
from pcs.test.tools.assertions import assert_raise_library_error, assert_report_item_list_equal
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.pcs_mock import mock


@mock.patch("os.listdir")
class GetAllConfigsTest(TestCase):
    def test_success(self, mock_listdir):
        mock_listdir.return_value = [
            "name1", "name2.conf", "name.conf.conf", ".conf", "name3.conf"
        ]
        self.assertEqual(
            ["name2.conf", "name.conf.conf", ".conf", "name3.conf"],
            config_files.get_all_configs()
        )
        mock_listdir.assert_called_once_with(BOOTH_CONFIG_DIR)


class ReadConfigTest(TestCase):
    def test_success(self):
        self.maxDiff = None
        mock_open = mock.mock_open(read_data="config content")
        with mock.patch(
            "pcs.lib.booth.config_files.open", mock_open, create=True
        ):
            self.assertEqual(
                "config content",
                config_files._read_config("my-file.conf")
            )

        self.assertEqual(
            [
                mock.call(join(BOOTH_CONFIG_DIR, "my-file.conf"), "r"),
                mock.call().__enter__(),
                mock.call().read(),
                mock.call().__exit__(None, None, None)
            ],
            mock_open.mock_calls
        )


@mock.patch("pcs.lib.booth.config_files._read_config")
@mock.patch("pcs.lib.booth.config_files.get_all_configs")
class ReadConfigsTest(TestCase):
    def setUp(self):
        self.mock_reporter = MockLibraryReportProcessor()

    def test_success(self, mock_get_configs, mock_read):
        def _mock_read_cfg(file):
            if file == "name1.conf":
                return "config1"
            elif file == "name2.conf":
                return "config2"
            elif file == "name3.conf":
                return "config3"
            else:
                raise AssertionError("unexpected input: {0}".format(file))
        mock_get_configs.return_value = [
            "name1.conf", "name2.conf", "name3.conf"
        ]
        mock_read.side_effect = _mock_read_cfg

        self.assertEqual(
            {
                "name1.conf": "config1",
                "name2.conf": "config2",
                "name3.conf": "config3"
            },
            config_files.read_configs(self.mock_reporter)
        )

        mock_get_configs.assert_called_once_with()
        self.assertEqual(3, mock_read.call_count)
        mock_read.assert_has_calls([
            mock.call("name1.conf"),
            mock.call("name2.conf"),
            mock.call("name3.conf")
        ])
        self.assertEqual(0, len(self.mock_reporter.report_item_list))

    def test_skip_failed(self, mock_get_configs, mock_read):
        def _mock_read_cfg(file):
            if file in ["name1.conf", "name3.conf"]:
                raise EnvironmentError()
            elif file == "name2.conf":
                return "config2"
            else:
                raise AssertionError("unexpected input: {0}".format(file))

        mock_get_configs.return_value = [
            "name1.conf", "name2.conf", "name3.conf"
        ]
        mock_read.side_effect = _mock_read_cfg

        self.assertEqual(
            {"name2.conf": "config2"},
            config_files.read_configs(self.mock_reporter, True)
        )
        mock_get_configs.assert_called_once_with()
        self.assertEqual(3, mock_read.call_count)
        mock_read.assert_has_calls([
            mock.call("name1.conf"),
            mock.call("name2.conf"),
            mock.call("name3.conf")
        ])
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severities.WARNING,
                    report_codes.BOOTH_CONFIG_READ_ERROR,
                    {"name": "name1.conf"}
                ),
                (
                    severities.WARNING,
                    report_codes.BOOTH_CONFIG_READ_ERROR,
                    {"name": "name3.conf"}
                )
            ]
        )

    def test_do_not_skip_failed(self, mock_get_configs, mock_read):
        def _mock_read_cfg(file):
            if file in ["name1.conf", "name3.conf"]:
                raise EnvironmentError()
            elif file == "name2.conf":
                return "config2"
            else:
                raise AssertionError("unexpected input: {0}".format(file))

        mock_get_configs.return_value = [
            "name1.conf", "name2.conf", "name3.conf"
        ]
        mock_read.side_effect = _mock_read_cfg

        assert_raise_library_error(
            lambda: config_files.read_configs(self.mock_reporter),
            (
                severities.ERROR,
                report_codes.BOOTH_CONFIG_READ_ERROR,
                {"name": "name1.conf"},
                report_codes.SKIP_UNREADABLE_CONFIG
            ),
            (
                severities.ERROR,
                report_codes.BOOTH_CONFIG_READ_ERROR,
                {"name": "name3.conf"},
                report_codes.SKIP_UNREADABLE_CONFIG
            )
        )
        mock_get_configs.assert_called_once_with()
        self.assertEqual(3, mock_read.call_count)
        mock_read.assert_has_calls([
            mock.call("name1.conf"),
            mock.call("name2.conf"),
            mock.call("name3.conf")
        ])
        self.assertEqual(2, len(self.mock_reporter.report_item_list))


@mock.patch("pcs.lib.booth.config_structure.get_authfile")
@mock.patch("pcs.lib.booth.config_parser.parse")
@mock.patch("pcs.lib.booth.config_files.read_authfile")
class ReadAuthFileFromConfigsTest(TestCase):
    def setUp(self):
        self.mock_reporter = MockLibraryReportProcessor()

    def test_success(self, mock_read, mock_parse, mock_get_authfile):
        def _mock_read(_, path):
            if path == "/etc/booth/k1.key":
                return "key1"
            elif path == "/etc/booth/k2.key":
                return "key2"
            else:
                raise AssertionError("unexpected input: {0}".format(path))

        configs = {
            "config1.conf": "config1",
            "config2.conf": "config2",
            "config3.conf": "config3"
        }

        config_authfile_map = {
            "config1": "/etc/booth/k1.key",
            "config2": "/etc/booth/k2.key",
            "config3": None,
        }
        def _mock_get_authfile(config):
            if config in config_authfile_map:
                return config_authfile_map[config]
            raise AssertionError("unexpected input: {0}".format(config))

        mock_read.side_effect = _mock_read
        mock_parse.side_effect = lambda config: config
        mock_get_authfile.side_effect = _mock_get_authfile

        self.assertEqual(
            {
                "k1.key": "key1",
                "k2.key": "key2"
            },
            config_files.read_authfiles_from_configs(
                self.mock_reporter, configs.values()
            )
        )
        self.assertEqual(3, mock_parse.call_count)
        mock_parse.has_calls([
            mock.call(configs["config1.conf"]),
            mock.call(configs["config2.conf"]),
            mock.call(configs["config3.conf"]),
        ])
        self.assertEqual(2, mock_read.call_count)
        mock_read.has_calls([
            mock.call(self.mock_reporter, "/etc/booth/k1.key"),
            mock.call(self.mock_reporter, "/etc/booth/k2.key")
        ])


class ReadAuthfileTest(TestCase):
    def setUp(self):
        self.mock_reporter = MockLibraryReportProcessor()
        self.maxDiff = None

    def test_success(self):
        path = join(BOOTH_CONFIG_DIR, "file.key")
        mock_open = mock.mock_open(read_data="key")

        with mock.patch(
            "pcs.lib.booth.config_files.open", mock_open, create=True
        ):
            self.assertEqual(
                "key", config_files.read_authfile(self.mock_reporter, path)
            )

        self.assertEqual(
            [
                mock.call(path, "rb"),
                mock.call().__enter__(),
                mock.call().read(),
                mock.call().__exit__(None, None, None)
            ],
            mock_open.mock_calls
        )
        self.assertEqual(0, len(self.mock_reporter.report_item_list))

    def test_path_none(self):
        self.assertTrue(
            config_files.read_authfile(self.mock_reporter, None) is None
        )
        self.assertEqual(0, len(self.mock_reporter.report_item_list))

    def test_invalid_path(self):
        path = "/not/etc/booth/booth.key"
        self.assertTrue(
            config_files.read_authfile(self.mock_reporter, path) is None
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [(
                severities.WARNING,
                report_codes.BOOTH_UNSUPORTED_FILE_LOCATION,
                {"file": path}
            )]
        )

    def test_not_abs_path(self):
        path = "/etc/booth/../booth.key"
        self.assertTrue(
            config_files.read_authfile(self.mock_reporter, path) is None
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [(
                severities.WARNING,
                report_codes.BOOTH_UNSUPORTED_FILE_LOCATION,
                {"file": path}
            )]
        )

    def test_read_failure(self):
        path = join(BOOTH_CONFIG_DIR, "file.key")
        mock_open = mock.mock_open()
        mock_open().read.side_effect = EnvironmentError("reason")

        with mock.patch(
            "pcs.lib.booth.config_files.open", mock_open, create=True
        ):
            return_value = config_files.read_authfile(self.mock_reporter, path)

        self.assertTrue(return_value is None)

        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [(
                severities.WARNING,
                report_codes.FILE_IO_ERROR,
                {
                    "file_role": "authfile",
                    "file_path": path,
                    "reason": "reason",
                }
            )]
        )
