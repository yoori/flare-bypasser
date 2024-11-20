import os
import sys
import shutil
import logging
import json
import zipfile
import argparse
from urllib.request import urlretrieve, urlopen


def fetch_package(download_url):
  return urlretrieve(download_url)[0]


def unzip_package(
  fp, extract_root='/', unzip_path='/tmp/unzip_chrome',
  extract_sub_directory=''
):
  try:
    os.unlink(unzip_path)
  except (FileNotFoundError, OSError):
    pass

  os.makedirs(unzip_path, mode=0o755, exist_ok=True)

  with zipfile.ZipFile(fp, mode="r") as zf:
    zf.extractall(unzip_path)

  shutil.copytree(
    os.path.join(unzip_path, extract_sub_directory), extract_root,
    dirs_exist_ok=True)
  shutil.rmtree(unzip_path)


def download_and_install(version_prefix = None, install_root = None, arch = 'x86_64'):
  # Script can install chrome only on linux platforms and only on x86_64.
  # here no archive of versions for linux/arm64
  if arch == 'x86_64':
    target_platform = "linux64"
  else:
    raise Exception("Unknown or unsupported platform: " + str(arch))

  chrome_download_url = None
  with urlopen(
    "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
  ) as conn:
    response = conn.read().decode()
  response_json = json.loads(response)

  # If version is undefined: use max_version
  if version_prefix == '':
    version_prefix = None

  for version_obj in response_json['versions']:
    if ('version' in version_obj and 'downloads' in version_obj and (
        version_prefix is None or version_obj['version'].startswith(version_prefix))):
      downloads_obj = version_obj['downloads']
      if ('chrome' in downloads_obj):
        local_chrome_download_url = None

        for platform_obj in downloads_obj['chrome']:
          if platform_obj['platform'] == target_platform:
            local_chrome_download_url = platform_obj['url']

        if local_chrome_download_url is not None:
          chrome_download_url = local_chrome_download_url
          if version_prefix is not None:
            break

  if chrome_download_url is None:
    raise Exception("Can't find download urls")

  print("Download chrome by url: " + str(chrome_download_url), flush=True)
  extract_root = install_root if install_root is not None else '/usr/bin/'
  unzip_package(
    fetch_package(chrome_download_url), extract_root=extract_root,
    extract_sub_directory=('chrome-' + target_platform))

  os.chmod(os.path.join(extract_root, 'chrome'), 0o755)
  os.chmod(os.path.join(extract_root, 'chrome-wrapper'), 0o755)
  os.chmod(os.path.join(extract_root, 'chrome_crashpad_handler'), 0o755)
  os.chmod(os.path.join(extract_root, 'chrome_sandbox'), 0o755)

  os.system(
    "sed -i 's/Google Chrome for Testing/Google Chrome\\x00for Testing/' " +
    str(extract_root) + "/chrome")
  return True


if __name__ == "__main__":
  parser = argparse.ArgumentParser(description='linux_chrome_installer.')
  parser.add_argument("-v", "--version-prefix", type=str, default='120.')
  parser.add_argument("-i", "--install-root", type=str, default='/usr/bin')
  parser.add_argument("--arch", type=str, default='x86_64')
  args = parser.parse_args()

  try:
    res = download_and_install(
      version_prefix = args.version_prefix,
      install_root = args.install_root,
      arch = args.arch
    )
  except Exception as e:
    logging.error("Can't install chrome: " + str(e))
    sys.exit(1)
