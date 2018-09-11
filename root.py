"""Root widget for panel app."""

from kivy.uix.floatlayout import FloatLayout
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.logger import Logger
from kivy.core.window import Window
from kivymd.dialog import MDDialog
from kivymd.textfields import MDTextField
from kivymd.material_resources import DEVICE_TYPE
from kivymd.list import OneLineIconListItem
from miscui import AvatarSampleWidget
from playeract import PlayerActions
from panelupd import PanelUpdater
import texttable
from util.prefmgr import PrefsMgr
from util.saferequests import (safe_post, safe_get)
import os
import re
import requests
import csv


CONFIGURATION_PATH = 'config'
PREFERENCES = 'prefs.json'


class ScoreboardException(Exception):
    """Exception in scoreboard communication."""

    pass


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
                    raise ScoreboardException
            except ScoreboardException:
                Logger.error('Could not setup successfully, returned: {}'
                             .format(response['error']))
                continue
            except Exception as ex:
                Logger.error(f'DebugSetup: failed to perform debug setup with'
                             f' {player_num} players, got "{ex}"')
                return

            player_num = int(response['playerNum'])

            # force pairing
            r = safe_get(self.scoreboard_address +
                         '/debug/fpair/{},{}'.format(player_num, player_num+1))

    def force_pairing(self):

        for p in range(0, 4):
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

            is_registered = str(player) in self.registered_player_list
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
