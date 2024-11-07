import sys

from setuptools import setup

name = 'flare-bypasser'

setup(
  name='flare-bypasser',
  python_requires='>= 3.9',
  version='0.1.24',
  packages=["flare_bypasser"],
  package_dir={
    "": ".",
    "flare_bypasser": "./src/flare_bypasser"
  },
  url='https://github.com/yoori/flare-bypasser',
  license='GNU Lesser General Public License',
  author='yoori',
  author_email='yuri.kuznecov@gmail.com',
  description='',
  install_requires=[  # Solver dependecies
    'asyncio',
    'uuid',
    'opencv-python',
    'certifi==2023.7.22',
    'requests',  # nodriver require it
    'nodriver @ git+https://github.com/yoori/nodriver.git',
    # < fork with cookie fix, switch to https://github.com/ultrafunkamsterdam/nodriver.git after MR
    'argparse',
    'oslex',
    'jinja2',
  ] + [  # Server dependecies
    'fastapi',
    'uvicorn',
    'gunicorn'
  ] + ['xvfbwrapper==0.2.9'] if sys.platform != 'win32' else [] +
  # < we believe that 'cygwin', 'darwin' are supported in addition to 'linux'
  ['gunicorn'] if sys.platform not in ['win32', 'cygwin'] else [],
  # < gunicorn use fcntl (supported only at darwin, linux)
  include_package_data=True,
  entry_points={
    'console_scripts': [
      'flare_bypass_server=flare_bypasser:server_run',
    ]
  }
)
