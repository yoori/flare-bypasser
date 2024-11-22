import distutils.core


def is_installed(pkgname):
  try:
    import cv2 # noqa
    return True
  except Exception:
    return False


install_requires = [
  'asyncio',
  'uuid',
  'urllib3',
  'numpy',
  'certifi==2024.8.30',
  'websockets==14.0',
  'zendriver_flare_bypasser',
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
