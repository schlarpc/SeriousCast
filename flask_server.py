#!/usr/bin/env python3

from flask import Flask, Response
import sirius
import requests
import subprocess
import io
import mpegutils
import struct
import configparser


app = Flask(__name__)


@app.route("/")
def index():
    return repr(sxm.lineup[52])


@app.route("/channel/<int:channel_number>/")
def channel(channel_number):
    channel = sxm.lineup[channel_number]
    return channel['name']


@app.route("/channel/<int:channel_number>/playlist")
@app.route("/channel/<int:channel_number>/playlist.m3u8")
def playlist(channel_number):
    original_playlist = sxm.get_playlist(sxm.lineup[channel_number]['channelKey'])
    playlist = []
    for line in original_playlist.splitlines():
        if line.startswith('#SXIR'):
            continue
        elif line.endswith('.ts'):
            playlist.append('media/' + line)
        else:
            playlist.append(line)
    return Response('\r\n'.join(playlist), mimetype='application/vnd.apple.mpegurl')


@app.route("/channel/<int:channel_number>/media/<segment>")
def media_segment(channel_number, segment):
    segment_data = sxm.get_segment(sxm.lineup[channel_number]['channelKey'], segment)

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

    id3 = mpegutils.create_id3(pcr, 'Title', 'Artist')

    return Response(id3 + audio_adts, mimetype='application/octet-stream')


if __name__ == "__main__":
    cfg = configparser.ConfigParser()
    cfg.read('settings.cfg')

    sxm = sirius.Sirius()
    sxm.login(cfg.get('SeriousCast', 'username'), cfg.get('SeriousCast', 'password'))
    app.run(debug=True)
