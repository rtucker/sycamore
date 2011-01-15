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
    // Use the each() method to gain access to each elements attributes
    $('#content div[class="rccomment"]').each(function()
    {
        $(this).qtip(
        {
            content: {
                text: '<center><img src="/wiki/throbber.gif" alt="Loading..." /></center>',
                url: '/wiki/cgi/revipbox.py',
                data: { ip: $(this).attr('title'), short: 1 },
                title: {
                    text: 'IP Information - ' + $(this).attr('title')
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

