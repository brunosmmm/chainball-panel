"""ChainBoard scoreboard controlling app."""

from kivy.app import App
from kivy.metrics import dp
from kivy.uix.floatlayout import FloatLayout
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.logger import Logger

from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.core.window import Window
from kivymd.theming import ThemeManager
from kivymd.dialog import MDDialog
from kivymd.textfields import MDTextField
from kivymd.material_resources import DEVICE_TYPE
from kivymd.list import OneLineIconListItem
import argparse
from threading import Thread
from miscui import AvatarSampleWidget
from playeract import PlayerActions
import texttable
try:
    from jnius import JavaException, autoclass
    _JAVA = True
except Exception:
    # well, just ignore if on a PC
    _JAVA = False
    pass
from util.prefmgr import PrefsMgr
from util.saferequests import (safe_post, safe_get,
                               is_connection_error_exception)
import os
import re
import requests
import csv

CONFIGURATION_PATH = 'config'
PREFERENCES = 'prefs.json'


class PanelUpdater(Thread):

    def __init__(self, *args, **kwargs):
        super(PanelUpdater, self).__init__(*args)

        self.scoreboard_address = kwargs['address']
        self.root = kwargs['root']
        self.disabled = False

    def run(self):

        if self.root.stop_refreshing is True:
            return

        # try to contact scoreboard
        r = safe_get(self.root.scoreboard_address+'/status/all', timeout=1)
        if r.success is False:
            if is_connection_error_exception(r.data):
                self.root.disable_app(from_thread=True)
                return
            else:
                # some other exception, just ignore
                Logger.info('PanelUpdater: other exception caught: {}'
                            .format(r.data))
                return
        else:
            try:
                status = r.data.json()
            except Exception as ex:
                # ignore
                Logger.info('PanelUpdater: exception '
                            'caught while retriving data: {}'.format(repr(ex)))
                return

        if self.root.disconnected:
            self.root.enable_app(from_thread=True)
            self.root.one_shot_refresh()
        self.disabled = False

        # first look at board status
        json_data = status['board']
        if json_data['status'] == 'error':
            self.root._scoreboard_status = 'board_err'
            return

        # get game status
        json_data = status['game']
        if json_data['status'] == 'error':
            self.root._scoreboard_status = 'game_err'
            return

        self.root_scoreboard_status = 'ok'
        server = -1
        if json_data['game'] == 'started':
            self.root.ids['gameActStart'].disabled = True
            self.root.ids['gameActPause'].disabled = False
            self.root.ids['gameActStop'].disabled = False
            self.root.ids['gameSetupRmAll'].disabled = True
            self.root.game_running = True
            self.root.game_paused = False
            self.root._game_id = str(json_data['game_id'])
            self.root._user_id = json_data['user_id']
            server = int(json_data['serving'])
            for i in range(0, 4):
                self.root.ids['pname{}'.format(i)].disabled = False
                self.root.ids['pscore{}'.format(i)].disabled = False
                self.root.ids['pindirect{}'.format(i)].disabled = False
                self.root.ids['preferee{}'.format(i)].disabled = False
        elif json_data['game'] == 'stopped' or json_data['game'] == 'paused':
            self.root._game_id = str(json_data['game_id'])
            self.root._user_id = json_data['user_id']
            self.root.game_running = False
            if json_data['game'] == 'stopped':

                if json_data['can_start']:
                    self.root.ids['gameActStart'].disabled = False
                else:
                    self.root.ids['gameActStart'].disabled = True

                self.root.ids['gameActStop'].disabled = True
                self.root.ids['gameActPause'].disabled = True
                self.root.ids['gameSetupRmAll'].disabled = False

                self.root.game_paused = False
            else:
                self.root.game_paused = True
            for i in range(0, 4):
                self.root.ids['pname{}'.format(i)].disabled = False
                self.root.ids['pscore{}'.format(i)].disabled = True
                self.root.ids['pindirect{}'.format(i)].disabled = True
                self.root.ids['preferee{}'.format(i)].disabled = True

        json_data = status['players']
        self.root.player_num = len(json_data)
        self.root.registered_player_list = json_data
        for i in range(0, 4):
            if str(i) in json_data:
                self.root.ids['pname{}'.format(i)].text =\
                    json_data[str(i)]['web_txt']
                self.root.ids['pname{}'.format(i)].md_bg_color =\
                    self.root._original_btn_color
            else:
                self.root.ids['pname{}'.format(i)].text = ''

        json_data = status['scores']
        if json_data['status'] == 'error':
            for i in range(0, 4):
                self.root.ids['pscore{}'.format(i)].update_score('-')

        for i in range(0, 4):
            if str(i) in json_data and i < self.root.player_num:
                self.root.ids['pscore{}'
                              .format(i)].update_score(str(json_data[str(i)]))
                if int(json_data[str(i)]) == -10:
                    self.root.ids['pname{}'.format(i)].disabled = True
                    self.root.ids['pscore{}'.format(i)].disabled = True
                    self.root.ids['pindirect{}'.format(i)].disabled = True
                    self.root.ids['preferee{}'.format(i)].disabled = True
            elif self.root.game_running is True:
                self.root.ids['pscore{}'.format(i)].update_score('-')
                self.root.ids['pname{}'.format(i)].disabled = True
                self.root.ids['pindirect{}'.format(i)].disabled = True
                self.root.ids['preferee{}'.format(i)].disabled = True

        if server > -1:
            player_name = self.root.ids['pname{}'.format(server)].text
            self.root.ids['pname{}'.format(server)].text = player_name
            self.root.ids['pname{}'.format(server)].md_bg_color = (1, 0, 0, 1)

        json_data = status['timer']
        if 'status' in json_data:
            if json_data['status'] == 'error':
                self.root.scoreboard_update()
                return
        else:
            timer_txt = '{:0>2d}'.format(json_data['minutes']) + ':' +\
                        '{:0>2d}'.format(json_data['seconds'])
            self.root.ids['timerlabel'].text = timer_txt
            self.root.scoreboard_update()


class RootWidget(FloatLayout):

    def __init__(self, *args, **kwargs):
        # pop kwargs!!!
        address = kwargs.pop('address')
        self._waiting_init = True
        self._disable_cb = kwargs.pop('disable_app_cb')
        self._enable_cb = kwargs.pop('enable_app_cb')
        super(RootWidget, self).__init__(*args, **kwargs)

        # widget default data, etc, read from kv
        self._widget_strings = {}

        # scoreboard data
        self.sfx_list = {}
        self.sfx_reverse_list = {}
        self.game_persist_list = []
        self.registered_player_list = []

        # flags
        self.stop_refreshing = False
        self.pbubb_open = False
        self.pbubb_player = None
        self.game_running = False
        self.game_paused = False
        self.disconnected = True

        # other
        self._game_id = None
        self._user_id = None
        self._scoreboard_status = 'ok'
        self._sfx_widgets = []

        self.scoreboard_address = address
        self._unformatted_address = None
        self._discovered_address = None

        # preferences
        self._prefmgr = PrefsMgr(os.path.join(CONFIGURATION_PATH, PREFERENCES))
        self._load_configuration_values()
        self._initialize_widgets()

        Clock.schedule_interval(self.refresh_status, 1)

    def _initialize_widgets(self):

        # do stuff that needs to be done upon initialization
        self._original_btn_color = self.ids['pname0'].md_bg_color[::]

        # remove default string in game status bar
        self._widget_strings['gameStatusBar'] = self.ids['gameStatusBar'].title
        self.ids['gameStatusBar'].title = ''

        # horrible hack for now
        if DEVICE_TYPE == 'mobile':

            self.ids['playerEvtLabel'].font_style = 'Body2'
            self.ids['playerScoreLabel'].font_style = 'Body2'
            self.ids['playerColLabel'].font_style = 'Body2'
            self.ids['playerCtlLabel'].font_style = 'Body2'

            # reduce button size to dp(60)
            for i in range(4):
                for j in range(8):
                    self.ids['refBtn_{}_{}'.format(i, j)].width = dp(60)

            self.ids['preferee0'].spacing = dp(5)
            self.ids['preferee1'].spacing = dp(5)
            self.ids['preferee2'].spacing = dp(5)
            self.ids['preferee3'].spacing = dp(5)
            self.ids['playerEvtBox'].spacing = dp(5)

            dp_proportion = dp(Window.height) / float(Window.height)
            Logger.info('cb_debug: dp_proportion = {}'.format(dp_proportion))

            if dp_proportion > 2.0:
                self.ids['remainingTime'].font_style = 'Title'
                self.ids['timerlabel'].font_style = 'Title'
                self.ids['gameActItem'].title = ''
                self.ids['gameSetupItem'].title = ''
                self.ids['gameActStart'].text = 'Start'
                self.ids['gameActStop'].text = 'Stop'
                self.ids['gameActPause'].text = 'Pause'
                self.ids['gameSetupRmAll'].text = 'Remove\nPlayers'
                self.ids['gameSetupRmAll'].height = dp(56)
                self.ids['gameAssignId'].text = 'Assign\nID'
                self.ids['gameAssignId'].height = dp(56)
                self.ids['gameOverridePairing'].text = 'Override\nPairing'

                self.ids['pindirect0'].spacing = dp(2)
                self.ids['pindirect1'].spacing = dp(2)
                self.ids['pindirect2'].spacing = dp(2)
                self.ids['pindirect3'].spacing = dp(2)

                self.ids['gameStatusBar'].height = dp(32)
                self.ids['maintoolbar'].height = dp(32)

                self.ids['playerListBox'].spacing = dp(5)
                self.ids['playerScoreBox'].spacing = dp(5)
                self.ids['playerCtlBox'].spacing = dp(5)
                self.ids['playerEvtBox'].spacing = dp(5)

                self.ids['playerSelButtons'].spacing = dp(20)
                self.ids['playerScoreButtons'].spacing = dp(20)
                self.ids['playerCtlButtons'].spacing = dp(20)

                self.ids['pIncr0'].width = dp(36)
                self.ids['pDecr0'].width = dp(36)
                self.ids['pSkip0'].width = dp(36)
                self.ids['pIncr1'].width = dp(36)
                self.ids['pDecr1'].width = dp(36)
                self.ids['pSkip1'].width = dp(36)
                self.ids['pIncr2'].width = dp(36)
                self.ids['pDecr2'].width = dp(36)
                self.ids['pSkip2'].width = dp(36)
                self.ids['pIncr3'].width = dp(36)
                self.ids['pDecr3'].width = dp(36)
                self.ids['pSkip3'].width = dp(36)

                self.ids['gameActionsMenu'].size_hint_x = 0.15
                self.ids['gameControlPanel'].size_hint_x = 0.85

                self.ids['preferee0'].spacing = dp(2)
                self.ids['preferee1'].spacing = dp(2)
                self.ids['preferee2'].spacing = dp(2)
                self.ids['preferee3'].spacing = dp(2)
        else:
            pass

    def _refresh_game_status_bar(self):

        if self.game_running is False:
            game_state = 'Stopped'
        else:
            if self.game_paused:
                game_state = 'Paused'
            else:
                game_state = 'Running'

        fix_game_id = int(self._game_id) - 1
        new_title = (self._widget_strings['gameStatusBar']
                     .format(internal=fix_game_id,
                             user=self._user_id,
                             state=game_state))
        self.ids['gameStatusBar'].title = new_title

    def _load_configuration_values(self):
        # modify all widgets here
        try:
            cfg_address = self._prefmgr.network__saved_address
            cfg_port = self._prefmgr.network__saved_port

            self._unformatted_address = '{}:{}'.format(cfg_address,
                                                       cfg_port)
        except:
            pass

        if self._prefmgr.network__enable_discovery:
            self.ids['autoDiscoveryBox'].state = 'down'
            self.ids['setAddressButton'].disabled = True
        else:
            self.ids['autoDiscoveryBox'].state = 'normal'
            self.ids['setAddressButton'].disabled = False
            self.set_scoreboard_address(self._unformatted_address)

    def scoreboard_update(self):
        self._refresh_game_status_bar()

    def post_init(self):
        self._waiting_init = False

    def _auto_discovery_changed(self):
        if self._waiting_init is True:
            return

        if self.ids['autoDiscoveryBox'].state == 'normal':
            self._prefmgr.network__enable_discovery = False
            self.ids['setAddressButton'].disabled = False
        else:
            self._prefmgr.network__enable_discovery = True
            self.ids['setAddressButton'].disabled = True
            if self._discovered_address is not None:
                self.set_scoreboard_address(self._discovered_address)

    def set_address_dialog(self):

        def save_apply_address(*args):

            m = re.match(r'([0-9a-zA-Z\.]+):([0-9]+)', addr_field.text)

            if m is not None:
                self.set_scoreboard_address(addr_field.text)
                dialog.dismiss()
            else:
                # don't know what to do
                pass

        addr_field = MDTextField(hint_text='adress:port')
        if self._unformatted_address is not None:
            addr_field.text = self._unformatted_address
        contents = addr_field

        dialog = MDDialog(title='Set Scoreboard Address',
                          content=contents,
                          size_hint=(0.5, 0.5),
                          auto_dismiss=True)

        dialog.add_action_button("Save & Apply",
                                 action=save_apply_address)

        dialog.open()

    def assign_game_id_dialog(self):

        def apply_game_id(*args):
            # do apply
            gid = id_field.text

            # do some processing
            if len(id_field.text) == 0:
                return

            self.assign_game_user_id(gid)
            dialog.dismiss()

        id_field = MDTextField(hint_text='Identifier')

        if self._user_id is not None:
            id_field.text = self._user_id

        dialog = MDDialog(title='Set Game Identifier',
                          content=id_field,
                          size_hint=(0.5, 0.5),
                          auto_dismiss=True)
        dialog.add_action_button('Apply',
                                 action=apply_game_id)

        dialog.open()

    def assign_game_user_id(self, user_id):

        headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
        data = {'user_id': user_id, 'game_id': self._game_id}
        r = safe_post(self.scoreboard_address+'/persist/assign_uid',
                      headers=headers,
                      data=data)
        try:
            status = r.data.json()
        except Exception:
            Logger.error('Could not set User ID')

        if status['status'] == 'error':
            Logger.error('Could not set User ID, got: {}'
                         .format(status['error']))

    def disable_app(self, **kwargs):

        self.ids['maintoolbar'].title = ('ChainBoard - Not connected'
                                         ' to Scoreboard')

        self.ids['gamectrltab'].disabled = True
        self.ids['debugtab'].disabled = True
        self.ids['saveddatatab'].disabled = True
        self.ids['gamesetuptab'].disabled = True
        self.disconnected = True

        for wid in self._sfx_widgets:
            self.ids['debugTabActions'].remove_widget(wid)

        self._disable_cb(**kwargs)

    def enable_app(self, **kwargs):

        self.ids['maintoolbar'].title = 'ChainBoard'

        self.ids['gamectrltab'].disabled = False
        self.ids['debugtab'].disabled = False
        self.ids['saveddatatab'].disabled = False
        self.ids['gamesetuptab'].disabled = False

        self.ids['debugHeader1'].disabled = True
        self.ids['debugHeader2'].disabled = True
        self.ids['debugHeader3'].disabled = True

        self.disconnected = False

        self._enable_cb(**kwargs)

    def do_pause_unpause(self, *args):
        r = safe_get(self.scoreboard_address+'/control/pauseunpause')

        try:
            status = r.data.json()
        except:
            print('could not parse response')
            return

        if status['status'] == 'error':
            print('could not pause/unpause timer, got: {}'
                  .format(status['error']))
            popup = Popup(title='Error!',
                          content=Label(text=status['error']),
                          size_hint=(0.25, 0.25))
            popup.open()

    def do_start_game(self, *args):
        r = safe_get(self.scoreboard_address+'/control/gbegin')

        try:
            status = r.data.json()
        except:
            print('could not parse response')
            return

        if status['status'] == 'error':
            print('could not start game, got: {}'.format(status['error']))
            popup = Popup(title='Error!',
                          content=Label(text=status['error']),
                          size_hint=(0.25, 0.25))
            popup.open()

    def do_end_game(self, *args):
        r = safe_get(self.scoreboard_address+'/control/gend')

        try:
            status = r.data.json()
        except:
            print ('could not parse response')
            return

        if status['status'] == 'error':
            print ('could not stop game, got: {}'.format(status['error']))
            popup = Popup(title='Error!',
                          content=Label(text=status['error']),
                          size_hint=(0.25, 0.25))
            popup.open()

    def do_debug_setup2(self, *args):
        self._do_debug_setup(2)

    def do_debug_setup4(self, *args):
        self._do_debug_setup(4)

    def do_remove_all(self, *args):

        r = safe_get(self.scoreboard_address+'/status/players')

        try:
            players = r.data.json()
        except Exception:
            print ('could not remove players')
            return

        headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
        for player in sorted(players)[::-1]:
            player_data = {'playerNumber': player}
            r = safe_post(self.scoreboard_address+'/control/punregister',
                          data=player_data, headers=headers)

            try:
                status = r.data.json()
            except Exception:
                print ('Could not unregister player {}'.format(player))
                continue

            if status['status'] == 'error':
                print ('Could not unregister player {}, got: {}'
                       .format(player, status['error']))
                continue

    def _do_debug_setup(self, player_num):

        player_names = ["A", "B", "C", "D"]

        # register some players

        headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}

        for p in range(0, player_num):

            player_data = {'panelTxt': player_names[p],
                           'webTxt': player_names[p]}
            r = safe_post(self.scoreboard_address+'/control/pregister',
                          data=player_data, headers=headers)

            try:
                response = r.data.json()
                if response['status'] == 'error':
                    raise Exception
            except Exception:
                print ('Could not setup successfully, returned: {}'
                       .format(response['error']))
                continue

            player_num = int(response['playerNum'])

            # force pairing
            r = safe_get(self.scoreboard_address +
                         '/debug/fpair/{},{}'.format(player_num, player_num+1))

    def force_pairing(self):

        for p in range(0, self.player_num):
            # force pairing
            safe_get(self.scoreboard_address +
                     '/debug/fpair/{},{}'.format(p, p+1))

    def do_sfx_play(self, * args):

        if args[0].text not in self.sfx_reverse_list:
            # try directly
            sfx_name = args[0].text
        else:
            sfx_name = self.sfx_reverse_list[args[0].text]

        r = safe_get(self.scoreboard_address+'/debug/sfx/{}'.format(sfx_name))

        try:
            status = r.data.json()
        except:
            print ('could not parse response')
            return

        if status['status'] == 'error':
            print ('Could not play SFX, got: {}'.format(status['error']))

    def do_test_score_1(self, *args):
        safe_get(self.scoreboard_address+'/debug/scoretest/0')

    def do_test_score_2(self, *args):
        safe_get(self.scoreboard_address+'/debug/scoretest/1')

    def do_test_score_3(self, *args):
        safe_get(self.scoreboard_address+'/debug/scoretest/2')

    def do_test_score_4(self, *args):
        safe_get(self.scoreboard_address+'/debug/scoretest/3')

    def do_announce(self, *args):
        pass

    def do_incr_score(self, pnum):
        safe_get(self.scoreboard_address+'/debug/sincr/{}'.format(pnum))

    def do_decr_score(self, pnum):
        safe_get(self.scoreboard_address+'/debug/sdecr/{}'.format(pnum))

    def do_force_serve(self, pnum):
        safe_get(self.scoreboard_address+'/debug/pass')

    def do_set_score(self, player, score):

        if score > 5 or score < -10:
            print ('Invalid score input')
            self.ids['setscore{}'.format(player)].text = ''
            return

        r = safe_get(self.scoreboard_address +
                     '/debug/setscore/{},{}'.format(player, score))

        try:
            response = r.data.json()
        except:
            return

        if response['status'] == 'error':
            print ('Could not set score, returned {}'
                   .format(response['error']))

    def do_set_turn(self, player):
        safe_get(self.scoreboard_address+'/debug/setturn/{}'.format(player))

    def do_set_turn_1(self, *args):
        safe_get(self.scoreboard_address+'/debug/setturn/0')

    def do_set_turn_2(self, *args):
        safe_get(self.scoreboard_address+'/debug/setturn/1')

    def do_set_turn_3(self, *args):
        safe_get(self.scoreboard_address+'/debug/setturn/2')

    def do_set_turn_4(self, *args):
        safe_get(self.scoreboard_address+'/debug/setturn/3')

    def one_shot_refresh(self):
        try:
            r = safe_get(self.scoreboard_address+'/status/sfxlist')
            status = r.data.json()
        except:
            print ('error getting SFX List')
            return

        if status['status'] != 'ok':
            print ('error getting SFX List')
            return

        self.sfx_list = status['sfx_list']

        self._sfx_widgets = []
        for k, v in self.sfx_list.items():
            if v is not None:
                name = v
            else:
                name = k

            widget = OneLineIconListItem(text=name)
            widget.add_widget(AvatarSampleWidget(icon='volume-high'))
            widget.bind(on_press=self.do_sfx_play)
            self._sfx_widgets.append(widget)
            self.ids['debugTabActions'].add_widget(widget)

        # create SFX reverse lookup dictionary
        self.sfx_reverse_list = {}
        for k, v in self.sfx_list.items():
            if v is not None:
                self.sfx_reverse_list[v] = k

        # get game persistance data
        try:
            r = safe_get(self.scoreboard_address+'/persist/game_list')
            status = r.data.json()
        except:
            print ('error getting game persistance')
            return

        self.game_persist_list = status['game_list']
        # update spinner
        self.ids['gpersist'].values = sorted(self.game_persist_list)
        self.ids['gpersist'].disabled = False

    def refresh_status(self, *args):
        # hacky hack
        updater = PanelUpdater(address=self.scoreboard_address, root=self)

        updater.start()

    def register_scoring_event(self, evt_type, player):
        safe_get(self.scoreboard_address +
                 '/control/scoreevt/{},{}'.format(player, evt_type))

    # beware of very convoluted logic below
    def handle_player_button(self, player):

        if self.game_running:
            self.do_set_turn(player)
            return

        if not hasattr(self, 'pbubb'):
            butpos = self.ids['pname{}'.format(player)].pos
            butsize = self.ids['pname{}'.format(player)].size
            bubsize = [320, 100]
            bubpos = []
            bubpos.append(butpos[0] + butsize[0]/2 - bubsize[0]/2)
            bubpos.append(butpos[1] - butsize[1]/2 + bubsize[1])

            is_registered = str(player) in self.registered_player_list.keys()
            is_paired = False
            if is_registered:
                rm_id = self.registered_player_list[str(player)]['remote_id']
                is_paired = rm_id is not None
            self.pbubb = PlayerActions(player=player,
                                       position=bubpos,
                                       size=bubsize,
                                       is_registered=is_registered,
                                       is_paired=is_paired,
                                       is_paused=self.game_paused,
                                       address=self.scoreboard_address)
            self.pbubb_open = False
            self.pbubb_player = player
        else:
            self.pbubb_player = player

    def kill_pbubb(self):
        self.pbubb_open = False
        self.remove_widget(self.pbubb)
        pbubb_cur_player = self.pbubb.player
        del self.pbubb

        return pbubb_cur_player

    def on_touch_down(self, touch):
        super(RootWidget, self).on_touch_down(touch)

        if hasattr(self, 'pbubb'):
            pbubb_cur_player = None
            if self.pbubb_open:
                if self.pbubb.collide_point(*touch.pos) is False:
                    # clicked outside of bubble
                    pbubb_cur_player = self.kill_pbubb()
                    if self.pbubb_player != pbubb_cur_player:
                        # create new bubble now (clicked onther player button)
                        self.handle_player_button(self.pbubb_player)
                        self.pbubb_open = True
                        self.add_widget(self.pbubb)
            else:
                self.pbubb_open = True
                self.add_widget(self.pbubb)

    def set_discovered_address(self, address):
        self._discovered_address = address

    def set_scoreboard_address(self, address):
        # do error checking?
        if address is None:
            return

        self._unformatted_address = address
        self.scoreboard_address = 'http://{}'.format(address)

    def get_persist_data(self, uuid):
        return
        # retrieve CSV data from game persistance
        persist_url = (self.scoreboard_address +
                       '/persist/dump_range/{},1'.format(uuid))

        csv_data = None
        with requests.Session() as sess:
            fmt = sess.get(self.scoreboard_address +
                           '/persist/dump_fmt').json()
            data = sess.get(persist_url)
            decoded_data = data.content.decode('utf-8')

            csv_data = csv.reader(decoded_data.splitlines(), delimiter=',')

        if csv_data is not None:

            tables = {}

            fmt = fmt['fmt']
            position = 0
            current_section = None
            section_position = -1
            for line in csv_data:
                if current_section is not None:
                    current_fmt = fmt['sections'][current_section]
                if len(line) == 1:
                    if line[0] in fmt['sections']:

                        # section length check
                        if section_position > -1 and section_position <\
                           current_fmt['min_length']:
                            print ('Section is too short')
                            raise IOError('error')

                        print ('found section: {}'.format(line[0]))
                        current_section = line[0]
                        section_position = 0
                        position += 1
                        # create table
                        tables[line[0]] = texttable.Texttable()
                        continue
                    else:
                        print ('Illegal section: {}'.format(line[0]))
                else:
                    if section_position > -1:
                        # inside section
                        if section_position == 0:
                            # section headers
                            print ('found section "{}"'
                                   ' headers: {}'.format(current_section,
                                                         line))
                            # insert into table
                            tables[current_section].add_row(line)
                            if current_fmt['max_length'] == 1:
                                section_position = -1
                                position += 1
                            else:
                                section_position += 1
                                position += 1

                            continue
                        else:
                            current_fmt = fmt['sections'][current_section]
                            # add more
                            tables[current_section].add_row(line)
                            if section_position < current_fmt['max_length']:
                                section_position += 1
                                position += 1
                            else:
                                section_position = -1
                                position += 1

                            continue

            one_big_label = ''
            for section, table in tables.items():
                if table is not None:
                    table_draw = table.draw()
                    if table_draw is not None:
                        one_big_label += table.draw()
            self.ids['persistshow'].text = one_big_label


class SimpleboardDebugPanel(App):

    theme_cls = ThemeManager()
    title = 'ChainBoard - ChainBot Remote'
    listener = None

    def __init__(self, *args, **kwargs):
        address = kwargs.pop('address')
        super(SimpleboardDebugPanel, self).__init__(*args, **kwargs)
        self._is_android = False

        self.root = RootWidget(address=address,
                               disable_app_cb=self.disable_app_cb,
                               enable_app_cb=self.enable_app_cb)

    def disable_app_cb(self, **kwargs):
        if self._is_android:
            self.listener.start_listening(**kwargs)

    def enable_app_cb(self, **kwargs):
        if self._is_android:
            self.listener.stop_listening(**kwargs)

    def set_listener(self, listener, is_android=False):
        self.listener = listener
        self._is_android = is_android

    def post_init(self):
        self.root.post_init()

    def discover_service(self, address, port, name, attr):
        if name == 'Chainball Scoreboard':
            Logger.info('discover: found scoreboard at {}:{}'.format(address,
                                                                     port))
            # set address
            self.root.set_discovered_address('{}:{}'.format(address, port))
            if self.root._prefmgr.network__enable_discovery:
                self.root.set_scoreboard_address('{}:{}'.format(address, port))

    def remove_service(self, name):
        if name == 'Chainball Scoreboard':
            Logger.info('discover: scoreboard service was removed')

            # unset address
            self.root.set_discovered_address(None)

    def build(self):
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
