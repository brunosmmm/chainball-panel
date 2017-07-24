"""Player Actions popup menu."""

from kivy.uix.bubble import Bubble, BubbleButton
from miscui import RootFinderMixin
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from util.saferequests import safe_post
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup


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

        panel_txt = self.ptxt.text
        web_txt = self.wtxt.text
        safe_post(self.scoreboard_address+'/control/pregister',
                  data={'panelTxt ': panel_txt,
                        'webTxt': web_txt})
        # get status
        # TODO: display failure dialog

        # kill popup
        self.popup.dismiss()

    def _add_dismiss(self, *args):
        del self.popup
        del self.ptxt
        del self.wtxt

    def add_player(self, *args):
        """Build popup contents to add."""
        box = BoxLayout(orientation='vertical', spacing=2)
        box.add_widget(Label(text='Full player name:'))
        self.wtxt = TextInput()
        box.add_widget(self.wtxt)
        box.add_widget(Label(text='Panel display name:'))
        self.ptxt = TextInput()
        box.add_widget(self.ptxt)

        addbut = Button(text='Add',
                        on_press=self._register_player)
        box.add_widget(addbut)

        # build popup and show
        self.popup = Popup(title='Add player',
                           content=box,
                           size_hint=(0.4, 0.4),
                           on_dismiss=self._add_dismiss)
        self.find_root().kill_pbubb()
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
