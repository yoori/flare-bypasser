import sys
import os
import importlib
import setuptools


# Trick for avoid installation of non pip installed packages (apt), available by ADDITIONAL_PYTHONPATH
def is_installed(pkgname):
  try:
    m = importlib.import_module(pkgname)
    return m is not None
  except Exception:
    pass
  return False


if "ADDITIONAL_PYTHONPATH" in os.environ:
  add_path = os.environ["ADDITIONAL_PYTHONPATH"]
  sys.path += add_path.split(':')

install_requires = [
  'asyncio',
  'uuid',
  'urllib3',
  'httpx',
  'argparse',
  'oslex',
  'jinja2',

  'xvfbwrapper==0.2.9 ; platform_system != "Windows"',

  # Server dependecies
  'fastapi',
  'uvicorn',
  'gunicorn ; platform_system != "Windows"',
]

nodriver_install_requires = [
  'websockets==13.0',
  'nodriver @ git+https://github.com/ultrafunkamsterdam/nodriver.git',
]

zendriver_install_requires = [
  'websockets==14.0',
  'zendriver_flare_bypasser==0.2.6.1',
]

for package_import_name, package in [('numpy', 'numpy'), ('cv2', 'opencv-python')]:
  if not is_installed(package_import_name):
    install_requires += [package]

setuptools.setup(
  install_requires=install_requires,
  extras_require={
    'nodriver': nodriver_install_requires,
    'zendriver': zendriver_install_requires,
  }
)
