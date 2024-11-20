import typing
import threading
import subprocess
import socket
import logging
import contextlib
import oslex
import jinja2

logger = logging.getLogger(__name__)


class ProxyController(object):
  _proxy_cmd_template: jinja2.Template
  _lock: threading.Lock
  _proxies_by_url: typing.Dict[str, object]  # -> ProxyHolder
  _proxies_by_port: typing.Dict[int, object]  # -> ProxyHolder

  class PortBusy(Exception):
    pass

  class NoPortForListen(Exception):
    pass

  class ProxyHolder(object):
    _proxy_storage: object  # ProxyController
    _local_port: int
    _url: str
    _ref_count: int = 0
    _start_wait: threading.Lock
    _started: bool = False
    _process = None

    # [start_port .. end_port]: localy started proxies will use ports in this interval
    def __init__(self, proxy_storage: object, local_port: int, url: str):
      self._proxy_storage = proxy_storage
      self._start_wait = threading.Lock()
      self._local_port = local_port
      self._url = url

    def add_ref(self):
      # wait start if it in progress
      with self._start_wait:
        if not self._started:
          self._proxy_storage._start_proxy(self)
          self._started = True
        self._ref_count += 1

    def remove_ref(self):
      self._ref_count -= 1
      if self._ref_count == 0:
        self._proxy_storage._close_proxy(self)

  class ProxyHolderRef(object):
    _proxy_holder: object  # ProxyController.ProxyHolder

    def __init__(self, proxy_holder: object):
      self._proxy_holder = proxy_holder
      self._proxy_holder.add_ref()

    def local_port(self):
      return self._proxy_holder._local_port

    def url(self):
      return self._proxy_holder._url

    def is_alive(self):
      return self._proxy_holder._process is not None

    def release(self):
      if self._proxy_holder:
        self._proxy_holder.remove_ref()
        self._proxy_holder = None

    def __enter__(self):
      return self

    def __exit__(self, type, value, traceback):
      self.release()
      return False

    def __del__(self):
      self.release()

  def __init__(
    self,
    start_port=10000,
    end_port=20000,
    command="gost -L=socks5://127.0.0.1:{{LOCAL_PORT}} -F='{{UPSTREAM_URL}}'"
  ):
    self._proxy_cmd_template = jinja2.Environment().from_string(command)
    self._lock = threading.Lock()
    self._proxies_by_url = {}
    self._proxies_by_port = {}
    self._start_port = start_port
    self._end_port = end_port

  def get_proxy(self, url):
    new_proxy_holder: ProxyController.ProxyHolder = None

    with self._lock:
      if url in self._proxies_by_url:
        return ProxyController.ProxyHolderRef(self._proxies_by_url[url])
      new_proxy_holder_port = self._choose_port(url)
      new_proxy_holder = ProxyController.ProxyHolder(self, new_proxy_holder_port, url)
      self._proxies_by_url[url] = new_proxy_holder
      self._proxies_by_port[new_proxy_holder_port] = new_proxy_holder

    return ProxyController.ProxyHolderRef(new_proxy_holder)
    # < Start/wait start or simple increase ref.

  def opened_proxies_count(self):
    return len(self._proxies_by_port)

  @staticmethod
  def _port_is_listen(port):
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
      try:
        result = sock.connect_ex(("127.0.0.1", port))
        return result == 0
      except socket.gaierror:
        return False

  def _choose_port(self, url):
    base_port_offset = hash(url) % (self._end_port - self._start_port + 1)
    for port_offset in range(self._end_port - self._start_port + 1):
      check_port = self._start_port + (base_port_offset + port_offset) % (
        self._end_port - self._start_port + 1)
      if check_port in self._proxies_by_port:
        continue
      if ProxyController._port_is_listen(check_port):
        raise ProxyController.PortBusy(
          "Port " + str(check_port) + " dedicated for proxy usage is busy.")
      return check_port
    raise ProxyController.NoPortForListen()

  def _start_proxy(self, proxy_holder):
    # Start proxy process
    proxy_cmd = self._proxy_cmd_template.render({
      'LOCAL_PORT': str(proxy_holder._local_port),
      'UPSTREAM_URL': proxy_holder._url})
    logger.info("Start with: " + str(proxy_cmd))
    proxy_holder._process = subprocess.Popen(
      oslex.split(proxy_cmd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

  def _close_proxy(self, proxy_holder):
    # Close proxy process
    with self._lock:
      del self._proxies_by_url[proxy_holder._url]
      del self._proxies_by_port[proxy_holder._local_port]
      if proxy_holder._process:
        logger.info("Close proxy for: " + str(proxy_holder._url))
        proxy_holder._process.kill()
        proxy_holder._process.wait()
        proxy_holder._process = None
