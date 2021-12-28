from pydbus import SystemBus
from time import sleep
from datetime import datetime

class dsp(object):

    def __init__(self):
        # get the session bus
        bus = SystemBus()
        # get the object
        self._dsp = bus.get("org.spotmicro.lcdd")
        self._lastUpdate=datetime.now()

    def setText(self, msg):
        reply = self._dsp.SetText(msg)
        self._lastUpdate = datetime.now()
        #print(reply)

    @property
    def lastUpdate(self):
        return self._lastUpdate

    def drawInfo(self):
        reply = self._dsp.DrawInfo()
        #print(reply)

    def quit(self):
        self._dsp.Quit()
