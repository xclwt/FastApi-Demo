from datetime import datetime

import pymysql
from PanasonicPlcDataParser import plc
from fastapi import FastAPI, Response, status

import PostBody as pb
import funcs
from const import const

# 打开数据库连接
db = pymysql.connect(const.ADDRESS, const.USER_NAME, const.PASSWORD, const.DATABASE)

# 使用cursor()方法获取操作游标
cursor = db.cursor()

# 建立deviceId->plc.DeviceTypeEnum索引
sql_overall = "SELECT deviceId, deviceRemarks FROM device_info;"
cursor.execute(sql_overall)
results_overall = cursor.fetchall()
device_dict = dict()

for row in results_overall:
    if row[1] == "单头激光上料机":
        device_dict[row[0]] = plc.DeviceTypeEnum.SINGLE_HEAD_CUTTING_FEEDING_MACHINE
    elif row[1] == "中转仓AGV机":
        device_dict[row[0]] = plc.DeviceTypeEnum.TRANSIT_WAREHOUSE_AGV_MACHINE
    elif row[1] == "机器人测厚机":
        device_dict[row[0]] = plc.DeviceTypeEnum.ROBOT_THICKNESS_MEASURING_MACHINE
    else:
        device_dict[row[0]] = plc.DeviceTypeEnum.ORTHER_MACHINE

app = FastAPI()


@app.get("/api/v1/products")
async def get_products(deviceid: str, date: str, shift: funcs.ShiftParam):
    deviceid_list = deviceid.split(',')

    year = int(date[0:4])
    month = int(date[4:6])
    day = int(date[6:8])
    date = "{:0>2d}-{:0>2d}-{:0>2d}".format(year, month, day)

    start_timestamp = funcs.date_to_timestamp(year, month, day, shift)
    end_timestamp = start_timestamp + const.INTERVAL

    results = dict()

    for id_str in deviceid_list:
        # 设备状态
        sql = '''
                 SELECT deviceStatus FROM device_info 
                 WHERE deviceId="{}"
              '''.format(id_str)

        cursor.execute(sql)
        select_results = cursor.fetchall()

        # 无信息设备
        if len(select_results) == 0:
            tmp = dict()
            tmp["error"] = "{}: device not found.".format(id_str)
        else:
            tmp = dict()
            tmp["status"] = select_results[0][0]

            # 订单号及订单产量
            sql = '''
                     SELECT order_id, order_products FROM device_mes_table 
                     WHERE device_id="{}" AND work_date="{}" AND work_shift="{}"
                  '''.format(id_str, date, const.SHIFT[shift])

            cursor.execute(sql)
            select_results = cursor.fetchall()

            if len(select_results) != 0:
                tmp["order_id"] = select_results[0][0]
                tmp["order_product"] = select_results[0][1]
            else:
                tmp["order_id"] = ""
                tmp["order_product"] = ""
            # 产量
            sql = '''
                     SELECT deviceDataValue, opTime, deviceDataType FROM device_log 
                     WHERE deviceId="{}" AND opTime>{} AND opTime<{} AND (deviceDataType="{}" OR deviceDataType="{}")
                     ORDER BY opTime ASC;
                  '''.format(id_str, start_timestamp, end_timestamp, const.UART, const.IO1)

            cursor.execute(sql)
            select_results = cursor.fetchall()

            # 无信息设备
            if len(select_results) == 0:
                tmp["product"] = 0
            else:
                product_list = funcs.plc_details_statics(id_str, select_results, device_dict)
                tmp["product"] = sum(product_list)

        results[id_str] = tmp

    return results


@app.get("/api/v1/alarm")
async def get_alarm(deviceid: str, start_timestamp: int, end_timestamp: int):
    deviceid_list = deviceid.split(',')

    results = dict()

    for id_str in deviceid_list:
        sql = '''
                SELECT deviceDataValue, opTime FROM device_log 
                WHERE deviceId="{}" AND deviceDataType="{}" AND opTime>{} AND opTime<{}
                ORDER BY opTime ASC;
              '''.format(id_str, const.UART, start_timestamp, end_timestamp)

        cursor.execute(sql)
        select_results = cursor.fetchall()

        tmp = list()

        for row in select_results:
            alarm_info = plc.DataParser(device_dict[id_str],
                                        plc.DataTypeEnum.ALARM_DATA,
                                        row[0])
            timestamp = str(datetime.fromtimestamp(row[1]))

            merge_info = "{} {}".format(timestamp, alarm_info)

            # 排除空报警信息
            if alarm_info != "":
                tmp.append(merge_info)

        # 无信息设备
        if len(select_results) == 0:
            tmp = dict()
            tmp["error"] = "{}: device not found.".format(id_str)

        results[id_str] = tmp

    return results


@app.get("/api/v1/devices")
async def get_all():
    sql = "SELECT deviceId, deviceName, deviceRemarks FROM device_info"

    cursor.execute(sql)
    select_results = cursor.fetchall()

    results = dict()

    for row in select_results:
        device_id = row[0]
        tmp = dict()
        tmp["device_name"] = row[1]
        tmp["device_info"] = row[2]
        results[device_id] = tmp

    return results


@app.get("/api/v1/users")
async def get_users():
    sql = "SELECT account, password, name, mobilephone, is_admin, status FROM ef_user"

    cursor.execute(sql)
    select_results = cursor.fetchall()

    results = dict()

    for row in select_results:
        account = row[0]
        tmp = dict()
        tmp["account"] = row[0]
        tmp["password"] = row[1]
        tmp["user_name"] = row[2]
        tmp["mobilephone"] = row[3]
        tmp["is_admin"] = row[4]
        tmp["user_status"] = row[5]
        results[account] = tmp

    return results


@app.get("/api/v1/roles")
async def get_roles():
    sql = "SELECT id, name, info, status FROM ef_role"

    cursor.execute(sql)
    select_results = cursor.fetchall()

    results = dict()

    for row in select_results:
        name = row[1]
        tmp = dict()
        tmp["id"] = row[0]
        tmp["name"] = row[1]
        tmp["info"] = row[2]
        tmp["status"] = row[3]
        results[name] = tmp

    return results


@app.get("/api/v1/{search_for}")
async def get_details(search_for: funcs.SearchParam, deviceid: str, date: str, shift: funcs.ShiftParam):
    deviceid_list = deviceid.split(',')

    year = int(date[0:4])
    month = int(date[4:6])
    day = int(date[6:8])

    start_timestamp = funcs.date_to_timestamp(year, month, day, shift)
    end_timestamp = start_timestamp + const.INTERVAL

    return funcs.plc_statics(search_for, start_timestamp, end_timestamp, cursor, deviceid_list, device_dict)


@app.post("/api/v1/login")
async def login(response: Response, body: pb.LoginBody):
    sql = """
             SELECT id, account, password, name, mobilephone, is_admin, status FROM ef_user
             WHERE account="{}" AND status={}
          """.format(body.account, const.VALIDUSER)

    cursor.execute(sql)
    select_results = cursor.fetchall()

    if len(select_results) == 0:
        response.status_code = status.HTTP_404_NOT_FOUND
        err_results = funcs.gen_error("10101", "Invaild account")
        return err_results

    results = dict()

    results["use_id"] = select_results[0][0]
    results["account"] = select_results[0][1]
    results["password"] = select_results[0][2]

    if body.password != results["password"]:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        err_results = funcs.gen_error("10102", "Password is wrong")
        return err_results

    results["user_name"] = select_results[0][3]
    results["mobilephone"] = select_results[0][4]
    results["is_admin"] = select_results[0][5]
    results["use_status"] = select_results[0][6]

    sql = """SELECT role_id FROM ef_user_role
             WHERE user_id={}
          """.format(results["use_id"])

    cursor.execute(sql)
    select_results = cursor.fetchall()

    if len(select_results) == 0:
        results["role_id"] = ""
    else:
        results["role_id"] = select_results[0][0]

        sql = """SELECT name, info, status FROM ef_role
                 WHERE id={}
              """.format(results["role_id"])

        cursor.execute(sql)
        select_results = cursor.fetchall()

        results["role_name"] = select_results[0][0]
        results["role_info"] = select_results[0][1]
        results["role_status"] = select_results[0][2]

        sql = """SELECT b.id, b.name
                 FROM ef_role_access a INNER JOIN ef_access b
                 WHERE a.access_id=b.id AND a.role_id = {}
                 ORDER BY b.id ASC
              """.format(results["role_id"])

        cursor.execute(sql)
        select_results = cursor.fetchall()

        for row in select_results:
            results[row[0]] = row[1]

    return results


@app.post("/api/v1/users")
async def create_user(response: Response, body: pb.GetUserBody):
    sql = """
             INSERT INTO ef_user (account, password, name, mobilephone) 
             SELECT "{}", "{}", "{}", "{}" FROM DUAL 
             WHERE NOT EXISTS (SELECT * FROM ef_user WHERE account="{}");
          """.format(body.account, body.password, body.name, body.mobilephone, body.account)

    change = cursor.execute(sql)

    if change == const.NOCHANGE:
        response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        err_results = funcs.gen_error("10103", "Account exist")
        return err_results

    db.commit()

    response.status_code = status.HTTP_201_CREATED
    err_results = funcs.gen_error("201", "Account created successfully")
    return err_results


@app.post("/api/v1/roles")
async def create_role(response: Response, body: pb.GetRoleBody):
    sql = """
             INSERT INTO ef_role (name, info) 
             SELECT "{}", "{}" FROM DUAL 
             WHERE NOT EXISTS (SELECT * FROM ef_role WHERE name="{}");
          """.format(body.name, body.info, body.name)

    change = cursor.execute(sql)

    if change == const.NOCHANGE:
        response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        err_results = funcs.gen_error("10104", "Role exist")
        return err_results

    db.commit()

    response.status_code = status.HTTP_201_CREATED
    err_results = funcs.gen_error("201", "Account created successfully")
    return err_results


@app.put("/api/v1/users/{user_id}")
async def update_user(response: Response, body: pb.UpdateUserBody, user_id: int):
    sql = """
             UPDATE ef_user
             SET account="{}", password="{}", mobilephone="{}"
             WHERE id={}
          """.format(body.account, body.password, body.mobilephone, user_id)
    cursor.execute(sql)
    db.commit()

    response.status_code = status.HTTP_201_CREATED
    err_results = funcs.gen_error("201", "Successfully modified")

    return err_results


@app.put("/api/v1/roles/{role_id}")
async def update_role(response: Response, body: pb.UpdateRoleBody, role_id: int):
    sql = """
             UPDATE ef_role
             SET name="{}", info="{}"
             WHERE id={}
          """.format(body.name, body.info, role_id)
    cursor.execute(sql)
    db.commit()

    response.status_code = status.HTTP_201_CREATED
    err_results = funcs.gen_error("201", "Successfully modified")

    return err_results


@app.put("/api/v1/user_role/{user_id}")
async def create_user_role(response: Response, body: pb.UserRoleBody, user_id: int):
    sql = """
             INSERT INTO ef_user_role (user_id, role_id) 
             VALUES ({}, {}) 
             ON DUPLICATE KEY UPDATE
             role_id={}
          """.format(user_id, body.role_id, body.role_id)
    cursor.execute(sql)
    db.commit()

    response.status_code = status.HTTP_201_CREATED
    err_results = funcs.gen_error("201", "Successfully modified")

    return err_results


@app.delete("/api/v1/users/{user_id}")
async def delete_user(response: Response, user_id: int):
    sql = """
             DELETE FROM ef_user
             WHERE id={}
          """.format(user_id)
    cursor.execute(sql)
    db.commit()

    response.status_code = status.HTTP_204_NO_CONTENT
    err_results = funcs.gen_error("204", "Successfully deleted")

    return err_results


@app.delete("/api/v1/roles/{role_id}")
async def delete_role(response: Response, role_id: int):
    sql = """
             DELETE FROM ef_role
             WHERE id={}
          """.format(role_id)
    cursor.execute(sql)
    db.commit()

    response.status_code = status.HTTP_204_NO_CONTENT
    err_results = funcs.gen_error("204", "Successfully deleted")

    return err_results
