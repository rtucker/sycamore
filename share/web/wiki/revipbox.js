// Create the tooltips only on document load
$(document).ready(function() 
{
    // Use the each() method to gain access to each elements attributes
    $('a[tooltip]').each(function()
    {
        $(this).qtip(
        {
            content: {
                text: '<center><img src="/wiki/throbber.gif" alt="Loading..." /></center>',
                url: '/wiki/cgi/revipbox.py',
                data: { ip: $(this).attr('tooltip') },
                title: {
                    text: 'IP Information - ' + $(this).attr('tooltip')
                }
            },
            position: {
                corner: {
                    target: 'bottomMiddle', // Position the tooltip above the link
                    tooltip: 'topMiddle'
                },
            },
            style: {
                border: {
                    width: 0,
                    radius: 4
                },
                tip: true,
                name: 'light',
                width: 570
            }
        })
    });

    // Recent changes page
    $('#content span[class="rceditor"]').each(function()
    {
        // nuke superfluous title overlays
        $(this).removeAttr("title");
        $(this).parent(".rccomment").removeAttr("title");
        // grab the editor's name from the link within
        var editor = $(this).contents().html();

        $(this).qtip(
        {
            content: {
                text: '<center><img src="/wiki/throbber.gif" alt="Loading..." /></center>',
                url: '/wiki/cgi/revipbox.py',
                data: { ip: $(this).attr('ip'), short: 1 },
                title: {
                    text: 'Edited by ' + editor + ' from ' + $(this).attr('ip')
                }
            },
            position: {
                corner: {
                    target: 'bottomLeft', // Position the tooltip above the link
                    tooltip: 'topLeft'
                },
            },
            style: {
                border: {
                    width: 0,
                    radius: 4
                },
                tip: true,
                name: 'light',
                width: 400
            }
        })
    });
});

