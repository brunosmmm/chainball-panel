from kivy.uix.spinner import Spinner
from kivy.metrics import dp
from kivy.properties import NumericProperty, ObjectProperty, BoundedNumericProperty, StringProperty
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivymd.selectioncontrols import MDCheckbox
from kivymd.list import ILeftBody, ILeftBodyTouch, IRightBodyTouch, BaseListItem
from kivymd.button import MDRaisedButton, MDIconButton, BaseRectangularButton, RectangularElevationBehavior, BaseRaisedButton, BasePressedButton, RectangularRippleBehavior, BaseButton
from kivymd.menu import MDDropdownMenu, MDMenuItem
from kivymd.spinner import MDSpinner
from kivymd.dialog import MDDialog
from kivymd.label import MDLabel
from kivymd.navigationdrawer import NavigationDrawerDivider
from kivymd.accordion import MDAccordionSubItem
from kivymd.list import OneLineIconListItem, TwoLineListItem, OneLineListItem
from kivy.app import App

def debug(value):

    equivalence = {1.0: dp(32),
                   2.0: dp(40),
                   3.0: dp(60),
                   4.0: dp(88)}

    if value in equivalence:
        return equivalence[value]
    else:
        if value < dp(60):
            return dp(60)

class AltBaseRectangularButton(BaseRectangularButton):
    '''
    Abstract base class for all rectangular buttons, bringing in the
    appropriate on-touch behavior. Also maintains the correct minimum width
    as stated in guidelines.
    '''
    #width = property
    width = BoundedNumericProperty(dp(60), min=dp(60), max=None,
                                   errorhandler=lambda x: dp(60))

class MDAltRaisedButton(AltBaseRectangularButton,
                        RectangularElevationBehavior,
                        BaseRaisedButton, BasePressedButton):
    pass

class MDAccordionIconSubItem(MDAccordionSubItem, OneLineIconListItem):
    parent_item = ObjectProperty()

class MDAccordionSubItem2(MDAccordionSubItem, TwoLineListItem):
    parent_item = ObjectProperty()

class AvatarSampleWidget(ILeftBody, MDIconButton):
    pass

class IconRightSampleWidget(IRightBodyTouch, MDCheckbox):
    pass

class RootFinderMixin(object):

    def __init__(self, root_widget_class='RootWidget', **kwargs):
        self.root_widget_class = root_widget_class

    def find_root(self):
        root = self.parent
        while root.__class__.__name__ != self.root_widget_class:
            root = root.parent
        return root

class ScoreValueItem(MDMenuItem):
    click_cb = ObjectProperty(None, allownone=True)

    def on_press(self, *args):
        if self.click_cb is not None:
            self.click_cb(int(self.text))
        super(ScoreValueItem, self).on_press(*args)

class ScoreButton(MDRaisedButton, RootFinderMixin):
    player = NumericProperty(-1)

    def __init__(self, *args, **kwargs):
        super(ScoreButton, self).__init__(*args, **kwargs)

        self.values = [str(x) for x in range(-10,6)]

        #create menu items
        self._mitems = []
        for value in self.values:
            item = {'viewclass': 'ScoreValueItem',
                    'text': value,
                    'click_cb': self._set_score}
            self._mitems.append(item)

    def _set_score(self, score):
        self.find_root().do_set_score(self.player, score)

    def update_score(self, score):
        if score not in self.values and score != '-':
            return

        self.text = score
        if self.text == '-':
            self.disabled = True
        else:
            self.disabled = False

    def open_set_score_dialog(self, player):

        class PlayerButton(MDRaisedButton):
            player = NumericProperty(-1)

        def score_btn_clicked(instance):
            self._set_score(int(instance.text))
            self._open_dialog.dismiss()

        content = BoxLayout(orientation='vertical',
                            size_hint=(None, None))

        #labels
        #header = MDLabel(font_style='Body1',
        #                 text='Please select a value',
        #                 size_hint=(1.0, 0.2),
        #                 valign='top')
        #content.add_widget(header)

        #content.add_widget(NavigationDrawerDivider())

        btn_grid = GridLayout(cols=4,
                              spacing=dp(20))
        #create score buttons
        for val in range(-10,6):
            btn = PlayerButton(text=str(val), player=player)
            btn.bind(on_release=score_btn_clicked)
            btn_grid.add_widget(btn)

        content.add_widget(btn_grid)

        #create dialog
        self._open_dialog = MDDialog(title='Force player {} score'.format(player),
                                     content=content,
                                     size_hint=(.6, .6),
                                     auto_dismiss=True)
        self._open_dialog.open()

    def on_release(self, *args, **kwargs):
        super(ScoreButton, self).on_release(*args)
        self.open_set_score_dialog(self.player)

class ScoreSpinner(Spinner, RootFinderMixin):

    player = NumericProperty(-1)

    def __init__(self, *args, **kwargs):
        super(ScoreSpinner, self).__init__(*args, **kwargs)

        self.values = [str(x) for x in range(-10, 6)]

        self.updating = False

    def update_score(self, score):
        if score not in self.values and score != '-':
            return

        self.updating = True
        self.text = score

        if self.text == '-':
            self.disabled = True
        else:
            self.disabled = False

        self.updating = False

    def on_text(self, *args, **kwargs):
        if self.updating:
            return

        # set score
        self.find_root().do_set_score(self.player)

    def on_is_open(self, spinner, is_open):
        super(ScoreSpinner, self).on_is_open(spinner, is_open)

        #if is_open:
        #    self.find_root().stop_refreshing = True
        #else:
        #    self.find_root().stop_refreshing = False

    def on_press(self, *args):
        if self.is_open == False:
            # opening
            pass
