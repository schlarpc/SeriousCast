#! python3

import http.server
import socketserver
import socket
import subprocess
import re
import configparser

import sirius


class SeriousHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


class SeriousRequestHandler(http.server.BaseHTTPRequestHandler):
    def channel_stream(self, channel_number):
        channel = sxm.lineup[channel_number]

        self.protocol_version = 'ICY' # if we don't pretend to be shoutcast, doctors HATE us
        self.send_response(200)
        self.send_header('Content-type', 'audio/aacp')
        self.send_header('icy-br', '64')
        self.send_header('icy-name', channel['name'])
        self.send_header('icy-genre', channel['genre'])
        self.end_headers()

        channel_id = str(channel['channelKey'])

        for packet in sxm.packet_generator(channel_id):
            command = ['ffmpeg', '-i', 'pipe:0', '-y', '-map', '0:1', '-c:a', 'copy', '-f', 'adts', 'pipe:1']
            proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            adts_data = proc.communicate(packet)[0]
            try:
                self.wfile.write(adts_data)
            except (ConnectionResetError, ConnectionAbortedError) as e:
                print('Connection dropped: ', e)
                return

        self.wfile.write(b'\r\n\r\n')


    def channel_playlist(self, channel_number):
        self.send_response(200)
        self.send_header('Content-type', 'audio/x-scpls')
        self.send_header('Content-disposition', 'attachment; filename={}.pls'.format(channel_number))
        self.end_headers()

        self.wfile.write(b'[playlist]\r\n')
        self.wfile.write('File1=http://{}:30000/channel/{}'.format(
            cfg.get('SeriousCast', 'hostname'),
            channel_number
        ).encode())

        self.wfile.write(b'\r\n\r\n')


    def index(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()

        html = """
        <html>
            <head>
                <title>SeriousCast</title>
            </head>
            <body>
                <h1>SeriousCast</h1>
                <b>Streams require something that can play Shoutcast, like VLC</b>
                <table>{}</table>
            </body>
        </html>
        """

        table = ""
        for channel_number in sorted(list(sxm.lineup.keys())):
            channel = sxm.lineup[channel_number]
            table += '<tr><td><a href="/playlist/{0}">{0}</a></td><td>{1}</td><td>{2}</td><td>{3}</td></tr>'.format(
                channel_number,
                channel['name'],
                channel['genre'],
                channel['description'],
            )

        self.wfile.write(html.format(table).encode('utf-8'))
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

    sxm = sirius.Sirius()
    sxm.login(username, password)
    
    server = SeriousHTTPServer(('0.0.0.0', 30000), SeriousRequestHandler)
    print('Starting server, use <Ctrl-C> to stop')
    server.serve_forever()
