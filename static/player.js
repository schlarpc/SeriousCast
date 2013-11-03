$(function() {
    var vlc = $('#vlc')[0];
    
    if (vlc.playlist === undefined) {
        $('#player, .vlc-stream').remove();
        $('header').css('position', 'static');
        $('h1').css('float', 'none');
        $('body').css('margin-top', '0');
        $('#player-loaded').text('VLC plugin not found, streaming not enabled.');
    }
    
    $('.vlc-stream').click(function() {
        var stream_url = 'http://' + document.location.hostname + ':' + document.location.port + '/channel/' + $(this).data('channel');
        console.log(stream_url);
        vlc.playlist.stop();
        vlc.playlist.clear();
        vlc.playlist.add(stream_url);
        vlc.playlist.play();
        return false;
    });
    
    $('#vlc-pause').click(function() {
        vlc.playlist.togglePause();
    });
    
    $('#vlc-mute').click(function() {
        vlc.audio.toggleMute();
    });
    
    $('#vlc-volume').change(function() {
        vlc.audio.volume = parseInt($('#vlc-volume').val(), 10);
    });
    
    setInterval(function() {
        try {
            $('#vlc-channel').text(vlc.mediaDescription.title);
            
            if (vlc.mediaDescription.nowPlaying != null) {
                $('#vlc-nowplaying').text(vlc.mediaDescription.nowPlaying);
                $('title').text(vlc.mediaDescription.title + ' :: ' + vlc.mediaDescription.nowPlaying);
            } else {
                $('#vlc-nowplaying').text("Retrieving info...");
            }
        } catch (ex) {
        }
    }, 1000);
});
