#         Python Stream Deck Library
#      Released under the MIT license
#
#   dean [at] fourwalledcubicle [dot] com
#         www.fourwalledcubicle.com
#

import binascii
import logging

from .Transport import Transport, TransportError


class Dummy(Transport):
    """
    Dummy transport layer, for testing.
    """

    class Device(Transport.Device):
        def __init__(self, vid, pid):
            self.vid = vid
            self.pid = pid
            self.id = "{}:{}".format(vid, pid)
            self._is_open = False

        def open(self):
            if self._is_open:
                return

            logging.info("Deck opened")
            self._is_open = True

        def close(self):
            if not self._is_open:
                return

            logging.info("Deck closed")
            self._is_open = False

        def is_open(self):
            return self._is_open

        def connected(self):
            return True

        def vendor_id(self):
            return self.vid

        def product_id(self):
            return self.pid

        def path(self):
            return self.id

        def write_feature(self, payload):
            if not self._is_open:
                raise TransportError("Deck feature write while deck not open.")

            logging.info("Deck feature write (length %s):\n%s", len(payload), binascii.hexlify(payload, ' ').decode('utf-8'))
            return True

        def read_feature(self, report_id, length):
            if not self._is_open:
                raise TransportError("Deck feature read while deck not open.")

            logging.info("Deck feature read (length %s)", length)
            payload = bytearray(length)
            # Deterministic synthetic serial number, so tests and the API see
            # a stable, unique device id per emulated product. Deck classes
            # read it from feature report 0x03 or 0x06, at data offset 2 or 5
            # depending on model; write a copy at each offset so every reader
            # sees a clean value.
            if report_id in (0x03, 0x06):
                serial = f"DUMMY{self.vid:04x}{self.pid:04x}".encode("ascii")
                payload[2 : 2 + len(serial)] = serial
                payload[5 : 5 + len(serial)] = serial
            return payload

        def write(self, payload):
            if not self._is_open:
                raise TransportError("Deck write while deck not open.")

            logging.info("Deck report write (length %s):\n%s", len(payload), binascii.hexlify(payload, ' ').decode('utf-8'))
            return True

        def read(self, length):
            if not self._is_open:
                raise TransportError("Deck read while deck not open.")

            logging.info("Deck report read (length %s)", length)
            return None

    @staticmethod
    def probe():
        pass

    def enumerate(self, vid, pid):
        return [Dummy.Device(vid=vid, pid=pid)]
