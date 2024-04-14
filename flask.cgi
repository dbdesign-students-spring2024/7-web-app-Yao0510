#!/home/yw4822/.local/share/virtualenvs/7-web-app-Yao0510-7KcYkFId/bin/python
import sys
#!/usr/bin/env python3
# sys.path.insert(0, '/misc/linux/centos7/x86_64/local/stow/python-3.6/lib/python3.6/site-packages/')
sys.path.insert(0, '/home/yw4822/.local/share/virtualenvs/7-web-app-Yao0510-7KcYkFId/lib/python3.9/site-packages')
from wsgiref.handlers import CGIHandler
from app import app
CGIHandler().run(app)

