"""Panel updater thread."""

from kivy.logger import Logger
from threading import Thread
from util.saferequests import (safe_get,
                               is_connection_error_exception)


class PanelUpdater(Thread):
    """Panel updater thread."""

    def __init__(self, *args, **kwargs):
        """Initialize."""
        super(PanelUpdater, self).__init__(*args)

        self.scoreboard_address = kwargs['address']
        self.root = kwargs['root']
        self.disabled = False

    def run(self):
        """Run thread."""
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
                success = True
            except Exception as ex:
                # ignore
                success = False
                Logger.info('PanelUpdater: exception '
                            'caught while retriving data: {}'.format(repr(ex)))

        if self.root.disconnected:
            self.root.enable_app(from_thread=True)
            self.root.one_shot_refresh()
        if success is False:
            return

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
