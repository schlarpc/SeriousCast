

$(function() {
    var vlc = $('#vlc')[0];
    var url_base = 'http://' + document.location.hostname + ':' + document.location.port;
    var offset = 0;
    var current_channel = undefined;
    
    function start_stream(stream_url) {
        vlc.playlist.stop();
        vlc.playlist.items.clear();
        vlc.playlist.add(stream_url);
        vlc.playlist.play();
    }
    
    function set_metadata(channel, now_playing) {
        $('#player-channel').text(channel);
        $('#player-nowplaying').text(now_playing);
        $('body').css('margin-top', '80px');
        $('title').text(now_playing);
    }
    
    if (vlc.playlist === undefined) {
        $('#player, .player-stream').remove();
        $('header').css('position', 'static');
        $('h1').css('float', 'none');
        $('body').css('margin-top', '0');
        $('#player-loaded').text('VLC plugin not found, streaming not enabled.');
    }
    
    $('.player-stream').click(function() {
        current_channel = $(this).data('channel');
        start_stream(url_base + '/channel/' + current_channel + '/' + offset);
        return false;
    });
    
    $('#player-pause').click(function() {
        vlc.playlist.togglePause();
    });
    
    $('#player-mute').click(function() {
        vlc.audio.toggleMute();
    });
    
    $('#player-volume').change(function() {
        vlc.audio.volume = parseInt($('#player-volume').val(), 10);
    });
    
    $('#player-rewind').change(function() {
        offset = 300 - $('#player-rewind').val();
        
        if (offset == 0) {
            $('#player-rewind-status').text('Live');
        } else {
            $('#player-rewind-status').text(offset + ' min ago');
        }
    });
    
    $('#player-rewind').mouseup(function() {
        if (current_channel !== undefined) {
            start_stream(url_base + '/channel/' + current_channel + '/' + offset);
        }
    });
    
    $('#player-rewind-status').click(function() {
        $('#player-rewind').val(300);
        $('#player-rewind').change();
        $('#player-rewind').mouseup();
    });
    
    setInterval(function() {
        try {
            var title = vlc.mediaDescription.title;
            var now_playing = "Retrieving info...";
            
            if (title != null) {
                if (vlc.mediaDescription.nowPlaying != null) {
                    now_playing = vlc.mediaDescription.nowPlaying;
                }
                set_metadata(title, now_playing);
            }
        } catch (ex) {
        }
    }, 1000);
});
