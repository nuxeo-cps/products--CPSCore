from Globals import DTMLFile
from ZServer.HTTPServer import zhttp_server
from App.Management import Navigation

zhttp_server.SERVER_IDENT += ' CPS/3.0'

manage_copyright = DTMLFile('zmi/copyright', globals())
    
Navigation.manage_copyright = manage_copyright

