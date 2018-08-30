from enum import IntFlag
from os import path
from collections import defaultdict
import sqlite3
import pika


class Status(IntFlag):
    read = 1
    trade = 3
    admin = 5


class Trigger:
    def __init__(self, type, msg):
        self.type = type
        self.msg = msg
        self.erased = False


class User:
    def __init__(self, user_id, nickname, status, orders, is_new):
        self.user_id = user_id
        self.nickname = nickname
        self.status = status
        self.orders = orders
        self.is_new = is_new


class Order:
    def __init__(self, order_id, user_id, res_code, bought_amount, wanted_amount, price, is_new):
        self.order_id = order_id
        self.user_id = user_id
        self.res_code = res_code
        self.bought_amount = bought_amount
        self.wanted_amount = wanted_amount
        self.price = price
        self.is_new = is_new


class DBHelper:
    @staticmethod
    def init_db():
        try:
            if path.exists("cwdb.db"):
                return sqlite3.connect("cwdb.db")
            else:
                con = sqlite3.connect("cwdb.db")
                con.execute(
                    '''CREATE TABLE triggers (id INTEGER, name TEXT, type TEXT, msg TEXT, PRIMARY KEY (id, name))''')
                con.execute('''CREATE TABLE users (id INTEGER PRIMARY KEY, nickname TEXT, status INTEGER)''')
                con.execute(
                    '''CREATE TABLE orders (id INTEGER PRIMARY KEY , user_id INTEGER, res_code INTEGER, bought_amount 
                                            INTEGER, wanted_amount INTEGER, price INTEGER)''')
                return con

        except Exception as ex:
            print("Couldn't establish proper connection with sqlite db, err: ", ex)

    @staticmethod
    def load_triggers():
        try:
            con = DBHelper.init_db()
            con.row_factory = sqlite3.Row
            cur = con.cursor()

            cur.execute("SELECT * FROM triggers")

            triggers = defaultdict(dict)
            for row in cur:
                triggers[row["id"]][row["name"]] = Trigger(row["type"], row["msg"])

            return triggers
        except Exception as ex:
            print("Couldn't load triggers due to: " + ex)
            con.rollback()
        finally:
            con.close()

    @staticmethod
    def save_triggers(chat_triggers):
        try:
            con = DBHelper.init_db()

            for chat, triggers in chat_triggers.items():
                for name in (key for key, value in triggers.items() if value.erased):
                    con.execute("DELETE FROM triggers WHERE id =? AND name =?", (chat, name))

            cleaned = defaultdict(dict)
            for chat, triggers in chat_triggers.items():
                for key, value in triggers.items():
                    if not value.erased:
                        cleaned[chat][key] = value

            for chat, triggers in cleaned.items():
                for name, data in triggers.items():
                    con.execute("INSERT OR IGNORE INTO triggers VALUES(?,?,?,?)", (chat, name, data.type, data.msg))

            con.commit()
            return cleaned

        except Exception as ex:
            print("Couldn't save triggers into db, error: " + ex)
            con.rollback()
        finally:
            con.close()

    @staticmethod
    def load_orders(user_id):
        try:
            con = DBHelper.init_db()
            con.row_factory = sqlite3.Row
            cur = con.cursor()

            cur.execute("SELECT * FROM orders WHERE user_id =?", (user_id,))

            user_orders = []
            for row in cur:
                order = Order(row["id"], row["user_id"], row["res_code"], row["bought_amount"], row["wanted_amount"],
                              row["price"])
                user_orders.append(order)

            return user_orders
        except Exception as ex:
            print("Couldn't load orders due to: " + ex)
            con.rollback()
        finally:
            con.close()

    @staticmethod
    def save_orders(orders):
        try:
            con = DBHelper.init_db()
            for order in (row for row in orders if row.is_new):
                con.execute("INSERT INTO orders VALUES(NULL,?,?,?,?,?,)",
                            (order.user_id, order.res_code, order.bought_amount, order.wanted_amount, order.price))

            for order in (row for row in orders if not row.is_new):
                con.execute("UPDATE OR IGNORE orders SET wanted_amount = ? WHERE id = ?",
                            (order.user_id, order.wanted_amount))
            con.commit()

        except Exception as ex:
            print("Couldn't save new orders, error: " + ex)
            con.rollback()
        finally:
            con.close()

    @staticmethod
    def update_order(order):
        try:
            con = DBHelper.init_db()
            con.execute("UPDATE orders SET bought_amount = ? WHERE id = ?", (order.order_id, order.bought_amount))
            con.commit()

        except Exception as ex:
            print("Couldn't update order[{0}] error: {1}".format(order.order_id, ex))
            con.rollback()
        finally:
            con.close()

    @staticmethod
    def delete_order(order):
        try:
            con = DBHelper.init_db()
            con.execute("DELETE FROM orders WHERE id = ?", (order.order_id,))
            con.commit()

        except Exception as ex:
            print("Couldn't delete order[{0}] error: {1}".format(order.order_id, ex))
            con.rollback()
        finally:
            con.close()

    @staticmethod
    def load_users():
        try:
            con = DBHelper.init_db()
            con.row_factory = sqlite3.Row
            cur = con.cursor()

            users = {}
            for row in cur.execute("SELECT * FROM users"):
                user_id = row["id"]
                orders = DBHelper.load_orders(user_id)
                user = User(user_id, row["nickname"], Status(row["status"]), orders, False)
                users[user_id] = user

            return users
        except Exception as ex:
            print("Couldn't load user data due to: " + ex)
            con.rollback()
        finally:
            con.close()

    @staticmethod
    def save_new_user(user):
        try:
            DBHelper.save_orders(user.orders)
            con = DBHelper.init_db()
            con.execute("INSERT OR REPLACE INTO users VALUES(?,?,?)", (user.user_id, user.nickname, user.status))
            con.commit()

        except Exception as ex:
            print("Couldn't put user record into db, error: " + ex)
            con.rollback()
        finally:
            con.close()

    @staticmethod
    def set_user_status(user):
        try:
            con = DBHelper.init_db()
            con.execute("UPDATE OR IGNORE users SET status = ? WHERE user_id = ?", (user.status.value, user.user_id))
            con.commit()

        except Exception as ex:
            print("Couldn't change status for user[{0}], error: ".format(user.status, ex))
            con.rollback()
        finally:
            con.close()

    @staticmethod
    def save_new_items(users):
        for user_id, user in users.items():
            DBHelper.save_new_user(user)


class CWAPIHelper:
    def __init__(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self.channel = self.connection.channel()


class BotEnv:
    def __init__(self):
        self.users = DBHelper.load_users()
        self.triggers = DBHelper.load_triggers()

    def __del__(self):
        self.dump()

    def dump(self):
        self.triggers = DBHelper.save_triggers(self.triggers)
        DBHelper.save_new_items(self.users)

    def get_chat_triggers(self, chat_id, name):
        triggers = self.triggers.get(chat_id, {})

        keys = [key for key, value in triggers.items() if not value.erased]
        trigger_list = "\n".join(keys) if len(keys) else "is empty!"

        return "Trigger list of chat '{}':\n".format(name) + trigger_list

    def add_user(self, user_id, nickname, status):
        if user_id not in self.users:
            self.users[user_id] = User(user_id, nickname, Status(status), [], True)

    def user_exists(self, user_id):
        return user_id in self.users

    def get_user_status(self, user_id):
        if user_id in self.users:
            return self.users[user_id].status
        else:
            return 0

    def set_user_status(self, user_id, status):
        if user_id in self.users:
            self.users[user_id].status = status

    def get_user_orders(self, user_id):
        if user_id in self.users:
            return self.users[user_id]
        else:
            return None

    def get_all_user_info(self):
        all_info = []
        for user in self.users:
            all_info.append(self.get_user_info(user))

        user_list = "\n" + "\n\n".join(all_info) if len(all_info) else " is empty"
        return "User list:" + user_list

    def get_user_info(self, user_id):
        if user_id in self.users:
            user = self.users[user_id]
            return "🌝User: @{}\n🔑Id: {}\n🌚Status: {}".format(user.nickname, user_id, user.status.name)
        else:
            return "User is not found in bot db."
