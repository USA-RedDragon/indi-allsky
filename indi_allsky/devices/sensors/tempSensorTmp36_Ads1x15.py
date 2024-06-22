#import time
import logging

from .sensorBase import SensorBase
from ..exceptions import SensorReadException


logger = logging.getLogger('indi_allsky')


class TempSensorTmp36_Ads1x15(SensorBase):

    def update(self):

        try:
            sensor_v = float(self.sensor.voltage)
        except RuntimeError as e:
            raise SensorReadException(str(e)) from e


        temp_c = (sensor_v - 0.5) * 100  # 500mv offset


        logger.info('ADS1x15 TMP36 - temp: %0.1fc', temp_c)

        if self.config.get('TEMP_DISPLAY') == 'f':
            current_temp = self.c2f(temp_c)
        elif self.config.get('TEMP_DISPLAY') == 'k':
            current_temp = self.c2k(temp_c)
        else:
            current_temp = temp_c


        data = {
            'data' : (
                current_temp,
            ),
        }

        return data


class TempSensorTmp36_Ads1015_I2C(TempSensorTmp36_Ads1x15):

    def __init__(self, *args, **kwargs):
        super(TempSensorTmp36_Ads1015_I2C, self).__init__(*args, **kwargs)

        i2c_address_str = kwargs['i2c_address']
        pin_1_name = kwargs['pin_1_name']

        import board
        import busio
        import adafruit_ads1x15.ads1015 as ADS
        from adafruit_ads1x15.analog_in import AnalogIn

        i2c_address = int(i2c_address_str, 16)  # string in config
        pin1 = getattr(ADS, pin_1_name)

        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS.ADS1015(i2c, address=i2c_address)
        self.sensor = AnalogIn(ads, pin1)


class TempSensorTmp36_Ads1115_I2C(TempSensorTmp36_Ads1x15):

    def __init__(self, *args, **kwargs):
        super(TempSensorTmp36_Ads1115_I2C, self).__init__(*args, **kwargs)

        i2c_address_str = kwargs['i2c_address']
        pin_1_name = kwargs['pin_1_name']

        import board
        import busio
        import adafruit_ads1x15.ads1115 as ADS
        from adafruit_ads1x15.analog_in import AnalogIn

        i2c_address = int(i2c_address_str, 16)  # string in config
        pin1 = getattr(ADS, pin_1_name)

        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS.ADS1115(i2c, address=i2c_address)
        self.sensor = AnalogIn(ads, pin1)


