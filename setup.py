import sys
import os
import importlib
import distutils.core


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
  'certifi==2024.8.30',
  'websockets==14.0',
  'zendriver_flare_bypasser==0.2.0',  # 'zendriver @ git+https://github.com/yoori/zendriver.git@flare-bypasser'
  'argparse',
  'oslex',
  'jinja2',

  # Server dependecies
  'fastapi',
  'uvicorn',

  'xvfbwrapper==0.2.9 ; platform_system != "Windows"',
  'gunicorn ; platform_system != "Windows"',
]

for package_import_name, package in [('numpy', 'numpy'), ('cv2', 'opencv-python')]:
  if not is_installed(package_import_name):
    install_requires += [package]

distutils.core.setup(install_requires=install_requires)
