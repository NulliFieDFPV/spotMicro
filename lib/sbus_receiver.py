import array
import serial
from time import sleep
import threading
from datetime import datetime
from copy import deepcopy
import numpy as np

MAX_VALUE_IN = 1807.0
MIN_VALUE_IN = 177.5
MIN_VALUE_OUT=1000
MAX_VALUE_OUT=2000

class SBUSReceiver(object):

    lock = threading.Lock()


    def __init__(self, uart_port):

        self.uart_port = uart_port
        # self.sbus.set_buffer_size(250)
        self._openUart()

        # .init(100000, bits=8, parity=0, stop=2, timeout_char=3, read_buf_len=250)

        # constants
        self.START_BYTE = b'0f'
        self.END_BYTE = b'00'
        self.SBUS_FRAME_LEN = 25
        self.SBUS_NUM_CHAN = 20
        self.OUT_OF_SYNC_THD = 10
        self.SBUS_NUM_CHANNELS = 20
        self.SBUS_SIGNAL_OK = 0
        self.SBUS_SIGNAL_LOST = 1
        self.SBUS_SIGNAL_FAILSAFE = 2

        # Stack Variables initialization
        self.validSbusFrame = 0
        self.lostSbusFrame = 0
        self.frameIndex = 0
        self.resyncEvent = 0
        self.outOfSyncCounter = 0
        self.sbusBuff = bytearray(1)  # single byte used for sync
        self.sbusFrame = bytearray(25)  # single SBUS Frame
        self.sbusChannels = array.array('H', [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])  # RC Channels
        self.rxChannels= array.array('H', [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])  # RC Channels
        self.isSync = False
        self.startByteFound = False
        self.failSafeStatus = self.SBUS_SIGNAL_FAILSAFE
        self.threadEvent= threading.Event()
        self.iempty=0

        t2 = threading.Thread(target=self._startReceive, args=[self.threadEvent])
        t2.start()

    def __del__(self):

        self.threadEvent.set()

    def _openUart(self):

        try:
            self.sbus.close()
        except:
            pass

        try:
            self.sbus = serial.Serial(
                port=self.uart_port,
                baudrate=100000,
                parity=serial.PARITY_EVEN,
                stopbits=serial.STOPBITS_TWO,
                bytesize=serial.EIGHTBITS,
                timeout=0,
            )
        except:
            print("no sbus")

    def getRxChannels(self):
        """
        Used to retrieve the last SBUS channels values reading
        :return:  an array of 18 unsigned short elements containing 16 standard channel values + 2 digitals (ch 17 and 18)
        """

        with SBUSReceiver.lock:
            rxData = array.array('H', np.copy(self.rxChannels))

        rxData[self.SBUS_NUM_CHAN-2]=1 if self.isSync else 0
        rxData[self.SBUS_NUM_CHAN - 1] =self.sbus.inWaiting()

        #print(self.sbus.inWaiting(), self.isSync)
        return rxData


    def getRxChannel(self, num_ch):
        """
        Used to retrieve the last SBUS channel value reading for a specific channel
        :param: num_ch: the channel which to retrieve the value for
        :return:  a short value containing
        """
        with SBUSReceiver.lock:
            rxData=self.rxChannels[num_ch]
        #print(self.sbus.inWaiting(),self.isSync)

        return rxData

    def getSyncStatus(self):

        fs=True
        with SBUSReceiver.lock:
            fs=self.isSync

        return fs

    def getFsStatus(self):
        """
        Used to retrieve the last FAILSAFE status
        :return:  a short value containing
        """

        fs=self.SBUS_SIGNAL_OK

        with SBUSReceiver.lock:
            fs=self.failSafeStatus
            rssi=self.sbusChannels[11]

        if self.iempty>100:
            fs = self.SBUS_SIGNAL_LOST
            self.sbusChannels[11]=0

        if fs == self.SBUS_SIGNAL_OK and rssi==0:
            fs=self.SBUS_SIGNAL_LOST

        return fs

    @property
    def Rssi(self):

        rssi=0
        with SBUSReceiver.lock:
            rssi=self.sbusChannels[11]

        return rssi

    def getRxReport(self):
        """
        Used to retrieve some stats about the frames decoding
        :return:  a dictionary containg three information ('Valid Frames','Lost Frames', 'Resync Events')
        """
        rep = {}
        rep['Valid Frames'] = -1
        rep['Lost Frames'] = -1
        rep['Resync Events'] = -1

        with SBUSReceiver.lock:
            rep['Valid Frames'] = self.validSbusFrame
            rep['Lost Frames'] = self.lostSbusFrame
            rep['Resync Events'] = self.resyncEvent

        return rep

    def _decodeFrame(self):

        # TODO: DoubleCheck if it has to be removed
        for i in range(0, self.SBUS_NUM_CHANNELS - 2):
            self.sbusChannels[i] = 0

        # counters initialization
        byte_in_sbus = 1
        bit_in_sbus = 0
        ch = 0
        bit_in_channel = 0


        for i in range(0, 175):  # TODO Generalization
            if self.sbusFrame[byte_in_sbus] & (1 << bit_in_sbus):

                self.sbusChannels[ch] |= (1 << bit_in_channel)

            bit_in_sbus += 1
            bit_in_channel += 1

            if bit_in_sbus == 8:
                bit_in_sbus = 0
                byte_in_sbus += 1

            if bit_in_channel == 11:
                bit_in_channel = 0
                ch += 1

        # Decode Digitals Channels

        # Digital Channel 1
        if self.sbusFrame[self.SBUS_FRAME_LEN - 2] & (1 << 0):
            self.sbusChannels[self.SBUS_NUM_CHAN - 4] = 1
        else:
            self.sbusChannels[self.SBUS_NUM_CHAN - 4] = 0

        # Digital Channel 2
        if self.sbusFrame[self.SBUS_FRAME_LEN - 2] & (1 << 1):
            self.sbusChannels[self.SBUS_NUM_CHAN - 3] = 1
        else:
            self.sbusChannels[self.SBUS_NUM_CHAN - 3] = 0

        # Failsafe
        #print(self.sbusFrame)
        self.failSafeStatus = self.SBUS_SIGNAL_OK
        if self.sbusFrame[self.SBUS_FRAME_LEN - 2] & (1 << 2):
            self.failSafeStatus = self.SBUS_SIGNAL_LOST
        if self.sbusFrame[self.SBUS_FRAME_LEN - 2] & (1 << 3):
            self.failSafeStatus = self.SBUS_SIGNAL_FAILSAFE


        with SBUSReceiver.lock:
            self.rxChannels = list(map(self._normalize, self.sbusChannels))


    def _normalize(self, iValue):

        iReturn = (iValue - MIN_VALUE_IN) / (MAX_VALUE_IN-MIN_VALUE_IN)

        if iReturn <0.0:
            iReturn=0.0
        elif iReturn >1.0:
            iReturn=1.0

        iReturn= (MAX_VALUE_OUT-MIN_VALUE_OUT) * iReturn + MIN_VALUE_OUT

        if iReturn < MIN_VALUE_OUT:
            iReturn = MIN_VALUE_OUT
        elif iReturn > MAX_VALUE_OUT:
            iReturn = MAX_VALUE_OUT

        return round(iReturn)

    def _getSync(self):

        if self.sbus.inWaiting() > 0:
            #print(self.sbus.inWaiting())
            if self.startByteFound:
                if self.frameIndex == (self.SBUS_FRAME_LEN - 1):
                    # self.sbus.read(self.sbusBuff)  # end of frame byte
                    self.sbusBuff = self.sbus.read(1)

                    if self._bytes_to_int(self.sbusBuff) == 0:  # TODO: Change to use constant var value
                        self.startByteFound = False
                        self.isSync = True
                        self.frameIndex = 0

                        # self.get_new_data()
                else:
                    self.sbusBuff = self.sbus.read(1)  # keep reading 1 byte until the end of frame
                    self.frameIndex += 1
            else:

                self.frameIndex = 0
                while (self.sbus.inWaiting() > 0):
                    self.sbusBuff = self.sbus.read(1)  # read 1 byte
                    #print(self.sbusBuff, self._bytes_to_int(self.sbusBuff))
                    if self._bytes_to_int(self.sbusBuff) == 15:  # TODO: Change to use constant var value
                        self.startByteFound = True
                        self.frameIndex += 1
                        break
                    sleep(0.0001)


    def _bytes_to_int(self, bytes):
        result = 0
        for b in bytes:
            result = result * 256 + int(b)
        return result


    def _startReceive(self, eSetter):

        iSyncs=0
        while not eSetter.is_set():

            d1 = datetime.now()

            #if self.resyncEvent > 14:
            #    print("reconnect", self.sbus.inWaiting())
                #self.sbus.close()
                #sleep(0.03)
                #self._openUart()
                #self.sbus.open()
            #    self.resyncEvemt = 0

            try:
                self._get_new_data()

            except Exception as e:
                print(e)
                sleep(0.3)
                # self.openUart()
                self.sbus.close()
                sleep(0.5)
                self.sbus.open()
                self.isSync = False
                self.startByteFound = False
                self.frameIndex = 0
                self.sbusChannels = array.array('H', [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,0,0])

            if self.isSync:

                iSyncs =0
                #print((datetime.now() - d1).microseconds)
                while (datetime.now() - d1).microseconds < 500:
                    sleep(0.00001)
            else:
                iSyncs +=1
                while (datetime.now() - d1).microseconds < 100:
                    sleep(0.00001)

    def _get_new_data(self):

        if self.isSync:

            if self.sbus.inWaiting() >= self.SBUS_FRAME_LEN:
                self.sbus.readinto(self.sbusFrame)  # read the whole frame

                if (self.sbusFrame[0] == 15 and self.sbusFrame[
                    self.SBUS_FRAME_LEN - 1] == 0):  # TODO: Change to use constant var value
                    self.validSbusFrame += 1
                    self.outOfSyncCounter = 0
                    self._decodeFrame()
                else:
                    self.lostSbusFrame += 1
                    self.outOfSyncCounter += 1

                if self.outOfSyncCounter > self.OUT_OF_SYNC_THD:
                    self.isSync = False
                    self.resyncEvent += 1

                self.iempty=0
            else:
                self.iempty +=1

        else:
            self._getSync()


if __name__== "__main__":
    rx=SBUSReceiver("/dev/ttyAMA0")

    while True:

        sleep(0.1)
