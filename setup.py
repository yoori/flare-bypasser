import pkg_resources
import distutils.core

def is_installed(pkgname):
  try:
    import cv2
    return True
  except:
    return False

install_requires = [
  'asyncio',
  'uuid',
  'urllib3',
  'numpy',
  'certifi==2024.8.30',
  'websockets==14.0',
  'zendriver @ git+https://github.com/yoori/zendriver.git',
  'argparse',
  'oslex',
  'jinja2',

  # Server dependecies
  'fastapi',
  'uvicorn',

  'xvfbwrapper==0.2.9 ; platform_system != "Windows"',
  'gunicorn ; platform_system != "Windows"',
]

if not is_installed('cv2'):
  # can be installed as opencv-python or opencv-contrib-python
  install_requires += ['opencv-python']

distutils.core.setup(install_requires=install_requires)
