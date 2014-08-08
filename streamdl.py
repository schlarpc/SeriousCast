#!/usr/bin/env python3

# Stream downloader.
# Usage: ./streamdl.py <channel_number>

import sirius
import mpegutils
import configparser
import sys
import datetime

if __name__ == "__main__":
    cfg = configparser.ConfigParser()
    cfg.read('settings.cfg')
    sxm = sirius.Sirius()
    sxm.login(cfg.get('SeriousCast', 'username'), cfg.get('SeriousCast', 'password'))

    channel_number = int(sys.argv[1])
    channel_key = sxm.lineup[channel_number]['channelKey']
    filename = sxm.lineup[channel_number]['name'] + ' ' + datetime.datetime.now().strftime("%y-%m-%d %H-%M") + '.aac'

    original_playlist = sxm.get_playlist(sxm.lineup[channel_number]['channelKey'])
    playlist = [x for x in original_playlist.splitlines() if x.endswith('.ts')]

    for segment in playlist:
        print(segment)
    
        segment_data = sxm.get_segment(channel_key, segment)

        audio = bytearray()
        metadata = bytearray()
        pcr = None

        for packet in mpegutils.parse_transport_stream(segment_data):
            if pcr == None and 'pcr_base' in packet:
                pcr = packet['pcr_base']
            if packet['pid'] == 768:
                audio += packet['payload']
            elif packet['pid'] == 1024:
                metadata += packet['payload']

        audio_adts = bytearray()
        for packet in mpegutils.parse_packetized_elementary_stream(audio):
            audio_adts += packet['payload']

        with open(filename, 'ab') as f:
            f.write(audio_adts)
