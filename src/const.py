"""
文件名: constants.py
本文件用于定义项目中的常量
"""


class Const(object):
    class ConstError(TypeError):
        pass

    class ConstCaseError(ConstError):
        pass

    def __setattr__(self, name, value):
        if name in self.__dict__:  # 判断是否已经被赋值，如果是则报错
            raise self.ConstError("Can't change const.%s" % name)
        if not name.isupper():  # 判断所赋值是否是全部大写，用来做第一次赋值的格式判断，也可以根据需要改成其他判断条件
            raise self.ConstCaseError('const name "%s" is not all supercase' % name)

        self.__dict__[name] = value


const = Const()

const.ADDRESS = "localhost"

const.USER_NAME = "iot_test"

const.PASSWORD = "test123"

const.DATABASE = "famqtt_test"

const.UART = "UART"

const.IO1 = "IO1"

# 班次开始与结束时间间隔 (秒)
const.INTERVAL = 12 * 60 * 60

# 每小时3600秒
const.ONE_HOUR = 3600

const.UART_PRODUCT_INCREMENT = 1

const.IO1_PRODUCT_INCREMENT = 2

const.VALIDUSER = 1

const.NOCHANGE = 0

const.SHIFT = {"day": "白班", "night": "晚班"}
