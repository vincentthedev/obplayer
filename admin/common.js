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

  postfields = {};

  $('#notice').hide();
  $('#error').hide();

  $('#content-'+section+' input').add('#content-'+section+' select').each(function(index,element)
  {
    if($(element).attr('name')=='save') return; // ignore 'save' button.

    if($(element).attr('type')=='checkbox') var value = ($(element).is(':checked') ? 1 : 0);
    else var value = $(element).val();

    postfields[$(element).attr('name')] = value;	
  });

  $.post('/',postfields,Site.saveSuccess,'json');

}

Site.saveSuccess = function(response)
{
  if(response.status) $('#notice').text('Settings saved.').show();
  else $('#error').text(response.error).show();
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

  $('#audio_output_select').change(function()
  {
    if($('#audio_output_select').val()=='alsa') $('#alsa_device_row').show();
    else $('#alsa_device_row').hide();

    if($('#audio_output_select').val()=='jack') $('#jack_port_name_row').show();
    else $('#jack_port_name_row').hide();
  });
  $('#audio_output_select').change();

  $('#http_admin_secure').change(function()
  {
    if($(this).is(':checked')) $('#http_admin_sslcert_row').show();
    else $('#http_admin_sslcert_row').hide();
  });
  $('#http_admin_secure').change();

});
