"""ShutTheBox.py - This is the file that starts up the Cloud Endpoints API
server.

Start the API server in a development environment by running this
command in the directory outside ShutTheBox:
    dev_appserver.py ShutTheBox/ --port=<your port>.

For help navigate here:
    https://cloud.google.com/appengine/docs/python/tools/using-local-server"""

import endpoints
from pkg.main import ShutTheBoxApi

api = endpoints.api_server([ShutTheBoxApi])
