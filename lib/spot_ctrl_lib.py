from lib.sbus_receiver import SBUSReceiver, MIN_VALUE_OUT, MAX_VALUE_OUT
from time import sleep
from datetime import datetime

class spot_controller(object):


    MAX_BUTTONS=21
    MAX_AXIS=6

    def __init__(self, port):
        self._rx = SBUSReceiver(port)
        self._iValidFrames=0
        self._iLastValidFrames=0
        self._lastFsCheck=0

    @property
    def rssi(self):
        return self._rx.getRxChannel(11)


    def getAxis(self, iChannel):

        iReturn=self._rx.getRxChannel(iChannel)

        return self._normalize(iReturn)

    def _normalize(self, iValue):

        iReturn = (iValue - MIN_VALUE_OUT) / (MAX_VALUE_OUT-MIN_VALUE_OUT)

        if iReturn <0.0:
            iReturn=0.0
        elif iReturn >1.0:
            iReturn=1.0

        iReturn = (iReturn*2)-1

        if iReturn < -1:
            iReturn = -1
        elif iReturn > 1:
            iReturn = 1

        return iReturn

    @property
    def rssi(self):
        return self._rx.Rssi

    @property
    def InSync(self):
        return self._rx.getSyncStatus()

    @property
    def FsStatus(self):

        iFs=self._rx.getFsStatus()

        if iFs == self._rx.SBUS_SIGNAL_OK:
            ival=self._rx.getRxReport()["Valid Frames"]

            return "Ok"

            #print(self._iValidFrames ,ival)
            #if self._iValidFrames == ival:
            #    return "1Signal Lost"
            #else:
            #    self._iValidFrames = ival
            #    return "Ok"




        elif iFs == self._rx.SBUS_SIGNAL_LOST:
            return "Signal Lost"
        elif iFs == self._rx.SBUS_SIGNAL_FAILSAFE:
            return "Failsafe"
        else:
            x=0
            rxc=self._rx.getRxChannels()
            for i in range(len(rxc)):
                x +=rxc[i]

            if x==1000*len(rxc):
                return "No Signal"
            else:
                return "?"

    def getCustom(self, iChannel):
        iState = 0

        #0 shutdown init?
        if iChannel == 0:
            if self.getButton(18)==1 and self.getButton(19)==1:
                iState=1

        #1 shutdown triggered
        elif iChannel ==1:
            if self.getButton(18)==1 and self.getButton(19)==0:
                iState=1

        return iState

    def getButton(self, iChannel):

        iState=0
        iStep=200
        iTol=4
        iRxValue=(MAX_VALUE_OUT-MIN_VALUE_OUT)/2
        iGoal = 1500

        if iChannel in range(0,6):
            iRxValue=self._rx.getRxChannel(8)
            iGoal=MIN_VALUE_OUT + (iStep* iChannel)

        elif iChannel in range(6,12):
            iRxValue=self._rx.getRxChannel(9)
            iGoal=MIN_VALUE_OUT + (iStep* (iChannel-6))

        elif iChannel in range(12, 18):
            iRxValue = self._rx.getRxChannel(10)
            iGoal = MIN_VALUE_OUT + (iStep * (iChannel - 12))

        elif iChannel in range(18, 20):
            iRxValue = self._rx.getRxChannel(iChannel-12)
            iGoal=MAX_VALUE_OUT

        if iRxValue in range(iGoal - iTol, iGoal + iTol):
            iState = 1

        #print(iChannel, iRxValue, iState)

        return iState

    def getChannels(self):

        return self._rx.getRxChannels()


if __name__== "__main__":
    ctrl=spot_controller("/dev/ttyAMA0")

    while True:
        lstLine = []
        print(ctrl._rx.getRxReport(), ctrl.getChannels())
        lstLine.append("| FS: {}".format(ctrl.FsStatus))
        lstLine.append("| Sync: {}".format(ctrl.InSync))

        lstLine.append("Axis: ")
        for i in range(ctrl.MAX_AXIS):
            lstLine.append("[{}: {}]".format(i, ctrl.getAxis((i))))

        # print(", ".join(lstLine))

        lstLine.append("| Buttons: ")
        # lstLine = []

        for i in range(ctrl.MAX_BUTTONS):
            lstLine.append("[{}: {}]".format(i, ctrl.getButton((i))))

        print(", ".join(lstLine))

        sleep(0.1)


"""
ctrl= spot_controller("dev/ttyS0")


while True:
    #print(ctrl.getChannels())
    lstLine = []

    lstLine.append("Axis: ")
    for i in range(ctrl.MAX_AXIS):
        lstLine.append("[{}: {}]".format(i, ctrl.getAxis((i))))

    #print(", ".join(lstLine))
    lstLine.append("| Buttons: ")
    #lstLine = []

    for i in range(ctrl.MAX_BUTTONS):
        lstLine.append("[{}: {}]".format(i, ctrl.getButton((i))))

    print(", ".join(lstLine))

    sleep(0.05)

"""
