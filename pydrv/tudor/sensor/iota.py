from __future__ import annotations

import struct
import logging
import tudor


class IOTA:
    def __init__(self, iota_id: int, data: bytes):
        self.id = iota_id
        self.payload = data[4:]

        payload_size, header_id = struct.unpack("<HH", data[:4])
        assert len(self.payload) == payload_size
        assert iota_id == header_id

    @staticmethod
    def read_from_comm(
        comm: tudor.CommunicationInterface, iota_id: int, iota_type=None
    ):
        logging.log(tudor.LOG_PROTO, "Reading IOTA %04x..." % iota_id)

        off = 0
        size = 0
        iota = bytes()
        while size <= 0 or off < size:
            # Send command & unpack response
            resp = comm.send_command(
                struct.pack("<BHHxxxxII", tudor.Command.IOTA_FIND, iota_id, 2, off, 0),
                0x10006,
            )
            (iota_size,), iota_data = struct.unpack("<xxI", resp[:6]), resp[6:]

            # Handle IOTA size
            if iota_size == 0:
                if size <= 0:
                    raise Exception("Invalid IOTA id")
                else:
                    raise Exception("IOTA read unexpectedly interrupted")

            if size <= 0:
                size = iota_size
                logging.log(tudor.LOG_PROTO, "    size=%d" % size)
            else:
                assert iota_size == size

            # Add read bytes to contents
            if size - off < len(iota_data):
                iota_data = iota_data[: size - off]
            iota += iota_data
            off += len(iota_data)

        # Construct IOTA object
        return iota_type(iota_id, iota)


class PackedIOTA(IOTA):
    def __init__(self, iota_id: int, data: bytes):
        self.id = iota_id

        # Iterate over all IOTAs in data
        off = 0
        while off + 4 <= len(data):
            payload_size, header_id = struct.unpack("<HH", data[:4])
            assert off + 4 + payload_size <= len(data)

            # Only continue if the id matches
            if header_id != iota_id:
                break

            # Update payload and offset
            self.payload = data[off + 4 : off + 4 + payload_size]
            off += 4 + payload_size
        assert off > 0

        logging.log(
            tudor.LOG_PROTO,
            "Packed IOTA %04x: size=%d -> size=%d"
            % (iota_id, len(data), 4 + len(self.payload)),
        )

    @staticmethod
    def read_from_comm(
        comm: tudor.CommunicationInterface, iota_id: int, iota_type: type = None
    ):
        return IOTA.read_from_comm(
            comm, iota_id, iota_type if iota_type != None else PackedIOTA
        )


class ConfigVersionIOTA(IOTA):
    IOTA_ID = 9

    def __init__(self, iota_id: int, data: bytes):
        super().__init__(iota_id, data)
        assert len(self.payload) == 0x10
        self.major, self.minor, self.revision = struct.unpack(
            "<IIHxxxxxx", self.payload
        )

    @staticmethod
    def read_from_comm(comm):
        return IOTA.read_from_comm(comm, ConfigVersionIOTA.IOTA_ID, ConfigVersionIOTA)


class IplIOTA(PackedIOTA):
    IOTA_ID = 0x1A

    def __init__(self, iota_id: int, data: bytes):
        super().__init__(iota_id, data)

    @staticmethod
    def read_from_comm(comm):
        return PackedIOTA.read_from_comm(comm, IplIOTA.IOTA_ID, IplIOTA)


class WbfParamIOTA(PackedIOTA):
    IOTA_ID = 0x2F

    def __init__(self, iota_id: int, data: bytes):
        super().__init__(iota_id, data)

        # Three on-wire variants of this IOTA payload:
        #   8 bytes  - compact (Kensington 047d:8054, fw 10.1.3031663):
        #              ver byte at [0], u32 param at [4].
        #   16 bytes - the original layout: version at [3], param byte at [4].
        #   24 bytes - newer firmware (e.g. 06cb:00f9, series 154/136): the
        #              same leading 16-byte layout, padded.
        # (The 16/24 variants share the leading fields, so read the same two.)
        if len(self.payload) == 8:
            ver, self.param = struct.unpack("<BxxxI", self.payload)
        else:
            ver, self.param = self.payload[3], self.payload[4]
        if ver != 1:
            raise ValueError(
                "Unsupported WBF parameter IOTA version: %d" % ver
            )

    @staticmethod
    def read_from_comm(comm):
        return PackedIOTA.read_from_comm(comm, WbfParamIOTA.IOTA_ID, WbfParamIOTA)
