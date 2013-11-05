

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
        $('.currentinfo h3').text(channel);
        $('.currentinfo h4').text(now_playing);
        $('.controls').css('bottom', '0');
        $('#channels').css('margin-bottom', '98px');
        $('title').text(now_playing);
    }

    function change_art(title) {
        console.log(title);
        console.log("https://itunes.apple.com/search?term="+encodeURI(title.replace( /[^a-zA-Z]/g, " ")));
        $.ajax({
            url: "https://itunes.apple.com/search?term="+encodeURI(title.replace( /[^a-zA-Z]/g, " ")),
            dataType: 'JSONP'
        })
        .done(function(data) {
            if (data['resultCount'] != 0) {
                var smallart = data['results'][0]['artworkUrl60'];
                var bigart = smallart.replace("60x60-50","1200x1200-75");
                $('.art').css('background-image',"url('"+bigart+"')");
                $('.playpause').css('background-image',"url('"+smallart+"')");
                $('#buylink').show();
                $('#buylink').attr('href',data['results'][0]['trackViewUrl']);
            } else {
                $('.art').css('background-image',"url('http://a4.mzstatic.com/us/r30/Music/v4/04/15/78/04157815-169d-9f91-d596-342dee2f4c46/UMG_cvrart_00602537150120_01_RGB72_1200x1200_12UMGIM46901.1200x1200-75.jpg')");
                $('.playpause').css('background-image','none');
                $('#buylink').hide();
            }
        })
    }
    
    if (vlc.playlist === undefined) {
        /*
        $('#player, .player-stream').remove();
        $('header').css('position', 'static');
        $('h1').css('float', 'none');
        $('body').css('margin-top', '0');
        */
        $('#player-loaded').text('VLC plugin not found, streaming not enabled.');
    }
    
    $('.player-stream').click(function() {
        current_channel = $(this).data('channel');
        start_stream(url_base + '/channel/' + current_channel + '/' + offset);
        return false;
    });
    
    $('.playpause img').click(function() {
        if (vlc.playlist.isPlaying) {
            $(this).attr('src','static/img/play.svg');
        } else {
            $(this).attr('src','static/img/pause.svg');
        }
        console.log(vlc.audio.volume);
        vlc.playlist.togglePause();
    });
    
    $('.volume img').click(function() {
        if (vlc.audio.mute) {
            $(this).attr('src','static/img/volume-high.svg');
        } else {
            $(this).attr('src','static/img/volume-mute.svg');
        }
        vlc.audio.toggleMute();
    });
    
    $('#player-volume').change(function() {
        vlc.audio.volume = parseInt($('#player-volume').val(), 10);
    });
    
    $('#player-rewind').change(function() {
        offset = 300 - $('#player-rewind').val();
        
        if (offset == 0) {
            $('#time').text('Live');
        } else {
            $('#time').text(offset + ' min ago');
        }
    });
    
    $('#player-rewind').mouseup(function() {
        if (current_channel !== undefined) {
            start_stream(url_base + '/channel/' + current_channel + '/' + offset);
        }
    });
    
    $('#time').click(function() {
        $('#player-rewind').val(300);
        $('#player-rewind').change();
        $('#player-rewind').mouseup();
    });

    $('#infobutton').mouseover(function() {
        console.log('test');
        $('.info').show();
        $('#infobutton').mouseleave(function() {
            $('.info').hide();
            console.log('test2');
        });
    });
    
    setInterval(function() {
        try {
            var title = vlc.mediaDescription.title;
            var now_playing = "Retrieving info...";
            
            if (title != null) {
                if (vlc.mediaDescription.nowPlaying != null) {
                    now_playing = vlc.mediaDescription.nowPlaying;
                }
                if ($('.currentinfo h4').text() != now_playing || $('.currentinfo h3').text() != channel) {
                    change_art(now_playing);
                    set_metadata(title, now_playing);
                }
            }
        } catch (ex) {
        }
    }, 1000);
});