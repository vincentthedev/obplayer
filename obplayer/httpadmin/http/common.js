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
    // we don't need no stinking response
  },'json');
}

Site.displayAlerts = function()
{
  if ($('#tabs .tab[data-content="alerts"]').hasClass('selected')){
    $.post('/alerts/list',{},function(response)
    {
      if(response.length){
	var alert_list = [ ];
	for(var key in response){
	  alert_list.push($('<div>').html(response[key]));
	}
	$('#active-alerts').html(alert_list);
      }
      else{
	$('#active-alerts').html($('<div>').html("No Active Alerts"));
      }
    },'json');
  }
}

Site.updateStatusInfo = function()
{
  if($('#tabs .tab[data-content="status"]').hasClass('selected')){
    $.post('/status_info',{},function(response)
    {

      if(response.show){
	$('#show-summary-time').html(Site.friendlyTime(response.time));
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
    },'json');
  }
}

Site.formatLogs = function(lines)
{
  var scroll = false;
  var debug = $('#log-debug').is(':checked');
  var logdiv = $('#log-data')[0];

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
    else if(lines[i].search('\\\[admin\\\]')>0) lines[i] = '<span style="color: #333300;">'+lines[i]+'</span>';
    else if(lines[i].search('\\\[live\\\]')>0) lines[i] = '<span style="color: #333300;">'+lines[i]+'</span>';
    else if(lines[i].search('\\[debug\\]')>0)
    {
      if(debug) lines[i] = '<span style="color: #008000;">'+lines[i]+'</span>';
      else {
	lines.splice(i, 1);
	i -= 1;
      }
    }
  }
  $('#log-data').html(lines.join('<br />\n'));
  if(scroll) logdiv.scrollTop = logdiv.scrollHeight;
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

    if($(this).attr('data-content')=='alerts') Site.displayAlerts();
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

  Site.displayAlertsInterval = setInterval(Site.displayAlerts, 3000);
  Site.displayAlerts();

  Site.updateStatusInfoInterval = setInterval(Site.updateStatusInfo, 3000);
  Site.updateStatusInfo();
  $('#log-debug').change(Site.updateStatusInfo);

});
