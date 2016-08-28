"""appengine_config.py - This file contains the configuration to incorporate
the python requests 3rd party module into the Google App Engine.

Instructions here:
https://cloud.google.com/appengine/docs/python/tools/using-libraries-python-27"""
from google.appengine.ext import vendor
import os
import sys
# This is a workaround from this issue thread on google
# https://code.google.com/p/googleappengine/issues/detail?id=12852
sys.platform = 'linux3'
# Add any libraries installed in the "lib" folder.
vendor.add(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lib'))
