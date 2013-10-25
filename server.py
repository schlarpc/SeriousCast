#!/usr/bin/env python3.3

import http.server
import socketserver
import socket
import subprocess
import re
import configparser

import jinja2
import sirius


class SeriousHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


class SeriousRequestHandler(http.server.BaseHTTPRequestHandler):
    def channel_stream(self, channel_number):
        channel = sxm.lineup[channel_number]

        self.protocol_version = 'ICY' # if we don't pretend to be shoutcast, doctors HATE us
        self.log_request(200)
        self.send_response_only(200)
        self.send_header('Content-type', 'audio/aacp')
        self.send_header('icy-br', '64')
        self.send_header('icy-name', channel['name'])
        self.send_header('icy-genre', channel['genre'])
        self.send_header('icy-url', url)
        self.end_headers()

        channel_id = str(channel['channelKey'])

        for packet in sxm.packet_generator(channel_id):
            command = ['ffmpeg', '-i', 'pipe:0', '-y', '-map', '0:1', '-c:a', 'copy', '-f', 'adts', 'pipe:1']
            proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            adts_data = proc.communicate(packet)[0]
            adts_data += b'\0' * (180000 - len(adts_data))
            print(len(adts_data))
            try:
                self.wfile.write(adts_data)
            except (ConnectionResetError, ConnectionAbortedError) as e:
                print('Connection dropped: ', e)
                return

        self.wfile.write(b'\r\n\r\n')


    def channel_playlist(self, channel_number):
        self.send_response(200)
        self.send_header('Content-type', 'audio/x-scpls')
        self.send_header('Content-disposition', 'attachment; filename="{} - {}.pls"'.format(
            channel_number, sxm.lineup[channel_number]['name']))
        self.end_headers()

        template = templates.get_template('playlist.pls')
        playlist = template.render({'url': url + 'channel/{}'.format(
            channel_number)})

        self.wfile.write(playlist.encode('utf-8'))
        self.wfile.write(b'\r\n\r\n')


    def index(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()

        template = templates.get_template('list.html')
        html = template.render({'channels': sorted(sxm.lineup.values(), key=lambda k: k['siriusChannelNo'])})
        
        self.wfile.write(html.encode('utf-8'))
        self.wfile.write(b'\r\n\r\n')


    def do_GET(self):
        match = re.search('^/channel/([0-9]+)$', self.path)
        if match:
            channel_number = int(match.group(1))
            return self.channel_stream(channel_number)

        match = re.search('^/playlist/([0-9]+)$', self.path)
        if match:
            channel_number = int(match.group(1))
            return self.channel_playlist(channel_number)

        self.index()


if __name__ == '__main__':
    print('Setting up, please wait')
    
    cfg = configparser.ConfigParser()
    cfg.read('settings.cfg')
    username = cfg.get('SeriousCast', 'username')
    password = cfg.get('SeriousCast', 'password')
    url = 'http://{}:{}/'.format(
        cfg.get('SeriousCast', 'hostname'),
        cfg.get('SeriousCast', 'port'),
    )
    
    sxm = sirius.Sirius()
    sxm.login(username, password)
    
    templates = jinja2.Environment(loader=jinja2.FileSystemLoader('templates'))
    
    port = cfg.getint('SeriousCast', 'port')
    server = SeriousHTTPServer(('0.0.0.0', port), SeriousRequestHandler)
    print('Starting server, use <Ctrl-C> to stop')
    server.serve_forever()
