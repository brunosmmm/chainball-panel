"""ChainBoard scoreboard controlling app."""

from kivy.app import App
from kivy.metrics import dp
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.logger import Logger
from kivy.core.window import Window
from kivymd.theming import ThemeManager
import argparse
try:
    from jnius import JavaException, autoclass
    _JAVA = True
except Exception:
    # well, just ignore if on a PC
    _JAVA = False
    pass
from root import RootWidget


class SimpleboardDebugPanel(App):
    """The app."""

    theme_cls = ThemeManager()
    title = 'ChainBoard - ChainBot Remote'
    listener = None

    def __init__(self, *args, **kwargs):
        """Initialize."""
        address = kwargs.pop('address')
        super(SimpleboardDebugPanel, self).__init__(*args, **kwargs)
        self._is_android = False

        self.root = RootWidget(address=address,
                               disable_app_cb=self.disable_app_cb,
                               enable_app_cb=self.enable_app_cb)

    def disable_app_cb(self, **kwargs):
        """Disable app callback."""
        if self._is_android:
            self.listener.start_listening(**kwargs)

    def enable_app_cb(self, **kwargs):
        """Enable app callback."""
        if self._is_android:
            self.listener.stop_listening(**kwargs)

    def set_listener(self, listener, is_android=False):
        """Set listener."""
        self.listener = listener
        self._is_android = is_android

    def post_init(self):
        """Run post-initialization tasks."""
        self.root.post_init()

    def discover_service(self, address, port, name, attr):
        """Discover scoreboard service."""
        if name == 'Chainball Scoreboard':
            Logger.info('discover: found scoreboard at {}:{}'.format(address,
                                                                     port))
            # set address
            self.root.set_discovered_address('{}:{}'.format(address, port))
            if self.root._prefmgr.network__enable_discovery:
                self.root.set_scoreboard_address('{}:{}'.format(address, port))

    def remove_service(self, name):
        """Remove service."""
        if name == 'Chainball Scoreboard':
            Logger.info('discover: scoreboard service was removed')

            # unset address
            self.root.set_discovered_address(None)

    def build(self):
        """Build application."""
        if self.listener is not None:
            self.listener.start_listening()

        Logger.info('cb_Debug: window size dp = {},{}'
                    .format(dp(Window.width),
                            dp(Window.height)))
        Logger.info('cb_Debug: window size  = {},{}'
                    .format(Window.width,
                            Window.height))
        return self.root


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('address', nargs='?')
    parser.add_argument('port', nargs='?')
    parser.set_defaults(address='1.1.1.1', port=80)

    args = parser.parse_args()

    Builder.load_file('panel.kv')
    panel = SimpleboardDebugPanel(address='http://{}:{}'.format(args.address,
                                                                args.port))

    # detect platform
    listener = None
    is_android = False
    if _JAVA is True:
        try:
            Context = autoclass('android.content.Context')
            from discover.android import AndroidListener
            Logger.info('Android detected')
            listener = AndroidListener('_http_tcp',
                                       Context,
                                       panel.discover_service,
                                       panel.remove_service)
            is_android = True
            Clock.schedule_interval(listener.discover_loop, 0.1)
        except JavaException:
            Logger.info('basic platform detected')
            from discover.linux import LinuxListener
            listener = LinuxListener('_http._tcp.local.',
                                     service_found_cb=panel.discover_service,
                                     service_removed_cb=panel.remove_service)
            # listener.start_listening()

    if listener is not None:
        panel.set_listener(listener, is_android=is_android)
    panel.post_init()
    panel.run()
