from flare_bypasser import ProxyController


def test_two_different_proxies_rent():
  proxy_controller = ProxyController(command = 'echo "Listening on {{LOCAL_PORT}}"')

  with proxy_controller.get_proxy("socks5://127.0.0.1:7777") as proxy1, \
    proxy_controller.get_proxy("socks5://127.0.0.1:7777") as proxy2 : # noqa
    assert proxy_controller.opened_proxies_count() == 1
    assert proxy1.local_port() == proxy2.local_port()

  assert proxy_controller.opened_proxies_count() == 0


def test_two_equal_proxies_rent():
  proxy_controller = ProxyController(command = 'echo "Listening on {{LOCAL_PORT}}"')

  with proxy_controller.get_proxy("socks5://127.0.0.1:7777") as proxy1, \
    proxy_controller.get_proxy("socks5://127.0.0.1:7777") as proxy2 : # noqa
    assert proxy_controller.opened_proxies_count() == 1
    assert proxy1.local_port() == proxy2.local_port()
    assert proxy1.is_alive()

  assert proxy_controller.opened_proxies_count() == 0
