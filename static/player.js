var current_channel = undefined;

$(function() {
    var vlc = $('#vlc')[0];
    var url_base = 'http://' + document.location.hostname + ':' + document.location.port;
    
    function start_stream(stream_url) {
        vlc.playlist.stop();
        vlc.playlist.clear();
        vlc.playlist.add(stream_url);
        vlc.playlist.play();
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
        start_stream(url_base + '/channel/' + current_channel);
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
    
    $('#player-rewind').click(function() {
        if (current_channel === undefined) {
            alert('Nothing is playing!');
        } else {
            var minutes = parseInt(prompt('Rewind how many minutes?'), 10);
            if (isNaN(minutes)) {
                alert('Invalid input.');
            } else {
                start_stream(url_base + '/channel/' + current_channel + '/' + minutes);
            }
        }
    });
    
    setInterval(function() {
        try {
            $('#player-channel').text(vlc.mediaDescription.title);
            
            if (vlc.mediaDescription.nowPlaying != null) {
                $('#player-nowplaying').text(vlc.mediaDescription.nowPlaying);
                $('title').text(vlc.mediaDescription.title + ' :: ' + vlc.mediaDescription.nowPlaying);
            } else {
                $('#player-nowplaying').text("Retrieving info...");
            }
        } catch (ex) {
        }
    }, 1000);
});
