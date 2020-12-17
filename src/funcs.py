from datetime import datetime
from enum import Enum

from PanasonicPlcDataParser import plc

from const import const


class SearchParam(str, Enum):
    standby = "standby"
    details = "details"


class ShiftParam(str, Enum):
    day = "day"
    night = "night"


def gen_error(err_id, err_msg):
    err_results = dict()
    tmp = dict()

    tmp["err_id"] = err_id
    tmp["err_msg"] = err_msg
    err_results["error"] = tmp

    return err_results


def date_to_timestamp(year, month, day, shift):
    if shift == ShiftParam.day:
        timestamp = datetime(year, month, day, 8, 00).timestamp()
    elif shift == ShiftParam.night:
        timestamp = datetime(year, month, day, 20, 00).timestamp()

    return timestamp


def standby_count(interval_list, cur_timestamp, prev_timestamp):
    cur_datetime = datetime.fromtimestamp(cur_timestamp)
    prev_datetime = datetime.fromtimestamp(prev_timestamp)

    if cur_datetime.hour == prev_datetime.hour:
        interval_list = standby_count_sub(interval_list,
                                          cur_datetime.hour,
                                          cur_timestamp - prev_timestamp)
    else:
        interval_list = standby_count_sub(interval_list,
                                          prev_datetime.hour,
                                          datetime_to_end(prev_timestamp))
        interval_list = standby_count_sub(interval_list,
                                          cur_datetime.hour,
                                          datetime_to_start(cur_timestamp))

        for hour in range(prev_datetime.hour + 1, cur_datetime.hour):
            interval_list = standby_count_sub(interval_list,
                                              hour,
                                              3600)

    return interval_list


def standby_count_sub(interval_list, hour, count):
    if hour < 8:
        interval_list[hour + 4] += count
    elif hour < 20:
        interval_list[hour - 8] += count
    else:
        interval_list[hour - 20] += count

    return interval_list


def details_count(product_list, hour, count):
    if hour < 8:
        product_list[hour + 4] += count
    elif hour < 20:
        product_list[hour - 8] += count
    else:
        product_list[hour - 20] += count

    return product_list


def datetime_to_start(timestamp):
    return timestamp % 3600


def datetime_to_end(timestamp):
    return 3600 - datetime_to_start(timestamp)


def tran_second(seconds):
    minutes = int(seconds) // 60
    seconds = int(seconds) % 60

    return "{:0>2d}:{:0>2d}".format(minutes, seconds)


def plc_details_statics(id_str, select_results, device_dict):
    product_list = [0] * 12

    # 对查询出的每条记录进行处理
    for row in select_results:
        if row[2] == const.UART:
            cur_product = plc.DataParser(device_dict[id_str],
                                         plc.DataTypeEnum.PRODUCT_DATA,
                                         row[0])

            if cur_product != "":
                cur_timestamp = row[1]
                cur_datetime = datetime.fromtimestamp(cur_timestamp)

                product_list = details_count(product_list,
                                             cur_datetime.hour,
                                             const.UART_PRODUCT_INCREMENT)
        elif row[2] == const.IO1:
            if row[0] == "1":
                cur_timestamp = row[1]
                cur_datetime = datetime.fromtimestamp(cur_timestamp)
                product_list = details_count(product_list,
                                             cur_datetime.hour,
                                             const.IO1_PRODUCT_INCREMENT)

    return product_list


def plc_standby_statics(id_str, prev_timestamp, select_results, device_dict):
    interval_list = [0] * 12

    # 对查询出的每条记录进行处理
    for row in select_results:
        if row[2] == const.IO1:
            cur_status = row[0]
            cur_timestamp = row[1]

        elif row[2] == const.UART:
            cur_status = plc.DataParser(device_dict[id_str],
                                        plc.DataTypeEnum.IDLE_DATA,
                                        row[0])
            cur_timestamp = row[1]

        if cur_status == "1":
            interval_list = standby_count(interval_list, cur_timestamp, prev_timestamp)
            prev_timestamp = cur_timestamp
        elif cur_status == "0":
            prev_timestamp = cur_timestamp

    return interval_list


def plc_statics(search_for, start_timestamp, end_timestamp, cursor, deviceid_list, device_dict):
    results = dict()

    for id_str in deviceid_list:
        sql = '''
                SELECT deviceDataValue, opTime, deviceDataType FROM device_log 
                WHERE deviceId="{}" AND opTime>={} AND opTime<{} AND (deviceDataType="{}" OR deviceDataType="{}")
                ORDER BY opTime ASC;
              '''.format(id_str, start_timestamp, end_timestamp, const.UART, const.IO1)

        cursor.execute(sql)
        select_results = cursor.fetchall()

        # 无信息设备
        if len(select_results) == 0:
            tmp = {"error": "{}: device not found.".format(id_str)}
        else:
            tmp = dict()

            if search_for == SearchParam.standby:
                interval_list = plc_standby_statics(id_str, start_timestamp, select_results, device_dict)

                # 生成该deviceId对应的待机时间表
                for i in range(12):
                    key_str = "{:0>2d}－{:0>2d}".format((8 + i) % 12, (9 + i) % 12)

                    if start_timestamp + i * 3600 < datetime.now().timestamp():
                        tmp[key_str] = tran_second(interval_list[i])
                    else:
                        tmp[key_str] = "0"

            elif search_for == SearchParam.details:
                product_list = plc_details_statics(id_str, select_results, device_dict)

                # 生成该deviceId对应的产量表
                for i in range(12):
                    key_str = "{:0>2d}－{:0>2d}".format((8 + i) % 12, (9 + i) % 12)
                    tmp[key_str] = product_list[i]

                tmp["total"] = sum(product_list)

        results[id_str] = tmp

    return results
