from google.appengine.ext import vendor
import os
import sys
# This is a workaround from this issue thread on google
# https://code.google.com/p/googleappengine/issues/detail?id=12852
sys.platform = 'linux3'
# Add any libraries installed in the "lib" folder.
vendor.add(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lib'))
