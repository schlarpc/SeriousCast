import struct
import re
import binascii
import io
import bitstring


def parse_transport_stream(data):
    data = data[data.index(b'G'):]

    while len(data):
        packet = {}
        ts = bitstring.ConstBitStream(data[:188])
        data = data[188:]

        packet.update({
            'sync_byte': ts.read(8),
            'transport_error_indicator': ts.read(1).bool,
            'payload_unit_start_indicator': ts.read(1).bool,
            'transport_priority': ts.read(1).bool,
            'pid': ts.read(13).uint,
            'scrambling_control': ts.read(2),
            'adaptation_field_exists': ts.read(1).bool,
            'contains_payload': ts.read(1).bool,
            'continuity_counter': ts.read(4),
        })

        if packet['adaptation_field_exists']:
            packet.update({
                'adaptation_field_length': ts.read(8).uint,
                'discontinuity_indicator': ts.read(1).bool,
                'random_access_indicator': ts.read(1).bool,
                'elementary_stream_priority_indicator': ts.read(1).bool,
                'pcr_flag': ts.read(1).bool,
                'opcr_flag': ts.read(1).bool,
                'splicing_point_flag': ts.read(1).bool,
                'transport_private_data_flag': ts.read(1).bool,
                'adaptation_field_extension_flag': ts.read(1).bool,
            })

            if packet['pcr_flag']:
                packet.update({
                    'pcr_base': ts.read(33).uint,
                    'pcr_padding': ts.read(6).uint,
                    'pcr_extension': ts.read(9).uint,
                })
            if packet['opcr_flag']:
                packet.update({
                    'opcr_base': ts.read(33).uint,
                    'opcr_padding': ts.read(6).uint,
                    'opcr_extension': ts.read(9).uint,
                })

            packet.update({
                'splice_countdown': ts.read(8).uint,
            })

            remaining_length = packet['adaptation_field_length'] - (2 + 4 * packet['pcr_flag'] + 4 * packet['opcr_flag'])
            if remaining_length > 0:
                ts.read(remaining_length * 8)

        if packet['contains_payload']:
            packet['payload'] = ts.read('bytes')

        yield packet


def synchsafe(n):
    bits28 = bitstring.BitArray('uint:28=' + str(n)).bin
    new_bits = '0b'
    for i in range(4):
        new_bits += '0' + bits28[i * 7 : (i + 1) * 7]
    return bitstring.BitArray(new_bits).bytes


def create_id3(pcr, title, artist):
    # use ID3 2.3 for Windows compatibility
    id3 = bytearray(b'ID3\x03\x00\x00')

    # As prescribed by HLS spec
    pcr_frame = bytearray()
    pcr_frame += b'com.apple.streaming.transportStreamTimestamp\x00'
    pcr_frame += struct.pack('!Q', pcr)
    pcr_frame = b'PRIV' + struct.pack('!I', len(pcr_frame)) + b'\x00\x00' + pcr_frame

    title_frame = bytearray()
    title_frame += b'\x01' + title.encode('utf-16') + b'\x00\x00'
    title_frame = b'TIT2' + synchsafe(len(title_frame)) + b'\x00\x00' + title_frame

    artist_frame = bytearray()
    artist_frame += b'\x01' + artist.encode('utf-16') + b'\x00\x00'
    artist_frame = b'TPE1' + synchsafe(len(artist_frame)) + b'\x00\x00' + artist_frame

    frames = pcr_frame + title_frame + artist_frame 
    id3 += synchsafe(len(frames)) + frames
    return id3


if __name__ == '__main__':
    with open('area33_64k_1_061235739360_00252952.ts', 'rb') as f:
        aac = bytearray()
        metadata = bytearray()
        pcr = None

        for packet in parse_transport_stream(f.read()):
            if pcr == None and 'pcr_base' in packet:
                pcr = packet['pcr_base']
            if packet['pid'] == 768:
                aac += packet['payload']
            elif packet['pid'] == 1024:
                metadata += packet['payload']

        with open('metadata.bin', 'wb') as m, open('aac.bin', 'wb') as a:
            a.write(aac)
            m.write(metadata)

        id3 = create_id3(pcr, 'title!', 'artist?')
        with open('tagged.m4a', 'wb') as tag:
            tag.write(id3)
            tag.write(aac)
