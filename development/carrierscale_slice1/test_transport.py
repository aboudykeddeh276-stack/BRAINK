import unittest

from transport import TransportError, frame_payload, reassemble_frames, verify_round_trip


class Slice1TransportTests(unittest.TestCase):
    def round_trip(self, payload: bytes) -> None:
        receipt = verify_round_trip(payload, transfer_id="test-transfer")
        self.assertTrue(receipt.verified)
        self.assertEqual(receipt.byte_count, len(payload))

    def test_zero_bytes(self):
        self.round_trip(b"")

    def test_all_byte_values(self):
        self.round_trip(bytes(range(256)))

    def test_embedded_nul_and_binary(self):
        self.round_trip(b"\x00KEX\xff\x00\x80\x01")

    def test_multiframe_payload(self):
        payload = bytes(range(256)) * 1024
        frames = frame_payload(payload, transfer_id="multi", frame_size=4096)
        self.assertGreater(len(frames), 1)
        self.assertEqual(reassemble_frames(frames, transfer_id="multi"), payload)

    def test_wrong_transfer_rejected(self):
        frames = frame_payload(b"abc", transfer_id="a")
        with self.assertRaises(TransportError):
            reassemble_frames(frames, transfer_id="b")

    def test_truncated_frame_rejected(self):
        frames = frame_payload(b"abc", transfer_id="a")
        with self.assertRaises(TransportError):
            reassemble_frames([frames[0][:8]], transfer_id="a")

    def test_corruption_rejected(self):
        frames = frame_payload(b"abc", transfer_id="a")
        damaged = bytearray(frames[0])
        damaged[-1] ^= 1
        with self.assertRaises(TransportError):
            reassemble_frames([bytes(damaged)], transfer_id="a")

    def test_missing_frame_rejected(self):
        payload = b"x" * 10000
        frames = frame_payload(payload, transfer_id="a", frame_size=1024)
        with self.assertRaises(TransportError):
            reassemble_frames(frames[:-1], transfer_id="a")

    def test_duplicate_frame_rejected(self):
        frames = frame_payload(b"x" * 3000, transfer_id="a", frame_size=1024)
        with self.assertRaises(TransportError):
            reassemble_frames([frames[0], frames[0], *frames[1:]], transfer_id="a")

    def test_oversize_rejected(self):
        with self.assertRaises(TransportError):
            frame_payload(b"12345", transfer_id="a", max_payload=4)

    def test_transport_does_not_execute_payload(self):
        payload = b"rm -rf /\x00not-a-command"
        frames = frame_payload(payload, transfer_id="opaque")
        self.assertEqual(reassemble_frames(frames, transfer_id="opaque"), payload)


if __name__ == "__main__":
    unittest.main()
