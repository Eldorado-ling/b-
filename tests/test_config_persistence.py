"""Regression tests for the configuration persistence of ``main_ed.py``.

The real ``main_ed.py`` module is loaded with small dependency stubs
(customtkinter, tkinter dialogs, PIL and requests) so that no GUI toolkit,
no image library and no network session is required.  Every test only uses
invented cookie strings and files inside a :class:`tempfile.TemporaryDirectory`.

Run with::

    python -X utf8 -m unittest discover -s tests -v
"""

import _io
import contextlib
import importlib.util
import io
import json
import os
import socket
import sys
import tempfile
import types
import unittest
from contextlib import contextmanager
from unittest import mock

MAIN_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main_ed.py"
)


# --------------------------------------------------------------------------- #
# Dependency stubs                                                            #
# --------------------------------------------------------------------------- #

class _StubTk(object):
    """Stand-in for ``customtkinter.CTk``; it is never shown as a window."""

    def __init__(self, *args, **kwargs):
        pass


class _StubVar(object):
    """Stand-in for the appearance-mode variable of the settings page."""

    def __init__(self, value=""):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


class _StubTextbox(object):
    """Stand-in for the cookie text box of the cookie page."""

    def __init__(self, text=""):
        self.text = text

    def get(self, start=None, end=None):
        return self.text

    def insert(self, index, text):
        self.text += text

    def delete(self, start=None, end=None):
        self.text = ""


class _StubMessageBox(object):
    """Records every dialog the application shows."""

    def __init__(self):
        self.calls = []

    def _record(self, kind, title, message):
        self.calls.append({"kind": kind, "title": title, "message": message})

    def showinfo(self, title, message=None, **kwargs):
        self._record("showinfo", title, message)

    def showwarning(self, title, message=None, **kwargs):
        self._record("showwarning", title, message)

    def showerror(self, title, message=None, **kwargs):
        self._record("showerror", title, message)

    def askyesno(self, title, message=None, **kwargs):
        self._record("askyesno", title, message)
        return False

    def of_kind(self, kind):
        return [call for call in self.calls if call["kind"] == kind]

    def reset(self):
        self.calls = []


class _ForbiddenSession(object):
    """Any attempt to reach the network fails loudly."""

    def _forbidden(self, *args, **kwargs):
        raise AssertionError("network access is not allowed in the test suite")

    get = _forbidden
    post = _forbidden
    put = _forbidden
    delete = _forbidden
    head = _forbidden
    request = _forbidden


class _StubRequestException(Exception):
    pass


class _StubTimeout(_StubRequestException):
    pass


class _Unserializable(object):
    """A value that JSON cannot encode."""


def _build_stub_modules():
    ctk = types.ModuleType("customtkinter")
    ctk.CTk = _StubTk
    ctk.appearance_calls = []
    ctk.set_appearance_mode = lambda mode: ctk.appearance_calls.append(mode)
    ctk.set_default_color_theme = lambda theme: None

    tkinter = types.ModuleType("tkinter")
    tkinter.filedialog = types.SimpleNamespace(
        asksaveasfilename=lambda **kwargs: "",
        askopenfilename=lambda **kwargs: "",
    )
    tkinter.messagebox = _StubMessageBox()

    pil = types.ModuleType("PIL")
    pil.Image = types.SimpleNamespace()
    pil.ImageTk = types.SimpleNamespace()

    requests = types.ModuleType("requests")
    requests.session = lambda: _ForbiddenSession()
    requests.get = _ForbiddenSession()._forbidden
    requests.post = _ForbiddenSession()._forbidden
    requests.exceptions = types.SimpleNamespace(
        RequestException=_StubRequestException,
        Timeout=_StubTimeout,
        ConnectionError=_StubRequestException,
        HTTPError=_StubRequestException,
    )

    return {
        "customtkinter": ctk,
        "tkinter": tkinter,
        "PIL": pil,
        "requests": requests,
    }


def _load_main_module():
    """Import the real ``main_ed.py`` with the dependency stubs in place."""
    stubs = _build_stub_modules()
    previous = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)
    try:
        spec = importlib.util.spec_from_file_location("main_ed_under_test", MAIN_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules["main_ed_under_test"] = module
        spec.loader.exec_module(module)
    finally:
        for name, original in previous.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original
        sys.modules.pop("main_ed_under_test", None)
    return module


MAIN = _load_main_module()


# --------------------------------------------------------------------------- #
# Network guard (restored after the suite)                                     #
# --------------------------------------------------------------------------- #

_NETWORK_GUARDS = []


def _network_forbidden(*args, **kwargs):
    raise AssertionError("network access is not allowed in the test suite")


def setUpModule():
    _NETWORK_GUARDS.extend([
        mock.patch.object(socket.socket, "connect", _network_forbidden),
        mock.patch.object(socket, "create_connection", _network_forbidden),
    ])
    for guard in _NETWORK_GUARDS:
        guard.start()


def tearDownModule():
    for guard in reversed(_NETWORK_GUARDS):
        guard.stop()
    _NETWORK_GUARDS.clear()


# --------------------------------------------------------------------------- #
# Failure injection helpers                                                   #
# --------------------------------------------------------------------------- #

@contextmanager
def _inject_write_failure():
    """The temporary file cannot be created or opened."""

    def failing_open(*args, **kwargs):
        raise OSError("injected write failure")

    with mock.patch.object(os, "open", side_effect=OSError("injected write failure")), \
            mock.patch.object(io, "open", failing_open), \
            mock.patch.object(_io, "open", failing_open):
        yield


_MID_WRITE_LOG = []


class _PartialWriter(object):
    """File proxy that lets only half of the first write reach the real file.

    ``tempfile`` may hand the wrapped methods to callers as bound copies,
    therefore every method tolerates a leading copy of this proxy.
    """

    def __init__(self, wrapped):
        self._wrapped = wrapped
        self._failed = False

    def _without_self(self, args):
        if args and args[0] is self:
            return args[1:]
        return args

    def write(self, *args):
        args = self._without_self(args)
        if self._failed:
            raise OSError("injected mid-write failure")
        self._failed = True
        data = args[0] if args else ""
        chunk = data[:max(1, len(data) // 2)]
        self._wrapped.write(chunk)
        self._wrapped.flush()
        _MID_WRITE_LOG.append(len(chunk))
        raise OSError("injected mid-write failure")

    def flush(self, *args):
        self._without_self(args)
        self._wrapped.flush()

    def fileno(self, *args):
        self._without_self(args)
        return self._wrapped.fileno()

    def close(self, *args):
        self._without_self(args)
        self._wrapped.close()

    def __getattr__(self, name):
        return getattr(self._wrapped, name)


@contextmanager
def _inject_mid_write_failure():
    """The temporary file is written partially before the write fails."""
    real_io_open = io.open
    real_cio_open = _io.open

    def io_open_proxy(*args, **kwargs):
        return _PartialWriter(real_io_open(*args, **kwargs))

    def cio_open_proxy(*args, **kwargs):
        return _PartialWriter(real_cio_open(*args, **kwargs))

    _MID_WRITE_LOG.clear()
    with mock.patch.object(io, "open", io_open_proxy), \
            mock.patch.object(_io, "open", cio_open_proxy):
        yield


@contextmanager
def _inject_fsync_failure():
    """Flushing/syncing the temporary file to disk fails."""
    with mock.patch.object(os, "fsync", side_effect=OSError("injected fsync failure")):
        yield


@contextmanager
def _inject_replace_failure():
    """Replacing the destination with the temporary file fails."""
    with mock.patch.object(os, "replace", side_effect=OSError("injected replace failure")):
        yield


# --------------------------------------------------------------------------- #
# Tests                                                                       #
# --------------------------------------------------------------------------- #

class ConfigPersistenceTestCase(unittest.TestCase):
    def setUp(self):
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.workdir = self._tempdir.name
        self.config_path = os.path.join(self.workdir, "config.json")
        self.sentinel_path = os.path.join(self.workdir, "unrelated-notes.txt")
        self.sentinel_bytes = b"unrelated sentinel content\n"
        with open(self.sentinel_path, "wb") as handle:
            handle.write(self.sentinel_bytes)
        self.messagebox = MAIN.messagebox
        self.messagebox.reset()
        del MAIN.ctk.appearance_calls[:]

    # -- helpers ------------------------------------------------------------

    def _make_app(self, cookie="", appearance="Dark"):
        """Build an application instance without ever opening a window."""
        app = MAIN.CrawlerGUI.__new__(MAIN.CrawlerGUI)
        app.config_file = self.config_path
        app.saved_cookie = cookie
        app.appearance_var = _StubVar(appearance)
        app.cookie_text = _StubTextbox()
        return app

    def _write_config(self, config):
        with open(self.config_path, "w", encoding="utf-8") as handle:
            json.dump(config, handle, ensure_ascii=False, indent=2)

    def _read_bytes(self, path):
        with open(path, "rb") as handle:
            return handle.read()

    def _read_config(self):
        with open(self.config_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _entries(self):
        return sorted(os.listdir(self.workdir))

    def _capture_stdout(self, func, *args, **kwargs):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            result = func(*args, **kwargs)
        return result, buffer.getvalue()

    def _assert_failed_save_keeps_everything(self, injection):
        previous = {"cookie": "old=1", "appearance": "Dark"}
        self._write_config(previous)
        original_bytes = self._read_bytes(self.config_path)
        app = self._make_app(cookie="new=2")
        with injection:
            result = app.save_config()
        self.assertIs(result, False)
        self.assertEqual(self._read_bytes(self.config_path), original_bytes)
        self.assertEqual(self._read_config(), previous)
        self.assertEqual(self._entries(), ["config.json", "unrelated-notes.txt"])
        self.assertEqual(self._read_bytes(self.sentinel_path), self.sentinel_bytes)


class SaveConfigTests(ConfigPersistenceTestCase):
    def test_initial_save_writes_a_valid_config_file(self):
        app = self._make_app()
        self.assertIs(app.save_config(), True)
        self.assertTrue(os.path.exists(self.config_path))
        stored = self._read_config()
        self.assertEqual(sorted(stored.keys()), ["appearance", "cookie"])
        self.assertEqual(stored["cookie"], "")
        self.assertEqual(stored["appearance"], "Dark")

    def test_update_replaces_the_previous_config(self):
        self._write_config({"cookie": "old=1", "appearance": "Dark"})
        app = self._make_app(cookie="new=2")
        self.assertIs(app.save_config(), True)
        stored = self._read_config()
        self.assertEqual(stored["cookie"], "new=2")
        self.assertEqual(stored["appearance"], "Dark")

    def test_unicode_content_round_trips(self):
        cookie = "SESSDATA=测试值; bili_jct=数据😀"
        app = self._make_app(cookie=cookie)
        self.assertIs(app.save_config(), True)
        raw = self._read_bytes(self.config_path).decode("utf-8")
        self.assertIn(cookie, raw)
        self.assertEqual(self._read_config()["cookie"], cookie)

    def test_successful_save_leaves_no_temporary_files_behind(self):
        app = self._make_app(cookie="a=1")
        self.assertIs(app.save_config(), True)
        self.assertEqual(self._entries(), ["config.json", "unrelated-notes.txt"])

    def test_failed_serialization_keeps_the_previous_file(self):
        previous = {"cookie": "old=1", "appearance": "Dark"}
        self._write_config(previous)
        original_bytes = self._read_bytes(self.config_path)
        app = self._make_app(cookie="new=2")
        app.appearance_var = _StubVar(_Unserializable())
        self.assertIs(app.save_config(), False)
        self.assertEqual(self._read_bytes(self.config_path), original_bytes)
        self.assertEqual(self._read_config(), previous)
        self.assertEqual(self._entries(), ["config.json", "unrelated-notes.txt"])
        self.assertEqual(self._read_bytes(self.sentinel_path), self.sentinel_bytes)

    def test_failed_initial_save_leaves_no_config_file(self):
        app = self._make_app(cookie="a=1")
        app.appearance_var = _StubVar(_Unserializable())
        self.assertIs(app.save_config(), False)
        self.assertFalse(os.path.exists(self.config_path))
        self.assertEqual(self._entries(), ["unrelated-notes.txt"])

    def test_failed_write_keeps_the_previous_file(self):
        self._assert_failed_save_keeps_everything(_inject_write_failure())

    def test_failed_mid_write_keeps_the_previous_file(self):
        self._assert_failed_save_keeps_everything(_inject_mid_write_failure())
        self.assertTrue(_MID_WRITE_LOG, "the fixture must really write part of the payload")

    def test_failed_fsync_keeps_the_previous_file(self):
        self._assert_failed_save_keeps_everything(_inject_fsync_failure())

    def test_failed_replace_keeps_the_previous_file(self):
        self._assert_failed_save_keeps_everything(_inject_replace_failure())

    def test_save_after_a_failed_save_succeeds(self):
        self._write_config({"cookie": "old=1", "appearance": "Dark"})
        app = self._make_app(cookie="new=2")
        with _inject_write_failure():
            self.assertIs(app.save_config(), False)
        self.assertIs(app.save_config(), True)
        self.assertEqual(self._read_config()["cookie"], "new=2")
        self.assertEqual(self._entries(), ["config.json", "unrelated-notes.txt"])

    def test_save_reports_failure_when_the_destination_directory_is_missing(self):
        app = self._make_app(cookie="a=1")
        app.config_file = os.path.join(self.workdir, "missing", "config.json")
        self.assertIs(app.save_config(), False)
        self.assertEqual(self._entries(), ["unrelated-notes.txt"])

    def test_destination_is_replaced_only_after_the_new_content_is_complete(self):
        previous = {"cookie": "old=1", "appearance": "Dark"}
        self._write_config(previous)
        original_bytes = self._read_bytes(self.config_path)
        observed = {}
        real_fsync = os.fsync

        def observing_fsync(fd):
            observed["destination_bytes"] = self._read_bytes(self.config_path)
            observed["entries"] = sorted(os.listdir(self.workdir))
            return real_fsync(fd)

        app = self._make_app(cookie="new=2")
        with mock.patch.object(os, "fsync", observing_fsync):
            self.assertIs(app.save_config(), True)
        self.assertEqual(observed["destination_bytes"], original_bytes)
        extras = set(observed["entries"]) - {"config.json", "unrelated-notes.txt"}
        self.assertEqual(len(extras), 1)
        self.assertEqual(self._read_config()["cookie"], "new=2")
        self.assertEqual(self._entries(), ["config.json", "unrelated-notes.txt"])


class SaveCookieTests(ConfigPersistenceTestCase):
    def test_save_cookie_reports_success_only_after_the_config_is_persisted(self):
        app = self._make_app()
        app.cookie_text.text = "invented=1; other=2"
        app.save_cookie()
        self.assertEqual(len(self.messagebox.of_kind("showinfo")), 1)
        self.assertEqual(self.messagebox.of_kind("showerror"), [])
        self.assertEqual(app.saved_cookie, "invented=1; other=2")
        self.assertEqual(app.cookie_text.text, "invented=1; other=2")
        self.assertEqual(self._read_config()["cookie"], "invented=1; other=2")

    def test_empty_cookie_is_not_saved(self):
        app = self._make_app()
        app.cookie_text.text = "   "
        app.save_cookie()
        self.assertEqual(len(self.messagebox.of_kind("showwarning")), 1)
        self.assertEqual(self.messagebox.of_kind("showinfo"), [])
        self.assertFalse(os.path.exists(self.config_path))

    def test_failed_save_cookie_reports_an_error_and_keeps_the_previous_state(self):
        self._write_config({"cookie": "old=1", "appearance": "Dark"})
        original_bytes = self._read_bytes(self.config_path)
        app = self._make_app(cookie="old=1")
        app.cookie_text.text = "new=2"
        with _inject_write_failure():
            app.save_cookie()
        errors = self.messagebox.of_kind("showerror")
        self.assertEqual(len(errors), 1)
        self.assertEqual(self.messagebox.of_kind("showinfo"), [])
        self.assertEqual(app.saved_cookie, "old=1")
        self.assertEqual(app.cookie_text.text, "new=2")
        self.assertEqual(self._read_bytes(self.config_path), original_bytes)
        self.assertEqual(self._entries(), ["config.json", "unrelated-notes.txt"])

    def test_failed_save_cookie_does_not_leak_the_cookie_or_private_paths(self):
        app = self._make_app(cookie="old=1")
        app.cookie_text.text = "secret-cookie-value"
        with _inject_write_failure():
            _result, output = self._capture_stdout(app.save_cookie)
        errors = self.messagebox.of_kind("showerror")
        self.assertEqual(len(errors), 1)
        message = errors[0]["message"] or ""
        self.assertNotIn("secret-cookie-value", message)
        self.assertNotIn(self.workdir, message)
        self.assertNotIn(os.path.basename(self.config_path), message)
        self.assertNotIn("secret-cookie-value", output)
        self.assertNotIn(self.workdir, output)


class ClearCookieTests(ConfigPersistenceTestCase):
    def test_clear_cookie_persists_the_empty_value_and_clears_the_widget(self):
        self._write_config({"cookie": "old=1", "appearance": "Dark"})
        app = self._make_app(cookie="old=1")
        app.cookie_text.text = "old=1"
        app.clear_cookie()
        self.assertEqual(len(self.messagebox.of_kind("showinfo")), 1)
        self.assertEqual(self.messagebox.of_kind("showerror"), [])
        self.assertEqual(app.saved_cookie, "")
        self.assertEqual(app.cookie_text.text, "")
        self.assertEqual(self._read_config()["cookie"], "")

    def test_failed_clear_cookie_keeps_the_previous_cookie_and_widget(self):
        self._write_config({"cookie": "old=1", "appearance": "Dark"})
        original_bytes = self._read_bytes(self.config_path)
        app = self._make_app(cookie="old=1")
        app.cookie_text.text = "old=1"
        with _inject_write_failure():
            app.clear_cookie()
        errors = self.messagebox.of_kind("showerror")
        self.assertEqual(len(errors), 1)
        self.assertEqual(self.messagebox.of_kind("showinfo"), [])
        self.assertEqual(app.saved_cookie, "old=1")
        self.assertEqual(app.cookie_text.text, "old=1")
        self.assertEqual(self._read_bytes(self.config_path), original_bytes)
        self.assertEqual(self._entries(), ["config.json", "unrelated-notes.txt"])


class AppearanceTests(ConfigPersistenceTestCase):
    def test_appearance_change_is_persisted(self):
        app = self._make_app(cookie="a=1")
        app.appearance_var.set("Light")
        app.change_appearance("Light")
        self.assertEqual(self.messagebox.of_kind("showerror"), [])
        self.assertIn("Light", MAIN.ctk.appearance_calls)
        self.assertEqual(self._read_config()["appearance"], "Light")

    def test_failed_appearance_change_is_reported(self):
        app = self._make_app(cookie="a=1")
        app.appearance_var.set("Light")
        with _inject_write_failure():
            app.change_appearance("Light")
        errors = self.messagebox.of_kind("showerror")
        self.assertEqual(len(errors), 1)
        self.assertIn("Light", MAIN.ctk.appearance_calls)


if __name__ == "__main__":
    unittest.main()
