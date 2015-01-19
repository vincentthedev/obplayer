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

  $.post('/inject_alert',{'alert':test_alert},function(response)
  {
    // we don't need no stinking response
  },'json');
}

Site.displayAlerts = function()
{
  $.post('/get_alerts',{},function(response)
  {
    $('#active-alerts').html(response);
  },'html');
}

Site.logUpdate = function(response)
{
  $.get('/logs.html',{},function(response)
  {
    var debug = $('#log-debug').is(':checked');
    var lines = response.split('\n');
    for(var i=0; i<lines.length; i++)
    {
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
        else lines[i] = "";
      }
    }
    $('#log-data').html(lines.join('\n'));
    $('#log-data')[0].scrollTop = $('#log-data')[0].scrollHeight;
  },'html');
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

  Site.displayAlertsInterval = setInterval(Site.displayAlerts, 5000);
  Site.displayAlerts();

  Site.logInterval = setInterval(Site.logUpdate, 5000);
  Site.logUpdate();
  $('#log-debug').change(Site.logUpdate);

});
