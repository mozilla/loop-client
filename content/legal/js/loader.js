// Set the current translation content
function setBody(data) {
  $("#legal-copy").html(data);
}

$(document).ready(function() {
  // Get the favorite language
  var lang, defaultLang = "en-US";
  $.get(loop.config.serverUrl, function(data) {
    if (data.hasOwnProperty("i18n")) {
      lang = data.i18n.lang;
      defaultLang = data.i18n.defaultLang;
    }
    if (lang === undefined) {
      lang = defaultLang;
    }

    $.get(lang.replace("-", "_") + ".html")
      .done(function(data) {
        setBody(data);
      })
      .fail(function() {
        $.get(defaultLang.replace("-", "_") + ".html")
          .done(function(data) {
            setBody(data);
          });
      });
  });
});
