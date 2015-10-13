Stream = new Object();

function ServerConnection(context)
{
  var that = this;

  that.context = context;

  that.connect = function ()
  {
    that.mode = $('#mic-mode').val();
    that.rate = $('#mic-rate').val();
    that.encoding = $('#mic-encoding').val();

    if (that.encoding == 'pcm')
      that.encoder = new PCMEncoder(that.rate);
    else if (that.encoding == 'a-law')
      that.encoder = new AlawEncoder(that.rate);

    that.socket = new WebSocket("ws://"+window.location.hostname+":"+window.location.port+"/stream", "Audio");
    that.socket.binaryType = "arraybuffer";

    that.socket.onopen = function (event)
    {
      console.log("websocket open");
      that.socket.send(JSON.stringify({
        'type': 'negotiate',
        'mode': that.mode,
        'rate': that.rate,
        'encoding': that.encoding,
        'blocksize': that.encoder.blockSize
      }));

      that.merger = that.context.createChannelMerger();

      if (that.mode == 'mic' || that.mode == 'mic+monitor') {
        that.microphone = new MicrophoneAudio(that.context);
        that.transmitter = new AudioTransmitter(that, that.encoder.sampleSize);
        that.microphone.connect(that.transmitter.processor);
        that.transmitter.connect(that.merger);
      }

      if (that.mode == 'monitor' || that.mode == 'mic+monitor') {
        that.receiver = new AudioReceiver(that, that.encoder.sampleSize);
        that.receiver.connect(that.merger);
      }

      that.merger.connect(that.context.destination);
    }

    that.socket.onmessage = function (event)
    {
      //console.log(JSON.stringify(event.data));

      if (event.data instanceof ArrayBuffer) {
        if (that.receiver)
          that.receiver.push_buffer(that.encoder.decodeBuffer(event.data));
      }
      else {
        msg = JSON.parse(event.data);
        Stream.handle_message(msg);
      }
    }

    that.socket.onclose = function (event)
    {
      console.log("websocket closed");
      if (that.receiver)
        that.receiver.disconnect();
      if (that.transmitter)
        that.transmitter.disconnect();
      if (that.microphone)
        that.microphone.disconnect();
      Stream.updateButtonState(false);
    }

    that.socket.onerror = function (event)
    {
      alert("Streaming Connection Lost");
      if (that.socket.readyState == WebSocket.OPEN)
        that.socket.close();
    }
  }

  that.disconnect = function ()
  {
    if (that.socket && that.socket.readyState != WebSocket.CLOSING && that.socket.readyState != WebSocket.CLOSED)
        that.socket.close();
  }

  that.send_audio = function (data)
  {
    if (that.socket)
      that.socket.send(that.encoder.encodeBuffer(data));
  }

  that.send_message = function (data)
  {
    if (that.socket)
      that.socket.send(JSON.stringify(data));
  }

  return that;
}


function AudioTransmitter(server, sampleSize)
{
  var that = this;

  that.server = server;
  that.processor = that.server.context.createScriptProcessor(sampleSize, 1, 1);

  that.processor.onaudioprocess = function (event)
  {
    var data = event.inputBuffer.getChannelData(0);
    that.server.send_audio(data);
    //event.outputBuffer.getChannelData(0).set(data);
  }

  that.connect = function (destination)
  {
    that.processor.connect(destination);
    //that.processor.connect(that.context.destination);
  }

  that.disconnect = function ()
  {
    that.processor.disconnect();
  }

  return that;
}


function AudioReceiver(server, sampleSize)
{
  var that = this;

  that.server = server;
  that.processor = that.server.context.createScriptProcessor(sampleSize, 1, 1);
  //that.processor.connect(context.destination);
  that.buffer = new Array();

  that.processor.onaudioprocess = function (event)
  {
    var data = that.buffer.shift() || new Float32Array(sampleSize);
    //var input = event.inputBuffer.getChannelData(0);
    /*
    for (var i = 0; i < input.length; i++) {
      data[i] += input[i];
    }
    */
    event.outputBuffer.getChannelData(0).set(data);
  }

  that.connect = function (destination)
  {
    that.processor.connect(destination);
    //that.processor.connect(that.context.destination);
  }

  that.disconnect = function ()
  {
    that.processor.disconnect();
  }

  that.push_buffer = function (data)
  {
    //console.log("Received " + data.length);
    that.buffer.push(data);

    /*
    var buffer = that.buffer.getChannelData(0);
    for (var i = 0; i < data.length; i++) {
      buffer[i] = data[i];
    }
    */
  }
}


function MicrophoneAudio(context)
{
  var that = this;

  that.context = context;

  that.connect = function (destination)
  {
    navigator.getUserMedia = navigator.getUserMedia || navigator.webkitGetUserMedia || navigator.mozGetUserMedia;

    if (navigator.getUserMedia) {
      navigator.getUserMedia({ audio: true, video: false },
        function (stream) {
          //var audioTracks = stream.getAudioTracks();
          stream.onended = function() {
            console.log('Stream ended');
          };

          that.source = that.context.createMediaStreamSource(stream);
          that.source.connect(destination);
          //that.source.connect(that.context.destination);
        },
        function (err) {
          console.log("The following error occured: " + err.name);
        });
    } else {
      console.log("getUserMedia not supported");
    }
  }

  that.disconnect = function ()
  {
    that.source.disconnect();
  }

  return that;
}


function AudioEncoder(rate)
{
  this.factor = this.getRateFactor(rate);
  this.sampleSize = 2048 * this.factor;
}
AudioEncoder.prototype = {
  getRateFactor: function (rate)
  {
    if (rate == '44100')
      return 1;
    else if (rate == '22050')
      return 2;
    else if (rate == '11025')
      return 4;
  }
}


function PCMEncoder(rate)
{
  AudioEncoder.call(this, rate);
  this.blockSize = (this.sampleSize / this.factor) * 2;
}
PCMEncoder.prototype = new AudioEncoder();

PCMEncoder.prototype.encodeBuffer = function(buffer)
{
  var pcm = new Int16Array(buffer.length / this.factor);
  for (var i = 0, j = 0; i < buffer.length; i++, j += this.factor) {
    pcm[i] = buffer[j] * 32767;
  }
  return pcm;
}

PCMEncoder.prototype.decodeBuffer = function(buffer)
{
  var pcm = new Int16Array(buffer);
  var data = new Float32Array(pcm.length / this.factor);
  for (var i = 0, j = 0; i < pcm.length; i++, j += this.factor) {
    for (var k = 0; k < this.factor; k++) {
      data[j + k] = pcm[i] / 32767;
    }
  }
  return data;
}


function AlawEncoder(rate)
{
  AudioEncoder.call(this, rate);
  this.blockSize = this.sampleSize / this.factor;
}
AlawEncoder.prototype = new AudioEncoder();

AlawEncoder.prototype.encodeBuffer = function(buffer)
{
  // TODO not done
  var pcm = new Int16Array(buffer.length / this.factor);
  for (var i = 0, j = 0; i < buffer.length; i++, j += this.factor) {
    pcm[i] = buffer[j] * 32767;
  }
  return pcm;
}

AlawEncoder.prototype.decodeBuffer = function(buffer)
{
  var alaw = new Uint8Array(buffer);
  var data = new Float32Array(alaw.length / this.factor);
  for (var i = 0, j = 0; i < alaw.length; i++, j += this.factor) {
    for (var k = 0; k < this.factor; k++) {
      data[j + k] = AlawEncoder.prototype.decodeTable[alaw[i]];
    }
  }
  return data;
}

AlawEncoder.prototype.encodeTable = [
  1,1,2,2,3,3,3,3,
  4,4,4,4,4,4,4,4,
  5,5,5,5,5,5,5,5,
  5,5,5,5,5,5,5,5,
  6,6,6,6,6,6,6,6,
  6,6,6,6,6,6,6,6,
  6,6,6,6,6,6,6,6,
  6,6,6,6,6,6,6,6,
  7,7,7,7,7,7,7,7,
  7,7,7,7,7,7,7,7,
  7,7,7,7,7,7,7,7,
  7,7,7,7,7,7,7,7,
  7,7,7,7,7,7,7,7,
  7,7,7,7,7,7,7,7,
  7,7,7,7,7,7,7,7,
  7,7,7,7,7,7,7,7
]

AlawEncoder.prototype.decodeTable = [
  -0.16797387615588855,   -0.16016113773003327,   -0.1835993530075991,   -0.17578661458174383,  -0.13672292245246742,   -0.12891018402661214,    -0.15234839930417798,   -0.1445356608783227, 
  -0.2304757835627308,    -0.22266304513687551,   -0.24610126041444136,  -0.23828852198858608,  -0.19922482985930967,   -0.1914120914334544,     -0.21485030671102023,   -0.20703756828516495, 
  -0.08398693807794427,   -0.08008056886501663,   -0.09179967650379955,  -0.08789330729087191,  -0.06836146122623371,   -0.06445509201330607,    -0.07617419965208899,   -0.07226783043916135, 
  -0.1152378917813654,    -0.11133152256843776,   -0.12305063020722068,  -0.11914426099429304,  -0.09961241492965484,   -0.0957060457167272,     -0.10742515335551012,   -0.10351878414258248, 
  -0.6718955046235542,    -0.6406445509201331,    -0.7343974120303964,   -0.7031464583269753,   -0.5468916898098697,    -0.5156407361064486,     -0.6093935972167119,    -0.5781426435132908, 
  -0.9219031342509232,    -0.8906521805475021,    -0.9844050416577654,   -0.9531540879543443,   -0.7968993194372387,    -0.7656483657338176,     -0.8594012268440809,    -0.8281502731406598, 
  -0.3359477523117771,    -0.32032227546006653,   -0.3671987060151982,   -0.35157322916348765,  -0.27344584490493484,   -0.2578203680532243,     -0.30469679860835597,   -0.2890713217566454, 
  -0.4609515671254616,    -0.44532609027375103,   -0.4922025208288827,   -0.47657704397717215,  -0.39844965971861934,   -0.3828241828669088,     -0.42970061342204047,   -0.4140751365703299, 
  -0.010498367259743034,  -0.010010071108127079,  -0.011474959562974944, -0.01098666341135899,  -0.008545182653279214,  -0.008056886501663259,   -0.009521774956511124,  -0.009033478804895169, 
  -0.014404736472670675,  -0.01391644032105472,   -0.015381328775902585, -0.01489303262428663,  -0.012451551866206854,  -0.0119632557145909,     -0.013428144169438765,  -0.01293984801782281, 
  -0.002685628833887753,  -0.002197332682271798,  -0.003662221137119663, -0.003173924985503708, -0.0007324442274239326, -0.00024414807580797754, -0.0017090365306558428, -0.0012207403790398877, 
  -0.0065919980468153935, -0.0061037018951994385, -0.007568590350047304, -0.007080294198431349, -0.004638813440351573,  -0.004150517288735618,   -0.005615405743583483,  -0.005127109591967528, 
  -0.04199346903897214,   -0.040040284432508316,  -0.04589983825189978,  -0.04394665364543596,  -0.034180730613116855,  -0.032227546006653035,   -0.038087099826044496,  -0.036133915219580676, 
  -0.0576189458906827,    -0.05566576128421888,   -0.06152531510361034,  -0.05957213049714652,  -0.04980620746482742,   -0.0478530228583636,     -0.05371257667775506,   -0.05175939207129124, 
  -0.02099673451948607,   -0.020020142216254158,  -0.02294991912594989,  -0.02197332682271798,  -0.017090365306558428,  -0.016113773003326518,   -0.019043549913022248,  -0.018066957609790338, 
  -0.02880947294534135,   -0.02783288064210944,   -0.03076265755180517,  -0.02978606524857326,  -0.02490310373241371,   -0.0239265114291818,     -0.02685628833887753,   -0.02587969603564562, 
  0.16797387615588855,     0.16016113773003327,    0.1835993530075991,    0.17578661458174383,   0.13672292245246742,    0.12891018402661214,     0.15234839930417798,    0.1445356608783227, 
  0.2304757835627308,      0.22266304513687551,    0.24610126041444136,   0.23828852198858608,   0.19922482985930967,    0.1914120914334544,      0.21485030671102023,    0.20703756828516495, 
  0.08398693807794427,     0.08008056886501663,    0.09179967650379955,   0.08789330729087191,   0.06836146122623371,    0.06445509201330607,     0.07617419965208899,    0.07226783043916135, 
  0.1152378917813654,      0.11133152256843776,    0.12305063020722068,   0.11914426099429304,   0.09961241492965484,    0.0957060457167272,      0.10742515335551012,    0.10351878414258248, 
  0.6718955046235542,      0.6406445509201331,     0.7343974120303964,    0.7031464583269753,    0.5468916898098697,     0.5156407361064486,      0.6093935972167119,     0.5781426435132908, 
  0.9219031342509232,      0.8906521805475021,     0.9844050416577654,    0.9531540879543443,    0.7968993194372387,     0.7656483657338176,      0.8594012268440809,     0.8281502731406598, 
  0.3359477523117771,      0.32032227546006653,    0.3671987060151982,    0.35157322916348765,   0.27344584490493484,    0.2578203680532243,      0.30469679860835597,    0.2890713217566454, 
  0.4609515671254616,      0.44532609027375103,    0.4922025208288827,    0.47657704397717215,   0.39844965971861934,    0.3828241828669088,      0.42970061342204047,    0.4140751365703299, 
  0.010498367259743034,    0.010010071108127079,   0.011474959562974944,  0.01098666341135899,   0.008545182653279214,   0.008056886501663259,    0.009521774956511124,   0.009033478804895169, 
  0.014404736472670675,    0.01391644032105472,    0.015381328775902585,  0.01489303262428663,   0.012451551866206854,   0.0119632557145909,      0.013428144169438765,   0.01293984801782281, 
  0.002685628833887753,    0.002197332682271798,   0.003662221137119663,  0.003173924985503708,  0.0007324442274239326,  0.00024414807580797754,  0.0017090365306558428,  0.0012207403790398877, 
  0.0065919980468153935,   0.0061037018951994385,  0.007568590350047304,  0.007080294198431349,  0.004638813440351573,   0.004150517288735618,    0.005615405743583483,   0.005127109591967528, 
  0.04199346903897214,     0.040040284432508316,   0.04589983825189978,   0.04394665364543596,   0.034180730613116855,   0.032227546006653035,    0.038087099826044496,   0.036133915219580676, 
  0.0576189458906827,      0.05566576128421888,    0.06152531510361034,   0.05957213049714652,   0.04980620746482742,    0.0478530228583636,      0.05371257667775506,    0.05175939207129124, 
  0.02099673451948607,     0.020020142216254158,   0.02294991912594989,   0.02197332682271798,   0.017090365306558428,   0.016113773003326518,    0.019043549913022248,   0.018066957609790338, 
  0.02880947294534135,     0.02783288064210944,    0.03076265755180517,   0.02978606524857326,   0.02490310373241371,    0.0239265114291818,      0.02685628833887753,    0.02587969603564562
]


Stream.connect = function ()
{
    if (!Stream.context)
      Stream.context = new (window.AudioContext || window.webkitAudioContext)();

    if (!Stream.server) {
      Stream.server = new ServerConnection(Stream.context);
      Stream.server.connect();
    }
    Stream.updateButtonState(true);
}

Stream.disconnect = function ()
{
    if (Stream.server) {
      Stream.server.disconnect();
      Stream.server = undefined;
    }

    //if (context) {
    //  context.close();
    //  context = undefined;
    //}
    Stream.updateButtonState(false);
}

Stream.updateButtonState = function (connected)
{
  if (connected) {
    $('#mic-mode').attr('disabled', true);
    $('#mic-rate').attr('disabled', true);
    $('#mic-encoding').attr('disabled', true);

    $('#mic-connect').attr('disabled', true);
    $('#mic-disconnect').removeAttr('disabled');
  }
  else {
    $('#mic-mode').removeAttr('disabled');
    $('#mic-rate').removeAttr('disabled');
    $('#mic-encoding').removeAttr('disabled');

    $('#mic-connect').removeAttr('disabled');
    $('#mic-disconnect').attr('disabled', true);
  }
}

Stream.mixerMicChange = function(event, ui)
{
  if (Stream.server) {
    Stream.server.send_message({
      'type': 'volume',
      'volume': $('#mixer-mic .mixer-volume').slider('value')
    });
  }
}

Stream.muteMic = function()
{
  if (Stream.server) {
    Stream.server.send_message({
      'type': 'mute'
    });
  }
}

Stream.handle_message = function (msg)
{

  if (msg.type == 'mic-status') {
    $('#mixer-mic .mixer-volume').slider('value', msg.volume);
    if (msg.mute)
      $('#mixer-mic .mixer-mute').addClass('muted');
    else
      $('#mixer-mic .mixer-mute').removeClass('muted');
  }

}



$(document).ready(function()
{

  Stream.updateButtonState(false);
  $('#mic-connect').click(function () { Stream.connect(); });
  $('#mic-disconnect').click(function () { Stream.disconnect(); });

  $('#mixer-mic .mixer-volume').slider({
    orientation: 'vertical',
    min: 0,
    max: 100,
    step: 1,
    slide: Stream.mixerMicChange
  });
  $('#mixer-mic .mixer-mute').click(function () { Stream.muteMic(); });

  $('#mixer-something .mixer-volume').slider({
    orientation: 'vertical',
    min: 0,
    max: 100,
    step: 1,
    slide: Stream.mixerMicChange
  });
  $('#mixer-something .mixer-mute').click(function () { Stream.muteMic(); });
});


$(document, window).on('beforeunload', function()
{
  Stream.disconnect();
});
