import json
from kivy.logger import Logger

_DEFAULT_PREFERENCES = 'config/default.json'

class FatalPreferenceError(Exception):
    pass

class PrefsMgr(object):

    def __init__(self, pref_file=None, auto_save=True):

        self._pref_path = None
        self._pref_default = False
        self._auto_save = auto_save
        #try to load
        prefs = None
        if pref_file is not None:
            with open(pref_file, 'r') as f:
                try:
                    prefs = json.load(f)
                    self._pref_path = pref_file
                except json.decoder.JSONDecodeError:
                    #failed to open!
                    pass

        if prefs is None:
            #load default
            Logger.warning('prefMgr: using default preferences')
            with open(_DEFAULT_PREFERENCES, 'r') as f:
                prefs = json.load(f)
                self._pref_default = True

            if prefs is None:
                Logger.error('prefMgr: could not load default preferences')
                raise FatalPreferenceError('could not load default values')

        self._prefs = prefs

    def __getattribute__(self, attr):

        #dirty but great
        try:
            return super(PrefsMgr, self).__getattribute__(attr)
        except AttributeError:
            #parse

            sep = attr.split('__')
            if len(sep) != 2:
                #failed
                raise AttributeError('Invalid attribute requested: {}'.format(attr))

            #configuration section
            if sep[0] in self._prefs:
                if sep[1] in self._prefs[sep[0]]:
                    return self._prefs[sep[0]][sep[1]]
                else:
                    raise KeyError('Invalid configuration entry: {}/{}'.format(sep[0],
                                                                               sep[1]))
            else:
                raise KeyError('Invalid configuration section: {}'.format(sep[0]))

    def __setattr__(self, attr, value):
        #we take over
        sep = attr.split('__')
        if len(sep) != 2:
            super(PrefsMgr, self).__setattr__(attr, value)
            return
            #raise AttributeError('Invalid attribute requested: {}'.format(attr))

        if sep[0] in self._prefs:
            if sep[1] in self._prefs[sep[0]]:
                self._prefs[sep[0]][sep[1]] = value
                if self._auto_save:
                    self.save_configuration()
                else:
                    raise KeyError('Invalid configuration entry: {}/{}'.format(sep[0],
                                                                               sep[1]))
            else:
                raise KeyError('Invalid configuration section: {}'.format(sep[0]))

    def save_configuration(self):
        if self._pref_default:
            #ignore
            return

        with open(self._pref_path, 'w') as f:
            json.dump(self._prefs, f, indent=4)
