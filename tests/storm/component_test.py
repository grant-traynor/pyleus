import contextlib
from cStringIO import StringIO

import mock

try:
    import simplejson as json
    _ = json # pyflakes
except ImportError:
    import json

from pyleus.storm import StormTuple
from pyleus.testing import ComponentTestCase


class TestComponent(ComponentTestCase):

    def test__read_msg_dict(self):
        msg_dict = {
            'hello': "world",
        }

        self.mock_input_stream.readline.side_effect = [
            json.dumps(msg_dict),
            "end",
        ]

        assert self.instance._read_msg() == msg_dict

    def test__read_msg_list(self):
        msg_list = [3, 4, 5]

        self.mock_input_stream.readline.side_effect = [
            json.dumps(msg_list),
            "end",
        ]

        assert self.instance._read_msg() == msg_list

    def test__msg_is_command(self):
        command_msg = dict(this_is_a_command=True)
        taskid_msg = ["this", "is", "a", "taskid", "list"]

        assert self.instance._msg_is_command(command_msg)
        assert not self.instance._msg_is_command(taskid_msg)

    def test__msg_is_taskid(self):
        command_msg = dict(this_is_a_command=True)
        taskid_msg = ["this", "is", "a", "taskid", "list"]

        assert not self.instance._msg_is_taskid(command_msg)
        assert self.instance._msg_is_taskid(taskid_msg)

    def test_read_command(self):
        command_msg = dict(this_is_a_command=True)
        taskid_msg = ["this", "is", "a", "taskid", "list"]

        messages = [
            taskid_msg,
            taskid_msg,
            taskid_msg,
            command_msg,
        ]

        with mock.patch.object(self.instance, '_read_msg',
                side_effect=messages):
            command = self.instance.read_command()

        assert command == command_msg
        assert len(self.instance._pending_taskids) == 3

    def test_read_command_queued(self):
        next_command = dict(next_command=3)
        another_command = dict(another_command=7)

        self.instance._pending_commands.extend([
            next_command,
            another_command,
            another_command,
        ])

        assert self.instance.read_command() == next_command
        assert len(self.instance._pending_commands) == 2

    def test_read_taskid(self):
        command_msg = dict(this_is_a_command=True)
        taskid_msg = ["this", "is", "a", "taskid", "list"]

        messages = [
            command_msg,
            command_msg,
            command_msg,
            taskid_msg,
        ]

        with mock.patch.object(self.instance, '_read_msg',
                side_effect=messages):
            taskid = self.instance.read_taskid()

        assert taskid == taskid_msg
        assert len(self.instance._pending_commands) == 3

    def test_read_taskid_queued(self):
        next_taskid = dict(next_taskid=3)
        another_taskid = dict(another_taskid=7)

        self.instance._pending_taskids.extend([
            next_taskid,
            another_taskid,
            another_taskid,
        ])


        assert self.instance.read_taskid() == next_taskid
        assert len(self.instance._pending_taskids) == 2

    def test_read_tuple(self):
        command_dict = {
            'id': "id",
            'comp': "comp",
            'stream': "stream",
            'task': "task",
            'tuple': "tuple",
        }

        expected_storm_tuple = StormTuple("id", "comp", "stream", "task",
            "tuple")

        with mock.patch.object(self.instance, 'read_command',
                return_value=command_dict):
            storm_tuple = self.instance.read_tuple()

        assert isinstance(storm_tuple, StormTuple)
        assert storm_tuple == expected_storm_tuple

    def test__send_msg(self):
        msg_dict = {
            'hello': "world",
        }

        expected_output = """{"hello": "world"}\nend\n"""

        with mock.patch.object(self.instance, '_output_stream',
                StringIO()) as sio:
            self.instance._send_msg(msg_dict)

        assert sio.getvalue() == expected_output

    def test__create_pidfile(self):
        with mock.patch('__builtin__.open') as mock_open:
            self.instance._create_pidfile("pid_dir", "pid")

        mock_open.assert_called_once_with("pid_dir/pid", 'a')

    def test__init_component(self):
        handshake_msg = {
            'conf': {"foo": "bar"},
            'context': "context",
            'pidDir': "pidDir",
        }

        patch__read_msg = mock.patch.object(self.instance, '_read_msg',
            return_value=handshake_msg)
        patch_os_getpid = mock.patch('os.getpid', return_value=1234)
        patch__send_msg = mock.patch.object(self.instance, '_send_msg')
        patch__create_pidfile = mock.patch.object(self.instance,
            '_create_pidfile')

        patches = contextlib.nested(patch__read_msg, patch_os_getpid,
            patch__send_msg, patch__create_pidfile)

        with patches as (_, _, mock__send_msg, mock__create_pidfile):
            conf, context = self.instance._init_component()

        mock__send_msg.assert_called_once_with({'pid': 1234})
        mock__create_pidfile.assert_called_once_with("pidDir", 1234)

        assert conf == {"foo": "bar"}
        assert context == "context"

    def test_send_command_with_opts(self):
        with mock.patch.object(self.instance, '_send_msg') as mock__send_msg:
            self.instance.send_command('test', {'option': "foo"})

        mock__send_msg.assert_called_once_with({
            'command': "test",
            'option': "foo",
        })

    def test_send_command_with_no_opts(self):
        with mock.patch.object(self.instance, '_send_msg') as mock__send_msg:
            self.instance.send_command('test')

        mock__send_msg.assert_called_once_with({
            'command': "test",
        })

    def test_send_command_clobber_command(self):
        with mock.patch.object(self.instance, '_send_msg') as mock__send_msg:
            self.instance.send_command('test', {'command': "joe"})

        mock__send_msg.assert_called_once_with({
            'command': "test",
        })