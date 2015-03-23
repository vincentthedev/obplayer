Site = new Object();

Site.fullscreen = function()
{
  
  $('#command_fullscreen').val('Fullscreen');

  $.get('/command/fstoggle',{},function(response)
  {
    $('#command_fullscreen').val('Fullscreen ('+response.fullscreen+')');
  },'json');
}

Site.quit = function()
{
  $('#command_quit').val('Quitting...');

  $.get('/command/restart',{},function(response)
  {
    $('#command_quit').attr('onclick','');
    Site.quitInterval = setInterval(Site.quitCountdown, 1000);
  },'json');
}

Site.quitCountdownCount = 10;
Site.quitCountdown = function()
{
  Site.quitCountdownCount--;
  $('#command_quit').val('Quitting ('+Site.quitCountdownCount+')');

  if(Site.quitCountdownCount==0)
  {
    clearInterval(Site.quitInterval);
    location.reload(true);
  }

}

Site.save = function(section)
{

  var postfields = {};

  $('#notice').hide();
  $('#error').hide();

  $('#content-'+section+' .settings input').add('#content-'+section+' .settings select').each(function(index,element)
  {
    if($(element).attr('name')=='save') return; // ignore 'save' button.

    if($(element).attr('type')=='checkbox') var value = ($(element).is(':checked') ? 1 : 0);
    else var value = $(element).val();

    postfields[$(element).attr('name')] = value;	
  });

  $.post('/save',postfields,Site.saveSuccess,'json');

}

Site.saveSuccess = function(response)
{
  if(response.status) $('#notice').text('Settings saved.').show();
  else $('#error').text(response.error).show();
}

Site.injectAlert = function()
{
  test_alert=$('#test_alert_select').val();

  $.post('/alerts/inject_test',{'alert':test_alert},function(response)
  {
    if(response.status) $('#notice').text('Settings saved.').show();
    else $('#error').text(response.error).show();
  },'json');
}

Site.cancelAlert = function()
{
  var ids = [ ];

  $('#active-alerts input').each(function(index,element)
  {
    if($(element).is(':checked'))
      ids.push($(element).attr('name'));
  });

  if(ids.length>0){
    $.post('/alerts/cancel',{'identifier[]':ids},function(response)
    {
      if(response.status) $('#notice').text('Settings saved.').show();
      else $('#error').text(response.error).show();
    },'json');
  }
}

Site.updateAlertInfo = function()
{
  if ($('#tabs .tab[data-content="alerts"]').hasClass('selected')){
    $.post('/alerts/list',{},function(response,status)
    {
      if(response.active.length){
	var alerts = response.active;
	var existing = $('#active-alerts');
	var alert_list = [ ];
	alert_list.push('<tr><th class="fit">Cancel</th><th>Sender</th><th>Times Played</th><th>Headline</th></tr>');
	for(var key in alerts){
	  var row;
	  row = '<tr>';
	  row += '<td class="fit"><input type="checkbox" name="'+alerts[key].identifier+'" value="1" '+ ( $(existing).find('[name="'+alerts[key].identifier+'"]').is(':checked') ? 'checked' : '' ) +'/></td>';
	  row += '<td>'+alerts[key].sender+'<br />'+alerts[key].identifier+'<br />'+alerts[key].sent+'</td>';
	  row += '<td class="center">' + alerts[key].played + '</td>';
	  row += '<td><div class="headline" data-id="'+alerts[key].identifier+'">'+alerts[key].headline+'</div><div>'+alerts[key].description+'</div></td>';
	  row += '</tr>';
	  alert_list.push(row);
	}
	$('#active-alerts').html(alert_list);
      }
      else{
	$('#active-alerts').html($('<tr><td>').html("No Active Alerts"));
      }

      if(response.expired.length){
	var alerts = response.expired;
	var alert_list = [ ];
	alert_list.push('<tr><th>Sender</th><th>Times Played</th><th>Description</th></tr>');
	for(var key in alerts){
	  var row;
	  row = '<tr>';
	  row += '<td>'+alerts[key].sender+'<br />'+alerts[key].identifier+'<br />'+alerts[key].sent+'</td>';
	  row += '<td class="center">'+alerts[key].played+'</td>';
	  row += '<td><div class="headline" data-id="'+alerts[key].identifier+'">'+alerts[key].headline+'</div><div>'+alerts[key].description+'</div></td>';
	  row += '</tr>';
	  alert_list.push(row);
	}
	$('#expired-alerts').html(alert_list);
      }
      else{
	$('#expired-alerts').html($('<tr><td>').html("No Expired Alerts"));
      }

      // display the last time a heartbeat was received
      if(response.last_heartbeat==0){
	$('#alerts-last-heartbeat').html('(none received)');
	$('#alerts-last-heartbeat').css('color','red');
      }
      else{
	var elapsed = (Date.now() / 1000) - response.last_heartbeat;
	$('#alerts-last-heartbeat').html(Site.friendlyDuration(elapsed) + " min");
	if(elapsed>150) $('#alerts-last-heartbeat').css('color','red');
	else $('#alerts-last-heartbeat').css('color','black');
      }

      // display the next time alerts will be played
      var next_check = response.next_play - (Date.now() / 1000);
      $('#alerts-next-play').html(Site.friendlyDuration(next_check) + " min");
    },'json').error(function()
    {
      $('#alerts-last-heartbeat').html("");
      $('#alerts-next-play').html("");

      $('#active-alerts').html('<span style="color: red; font-weight: bold;">(connection to player lost)</span>');
      $('#expired-alerts').html('<span style="color: red; font-weight: bold;">(connection to player lost)</span>');
    });
  }
}

Site.updateStatusInfo = function()
{
  if($('#tabs .tab[data-content="status"]').hasClass('selected')){
    $.post('/status_info',{},function(response,status)
    {

      if(response.show){
	$('#show-summary-time').html(Site.friendlyTime(response.time));
	$('#show-summary-uptime').html(response.uptime);
	$('#show-summary-type').html(response.show.type);
	$('#show-summary-id').html(response.show.id);
	$('#show-summary-name').html(response.show.name);
	$('#show-summary-description').html(response.show.description);
	$('#show-summary-last-updated').html(Site.friendlyTime(response.show.last_updated));
      }

      if(response.audio){
	$('#audio-summary-media-type').html(response.audio.media_type);
	$('#audio-summary-order-num').html(response.audio.order_num);
	$('#audio-summary-media-id').html(response.audio.media_id);
	$('#audio-summary-artist').html(response.audio.artist);
	$('#audio-summary-title').html(response.audio.title);
	$('#audio-summary-duration').html(Site.friendlyDuration(response.audio.duration));
	$('#audio-summary-end-time').html(Site.friendlyTime(response.audio.end_time));
	Site.drawAudioMeter(response.audio_levels);
      }

      if(response.visual){
	$('#visual-summary-media-type').html(response.visual.media_type);
	$('#visual-summary-order-num').html(response.visual.order_num);
	$('#visual-summary-media-id').html(response.visual.media_id);
	$('#visual-summary-artist').html(response.visual.artist);
	$('#visual-summary-title').html(response.visual.title);
	$('#visual-summary-duration').html(Site.friendlyDuration(response.visual.duration));
	$('#visual-summary-end-time').html(Site.friendlyTime(response.visual.end_time));
      }

      Site.formatLogs(response.logs);
    },'json').error(function()
    {
      $('#log-data').html('<span style="color: red; font-weight: bold;">(connection to player lost)</span>');
    });
  }
}

Site.formatLogs = function(lines)
{
  var scroll = false;
  var logdiv = $('#log-data')[0];
  var log_level = $('#log_level').val();

  if(logdiv.scrollTop == logdiv.scrollTopMax) scroll=true;

  for(var i=0; i<lines.length; i++)
  {
    lines[i] = lines[i].replace(/\</g,'&lt;');
    lines[i] = lines[i].replace(/\>/g,'&gt;');
    lines[i] = lines[i].replace(/\&/g,'&amp;');

    if(lines[i].search('\\\[error\\\]')>0) lines[i] = '<span style="color: #550000;">'+lines[i]+'</span>';
    else if(lines[i].search('\\\[player\\\]')>0) lines[i] = '<span style="color: #005500;">'+lines[i]+'</span>';
    else if(lines[i].search('\\\[data\\\]')>0) lines[i] = '<span style="color: #333333;">'+lines[i]+'</span>';
    else if(lines[i].search('\\\[emerg\\\]')>0) lines[i] = '<span style="color: #550000;">'+lines[i]+'</span>';
    else if(lines[i].search('\\\[scheduler\\\]')>0) lines[i] = '<span style="color: #005555;">'+lines[i]+'</span>';
    else if(lines[i].search('\\\[sync\\\]')>0) lines[i] = '<span style="color: #000055;">'+lines[i]+'</span>';
    else if(lines[i].search('\\\[sync download\\\]')>0) lines[i] = '<span style="color: #AA4400;">'+lines[i]+'</span>';
    else if(lines[i].search('\\\[admin\\\]')>0) lines[i] = '<span style="color: #333300;">'+lines[i]+'</span>';
    else if(lines[i].search('\\\[live\\\]')>0) lines[i] = '<span style="color: #333300;">'+lines[i]+'</span>';
    else if(lines[i].search('\\[debug\\]')>0)
    {
      if(log_level=='debug') lines[i] = '<span style="color: #008000;">'+lines[i]+'</span>';
      else {
	lines.splice(i, 1);
	i -= 1;
      }
    }
  }
  $('#log-data').html(lines.join('<br />\n'));
  if(scroll) logdiv.scrollTop = logdiv.scrollHeight;
}

Site.drawAudioMeter = function(levels)
{
  var canvas = $('#audio-levels')[0];
  var c = canvas.getContext('2d');
  var channels = levels.length;

  c.clearRect(0, 0, canvas.width, canvas.height);

  gradient = c.createLinearGradient(0, 0, canvas.width, 0);
  gradient.addColorStop(0, "green");
  gradient.addColorStop(1, "red");
  c.fillStyle = gradient;

  for(var i=0; i<channels; i++) {
    //c.fillRect(0, i * (canvas.height / channels), levels[i] * canvas.width, canvas.height / channels);
    c.fillRect(0, i * (canvas.height / channels), canvas.width + (levels[i] * (canvas.width / 100) ), canvas.height / channels);
  }
}

// convert seconds to friendly duration
Site.friendlyDuration = function(secs)
{

  secs = Math.floor(secs);

  var hours = Math.floor(secs/60/60);
  secs -= hours*60*60;

  var minutes = Math.floor(secs/60);
  secs -= minutes*60;

  var seconds = Math.round(secs);

  if(hours<10) hours = '0'+hours;
  if(minutes<10) minutes = '0'+minutes;
  if(seconds<10) seconds = '0'+seconds;

  var friendly_duration = minutes+':'+seconds;
  if(hours>0) friendly_duration = hours+':'+friendly_duration;

  return friendly_duration;
}

// convert unix timestamp (in seconds) to friendly time
Site.friendlyTime = function(timestamp)
{
  var date = new Date(timestamp*1000);
  var hours = date.getHours();
  var minutes = date.getMinutes();
  var seconds = date.getSeconds();

  if(hours<10) hours = '0'+hours;
  if(minutes<10) minutes = '0'+minutes;
  if(seconds<10) seconds = '0'+seconds;

  return hours+':'+minutes+':'+seconds;
}

$(document).ready(function()
{

  // hide some home page (setting list) settings, if not applicable.
  if($('#sync_mode_value').text()=='remote') $('.local_media_location').hide();
  if($('#sync_mode_value').text()!='backup') $('.backup_media').hide();
  if($('#https_setting').text()=='False') $('.ssl_certificate').hide();

  $('.tab').click(function()
  {
    $('#content > div').hide();
    $('#content-'+$(this).attr('data-content')).show();

    $('.tab').removeClass('selected');
    $(this).addClass('selected');

    if($(this).attr('data-content')=='alerts') Site.updateAlertInfo();
    if($(this).attr('data-content')=='status') Site.updateStatusInfo();
  });

  $('#sync_media_mode').change(function()
  {
    $('.sync_display_adjust').hide();
    $('.sync_display_adjust.sync_'+$('#sync_media_mode').val()).show();
  });
  $('#sync_media_mode').change();

  $('#audio_out_mode_select').change(function()
  {
    if($('#audio_out_mode_select').val()=='alsa') $('#audio_out_alsa_device_row').show();
    else $('#audio_out_alsa_device_row').hide();

    if($('#audio_out_mode_select').val()=='jack') $('#audio_out_jack_name_row').show();
    else $('#audio_out_jack_name_row').hide();
  });
  $('#audio_out_mode_select').change();

  $('#audio_in_mode_select').change(function()
  {
    if($('#audio_in_mode_select').val()=='alsa') $('#audio_in_alsa_device_row').show();
    else $('#audio_in_alsa_device_row').hide();

    if($('#audio_in_mode_select').val()=='jack') $('#audio_in_jack_name_row').show();
    else $('#audio_in_jack_name_row').hide();
  });
  $('#audio_out_mode_select').change();

  $('#http_admin_secure').change(function()
  {
    if($(this).is(':checked')) $('#http_admin_sslcert_row').show();
    else $('#http_admin_sslcert_row').hide();
  });
  $('#http_admin_secure').change();

  Site.updateAlertInfoInterval = setInterval(Site.updateAlertInfo, 2000);
  Site.updateAlertInfo();

  Site.updateStatusInfoInterval = setInterval(Site.updateStatusInfo, 1000);
  Site.updateStatusInfo();
  $('#log_level').change(Site.updateStatusInfo);

  $('#alerts_inject_button').click(Site.injectAlert);
  $('#alerts_cancel_button').click(Site.cancelAlert);

  $('#active-alerts, #expired-alerts').delegate('.headline', 'click', function (e) {
    var id = $(this).attr('data-id');
    window.open('/alertdetails.html?id='+id, '_blank', "width=500, height=600, scrollbars=1, menubar=0, toolbar=0, titlebar=0");
  });
});
