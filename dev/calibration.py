# meas_freq.py: We want to get a feeling for the frequencies emitted by the TCS3200
# The value for a color component is calculated with the following formula:
# rgb = top * (Fv -Fb) / (Fw -Fb) where
# top is the maximum for each color component. This is generally 0xff or 255
# Fv is the frequency measured to the color component
# Fw is the frequency when measuring a white target
# Fb is the frequency when measuring a black target
# Before measuring the frequency of a color component and calculating the rgb value of a colored target
# we must measure the rgb frequencies for a black and a white target first
# These calibration values are stored in the _freq_black and _freq_white arrays. 
#
# Copyright (c) U. Raich
# Written for the course on the Internet of Things at the
# University of Cape Coast, Ghana
# The program is released under the MIT licence

from machine import Pin,Timer
import utime as time

class TCS3200(object):
    """
    This class reads RGB values from a TCS3200 colour sensor.

    GND   Ground.
    VDD   Supply Voltage (2.7-5.5V)
    LED   1: LEDs on, 0: LEDs off
    /OE   Output enable, active low. When OE is high OUT is disabled
         allowing multiple sensors to share the same OUT line.
    OUT   Output frequency square wave.
    S0/S1 Output frequency scale selection.
    S2/S3 Colour filter selection.
    
    OUT is a square wave whose frequency is proprtional to the
    intensity of the selected filter colour.
    
    S2/S3 selects between red, green, blue, and no filter.
    
    S0/S1 scales the frequency at 100%, 20%, 2% or off.
    
    To take a reading the colour filters are selected in turn for a
    fraction of a second and the frequency is read and converted to
    Hz.
    
    Default connections:
    TCS3200 WeMos GPIO
      S0     D2   21 
      S1     D1   22
      S2     D8   05
      S3     D5   18
      OUT    D6   19
      LED    D7   23
      OE     GND  
    """
    # class variables
    
    ON  = True  # on for debugging and the leds
    OFF = False # off

    RED   = (0,0) # S2 and S3 low
    BLUE  = (0,1) # S2 low, S3 high
    GREEN = (1,1) # S2 and S3 high
    CLEAR = (1,0) # S2 high and S3 low

    RED_COMP   = 0 # the color components
    GREEN_COMP = 1
    BLUE_COMP  = 2
    
    POWER_OFF       = (0,0) # S0 and S1 low
    TWO_PERCENT     = (0,1) # S0 low, S1 high
    TWENTY_PERCENT  = (1,0) # S0 high, S1 low
    HUNDRED_PERCENT = (1,1) # S0 and S1 high

    WHITE = True
    BLACK = False
    
    def __init__(self, OUT=19, S2=5, S3=18, S0=None, S1=None, LED=None,OE=None):
        """
        The gpios connected to the sensor OUT, S2, and S3 pins must
        be specified.  The S0, S1 (frequency) and LED and OE (output enable) 
        gpios are optional.
        The OE pin is missing on some TCS3200 boards
        """
        
        self._OUT = Pin(OUT,Pin.IN,Pin.PULL_UP)
        
        self._S2 = Pin(S2,Pin.OUT)
        self._S3 = Pin(S3,Pin.OUT)
        
        self._S0  = S0
        self._S1  = S1
        self._OE  = OE
        self._LED = LED
        
        
        if S0 and S1 :
            self._S0 = Pin(S0,Pin.OUT)
            self._S1 = Pin(S1,Pin.OUT)
            
        if LED :
            self._LED = Pin(LED,Pin.OUT)
            self._LED.on()
                
        if OE :
            self._OE =  Pin(OE,Pin.OUT)

        self._tim = Timer(0) # timer generating a timeout if the measurement takes to long
        self._timeout = 5000   # timeout in ms
        
        self._debug = self.OFF
        self._cycles = 100    # the number of cycles of the out signal for which the time is measured
        self._cycle = 0
        self._freq_div = self.POWER_OFF
        self._start_tick = 0
        self._end_tick = 0
        meas_finished = False
        # variables containing the calibration
        self._freq_black = [0]*3
        self._freq_white = [0]*3
        
    @property
    def debugging(self) :
        return self._debug
        
    @debugging.setter
    def debugging(self,onOff) :
        if onOff:
            print("Debugging switched on")
        else :
            print("Debugging switched off")
        self._debug = onOff

    # controls the illumination LEDs
    @property
    def led(self):
        # get the current state of the illumination leds
        return self._LED.value()
    
    @led.setter
    def led(self,onOff):
        if onOff:
            self._LED.on()
        else:
            self._LED.off()
            
    # sets the filters
    @property
    def filter(self):
        current_setting = (self._S2.value(),self._S3.value())
        if self._debug:
            if current_setting == self.RED:
                print("Red filter is set")
            elif current_setting == self.GREEN:
                print("Green filter is set")
            elif current_setting == self.BLUE :
                print("Blue filter is set")
            else:
                print("No filters are set. The filter setting is clear")
        return current_setting      
    
    @filter.setter
    def filter(self,filter_setting):
        if self._debug:
            print("Setting S2 to {:d} and S3 to {:d}".format(filter_setting[0],filter_setting[1]))
        self._S2.value(filter_setting[0])
        self._S3.value(filter_setting[1])

    @property
    def freq_divider(self):
        if not self._S0 or not self._S1:
            print("S0 or S1 signal is not connected. The frequency divider is therefore fixed")
            return
        current_freq_div = (self._S0.value(),self._S1.value())
        if self._debug:
            if current_freq_div == self.POWER_OFF:
                print("Device set to sleep mode")
            elif current_freq_div == self.TWO_PERCENT:
                print("Frequency divided by a factor 50")
            elif current_freq_div == self.TWENTY_PERCENT:
                print("Frequency divided by a factor 5")
            else:
                print("Frequency at 100%")

        return current_freq_div
    
    @freq_divider.setter
    def freq_divider(self,freq_div):
        if not self._S0 or not self._S1:
            print("S0 or S1 signal is not connected. The frequency divider is therefore fixed and cannot be set")
            return
        
        if self._debug:
            print("Setting S0 to {:d} and S1 to {:d}".format(freq_div[0],freq_div[1]))
        self._S0.value(freq_div[0])
        self._S1.value(freq_div[1])

    def power_off(self):
        self.freq_divider = self.POWER_OFF
        
    @property
    def cycles(self):
        return self._cycles

    @cycles.setter
    def cycles(self,no_of_cycles):
        if no_of_cycles < 1:
            print("The number of cycles must be at least 1")
            return
        self._cycles = no_of_cycles
        if self._debug:
            print("No of cycles to be measured was set to {:d}".format(self._cycles))

    @property
    def meas(self):
        if self._debug:
            if self._meas:
                print("Measurement is started")
            else:
                print("Measurement is stopped")
        return self._meas
    
    @meas.setter
    def meas(self,startStop):
        if startStop:
            self._meas = True
            self._cycle = 0
            self._start_tick = 0
            self._end_tick = 0
            if self._debug:
                print("Measurement handler started")
            self._OUT.irq(trigger=Pin.IRQ_RISING,handler=self._cbf)
            # start the timeout counter
            self._tim.init(period=self._timeout, mode=Timer.ONE_SHOT, callback=self._timeout_handler)
        else:
            self._meas=False
            self._OUT.irq(trigger=Pin.IRQ_RISING,handler=None)
            if self._debug:
                print("Measurement handler stopped")
            # disarm the timeout
            self._tim.deinit()
            
    def calib(self,black_or_white):
        if black_or_white == self.BLACK:
            return self._freq_black
        else:
            return self._freq_white

    @property
    def meas_freqs(self):
        # set the filter to red
        freqs = [None]*3
        self.filter = self.RED
        self.meas = self.ON       # start the measurement
        while self._end_tick == 0:
            time.sleep_ms(10)
        freqs[self.RED_COMP] = self.measured_freq
        
        self.filter = self.GREEN
        self.meas = self.ON       # start the measurement
        while self._end_tick == 0:
            time.sleep_ms(10)
        freqs[self.GREEN_COMP] = self.measured_freq
        
        self.filter = self.BLUE
        self.meas = self.ON       # start the measurement
        while self._end_tick == 0:
            time.sleep_ms(10)
        freqs[self.BLUE_COMP] = self.measured_freq
        if self._debug:
            print("Measured frequencies: ",freqs)
        return freqs
    
    def calibrate(self):
        print("Calibrating black object, press enter to start",end='')
        self.wait_for_return()
        self._freq_black = self.meas_freqs
        print("Calibrating white object, press enter to start",end='')
        self.wait_for_return()
        self._freq_white = self.meas_freqs
        
    def wait_for_return(self):
        dummy = input()
        
    @property
    def timeout(self):
        return self._timeout

    @timeout.setter
    def timeout(self,timeout_ms):
        self._timeout = timeout_ms
    
    @property
    def measured_freq(self):
        duration = self._end_tick - self._start_tick  # measurement duration
        frequency = 1000000 * self._cycles/duration   # duration is measured in us
        return frequency
    
    # This is the callback function that measures the time taken by a predefined no of cycles of the out signal
    def _cbf(self,src):
        t = time.ticks_us()
        if self._cycle == 0:
            self._start_tick = t
        if self._cycle >= self._cycles: # the number of cycles has been reached
            self._end_tick = t
            self.meas=self.OFF
            return
        self._cycle += 1
        
    # The timeout handler raises a timeout exception
    def _timeout_handler(self,src):
        # stop the measurement
        self._OUT.irq(trigger=Pin.IRQ_RISING,handler=None)
        # raise the timeour exception
        raise Exception("Measurement Timeout!")
        
# This part is the main project and should later go into a separate file

# create an TCS3200 object
tcs3200 = TCS3200(OUT=19, S2=5, S3=18, S0=21, S1=22, LED=23)

# set debugging on
tcs3200.debugging=tcs3200.ON

# switch the LEDs on
tcs3200.led = tcs3200.ON

# Set the frequency divider to 2% and read it back
tcs3200.freq_divider=tcs3200.TWO_PERCENT
print(tcs3200.freq_divider)
if tcs3200.freq_divider == tcs3200.TWO_PERCENT:
    print("Frequency divider is set to 2%")
else:
    print("Something went wrong when setting the frequency divider")

# Set no of cycles to be measured
tcs3200.cycles=100
tcs3200.calibrate()
black_freq = tcs3200.calib(tcs3200.BLACK)
print("Calibration frequencies for black: ",black_freq)
white_freq = tcs3200.calib(tcs3200.WHITE)
print("Calibration frequencies for white: ",white_freq)


