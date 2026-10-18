"""Offline contract tests for the live eight-byte shared-memory protocol."""
import importlib.util
import pathlib
import sys
import types
import unittest


class Memory:
    def __init__(self):
        self.data = bytearray(8)

    def read(self, offset, target):
        assert 0 <= offset <= offset + len(target) <= 8
        target[:] = self.data[offset:offset + len(target)]

    def write(self, offset, data):
        assert 0 <= offset <= offset + len(data) <= 8
        self.data[offset:offset + len(data)] = data


class ProtocolTest(unittest.TestCase):
    def setUp(self):
        self.memory = Memory()
        previous = sys.modules.get('cambc')
        sys.modules['cambc'] = types.SimpleNamespace(shared_memory=self.memory)
        path = pathlib.Path(__file__).resolve().parents[1] / 'bots' / 'my-bot' / 'src' / 'coordination.py'
        if not path.exists():
            path = pathlib.Path(__file__).with_name('coordination.py')
        spec = importlib.util.spec_from_file_location('coordination_tested', path)
        self.protocol = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.protocol)
        if previous is None:
            del sys.modules['cambc']
        else:
            sys.modules['cambc'] = previous

    def test_each_writer_preserves_teammates_and_alert(self):
        self.protocol.report(99, 99, 254, True)
        alert = self.memory.data[5:]
        expected = [0] * 6
        for slot, group in enumerate([0, 62, 30, 14, 3, 55]):
            self.protocol.write_claim(slot, group)
            expected[slot] = group + 1
            self.assertEqual(self.protocol.read_claims(), expected)
            self.assertEqual(self.memory.data[5:], alert)
        self.protocol.write_claim(2, None)
        expected[2] = 0
        self.assertEqual(self.protocol.read_claims(), expected)

    def test_alert_preserves_claims_and_wraps_timestamp(self):
        self.protocol.write_claim(5, 62)
        claims = self.memory.data[:5]
        self.protocol.report(0, 99, 254, False)
        _, position, age = self.protocol.read_report(257)
        self.assertEqual(position, (0, 99))
        self.assertEqual(age, 3)
        self.assertEqual(self.memory.data[:5], claims)
        self.assertGreater(self.protocol.read_report(270)[2], 8)

    def test_empty_and_unencodable_claims(self):
        self.assertIsNone(self.protocol.read_report(0)[1])
        self.protocol.write_claim(0, 63)
        self.protocol.write_claim(6, 0)
        self.assertEqual(bytes(self.memory.data), bytes(8))


if __name__ == '__main__':
    unittest.main()
