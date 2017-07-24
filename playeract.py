"""Player Actions popup menu."""

from kivy.uix.bubble import Bubble, BubbleButton
from miscui import RootFinderMixin
from util.saferequests import safe_post
from kivymd.dialog import MDDialog
from kivymd.textfields import MDTextField
from kivymd.label import MDLabel

from kivy.logger import Logger


class UsefulDialog(MDDialog):
    """Make MDDialog not be worthless."""

    def __init__(self, **kwargs):
        """Initialize."""
        super().__init__(**kwargs)

        self._container.orientation = 'vertical'
        self._container.padding = (0, 10, 0, 10)
        self._container.spacing = 20

    def add_to_box(self, widget):
        """Add stuff to internal boxlayout."""
        self._container.add_widget(widget)


class PlayerActions(Bubble, RootFinderMixin):
    """Player-related actions popup menu."""

    def __init__(self, *args, **kwargs):
        """Initialize."""
        super(PlayerActions, self).__init__(*args, **kwargs)

        self.player = kwargs['player']
        self.pos = kwargs['position']
        self.size = kwargs['size']
        self.is_paired = kwargs['is_paired']
        self.game_paused = kwargs['is_paused']
        self.scoreboard_address = kwargs['address']
        self.size_hint = (None, None)

        self.add_btn = BubbleButton(on_press=self.add_player,
                                    text='Add player',
                                    disabled=kwargs['is_registered'] or
                                    kwargs['is_paused'])
        self.rm_btn = BubbleButton(on_press=self.remove_player,
                                   text='Remove player',
                                   disabled=not kwargs['is_registered'] or
                                   kwargs['is_paused'])
        pair_txt = 'Unpair remote' if self.is_paired else 'Pair remote'
        self.pair_btn = BubbleButton(on_press=self.pair_remote,
                                     text=pair_txt,
                                     disabled=not kwargs['is_registered'])
        self.add_widget(self.add_btn)
        self.add_widget(self.rm_btn)
        self.add_widget(self.pair_btn)

    def _register_player(self, *args):

        panel_txt = self.ptxt.text.strip(' ')
        web_txt = self.wtxt.text.strip(' ')

        if len(panel_txt) == 0:
            Logger.warning('RegisterPlayer: empty text')
            self.ptxt.helper_text = 'Cannot be empty'
            self.ptxt.error = True
            self.ptxt.helper_text_mode = 'persistent'
            return
        elif len(panel_txt) > 7:
            Logger.warning('RegisterPlayer: text too big')
            self.ptxt.helper_text = 'Text is too big'
            self.ptxt.error = True
            self.ptxt.helper_text_mode = 'persistent'
            return

        if len(web_txt) == 0:
            web_txt = panel_txt

        ret = safe_post(self.scoreboard_address + '/control/pregister',
                        data={'panelTxt': panel_txt,
                              'webTxt': web_txt})
        # get status
        # TODO: display failure dialog
        Logger.info('PlayerRegister: {}'.format(ret))

        # kill popup
        self.popup.dismiss()

    def _add_dismiss(self, *args):
        del self.popup
        del self.ptxt
        del self.wtxt

    def add_player(self, *args):
        """Build popup contents to add."""
        self.wtxt = MDTextField(hint_text='Full Player Name')
        self.ptxt = MDTextField(hint_text='Panel Display Name',
                                required=True)
        self.ptxt.max_text_length = 7

        # build popup and show
        self.popup = UsefulDialog(title='Add player',
                                  content=None,
                                  size_hint=(0.5, 0.5),
                                  auto_dismiss=True)
        self.popup.add_to_box(MDLabel(text='Full Player Name'))
        self.popup.add_to_box(self.wtxt)
        self.popup.add_to_box(MDLabel(text='Panel Display Name'))
        self.popup.add_to_box(self.ptxt)
        self.find_root().kill_pbubb()
        self.popup.add_action_button("Add", action=self._register_player)
        self.popup.open()

    def remove_player(self, *args):
        """Remove selected player."""
        safe_post(self.scoreboard_address+'/control/punregister',
                  data=('playerNumber={}'.format(self.player)))

        self.find_root().kill_pbubb()

    def pair_remote(self, *args):
        """Pair remote."""
        if self.is_paired:
            # unpair, easy
            safe_post(self.scoreboard_address+'/control/runpair',
                      data=('playerNumber={}'.format(self.player)))
        else:
            pass

        self.find_root().kill_pbubb()
