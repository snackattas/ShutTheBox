# Run this command while directly outside the ShutTheBox main directory to
# run the app:
#   dev_appserver.py ShutTheBox

# Copy and paste this statement in the run terminal (ctrl+R) to test the google
# cloud endpoints locally.  There's a bug in chrome that only allows local
# testing by running chrome with these flags.  Port 8080 here is the regular
# port (not the admin port)
# "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" --incognito --user-data-dir=%TMP% --unsafely-treat-insecure-origin-as-secure=http://localhost:8080 http://localhost:8080/_ah/api/explorer

from pkg import *
from pkg.main import ShutTheBoxApi

api = endpoints.api_server([ShutTheBoxApi])
