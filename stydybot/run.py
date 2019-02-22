
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import telegram
from telegram import ReplyKeyboardMarkup
import logging
import socket, socks, urllib, requests, pymysql.cursors
import hashlib, bcrypt, base64
import time
import json
import config as cfg

connection = pymysql.connect(host=cfg.db_host,user=cfg.db_user,password=cfg.db_pass,db=cfg.db_name)
chats_list = {}
class_btns = []
class_list = cfg.classes
for c in class_list:
    tmp = []
    tmp.append(c)
    class_btns.append(tmp)

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',level=logging.INFO)
logger = logging.getLogger(__name__)

class UserData:
    def __init__(self, is_write, text, sel = None, authed = False):
        self.write = is_write
        self.text = text
        self.authed = authed
        self.sel = sel

def WriteTextIntoDb(message, photo = None, doc = None):
    try:
        t = int(time.time())   
        usr_id = message.from_user.id
        sel = chats_list[message.chat_id][message.from_user.id].sel
        if (not message.text_markdown == None):
            text = message.text_markdown
        else:
            text = message.caption_markdown
        with connection.cursor() as curs:
            sql = "INSERT INTO study (user, className, content, photo, doc, time_add) VALUES (%(usr)s, %(cls)s, %(con)s, %(ph)s, %(dc)s, %(time)s)"
            data = {'usr': usr_id, 'cls': sel, 'con': text, 'ph': photo , 'dc': doc, 'time': t }
            result = curs.execute(sql, data)
            connection.commit()
        logger.warning('status: "%s"', result)
        return result
    except:
        return 0

def WriteFileIntoDb(userid, filename, url, typ):
    try:
        t = int(time.time())
        with connection.cursor() as curs:
            sql = "INSERT INTO files (author, type, filename, url, time_add) VALUES (%(usr)s, %(typ)s, %(fl)s, %(url)s, %(time)s)"
            data = {'usr': userid, 'typ': typ, 'fl': filename, 'url': url, 'time': t }
            result = curs.execute(sql, data)
            connection.commit()
        logger.warning('status: "%s"', result)
        return result
    except:
        return 0
    finally:
        pass

def ParseContentFromFile(data):
    return

def GetClasses():
    return

def CheckAuth(uid):
    try:
        result = [False, None]
        with connection.cursor() as cursor:
            sql = "SELECT name FROM cred WHERE tg_id = %(usr)s"
            data = {'usr': uid}
            cursor.execute(sql, data)
            res = cursor.fetchall()
            connection.commit()
            for row in res:
                if (row[0] != None):
                    result = [True, row[0]]        
        return result 
    except:
        return [False, None]

def Auth(msg, uid):
    c = msg.split()
    try:
        result = [False, None]
        with connection.cursor() as cursor:
            sql = "SELECT password, name FROM cred WHERE username = %(usr)s"
            data = {'usr': c[0]}
            cursor.execute(sql, data)
            connection.commit()
            row = cursor._rows[0]            
            result[0] = bcrypt.checkpw(bytes(c[1],'utf-8'),bytes(row[0],'utf-8'))
            result[1] = row[1]
        if result[0]:
            with connection.cursor() as cursor:
                sql = "UPDATE cred SET tg_id = %(id)s WHERE username = %(usr)s"
                data = {'id': uid, 'usr': c[0]}
                cursor.execute(sql, data)
                connection.commit()  
                return result
        else:
            return result
    except:
        return [False, None]

#Start command
def start(bot, update):
    usr = userDataExist(update.message)
    if (CheckAuth(update.message.from_user.id)[0]):
        chats_list[update.message.chat_id][update.message.from_user.id].authed = True
        if(usr[0] == True or not usr[1].write):
            text = "Привет!\nВыберите предмет"
            reply_markup = telegram.ReplyKeyboardMarkup(class_btns, one_time_keyboard=True, resize_keyboard=True)
            update.message.reply_text(text, reply_markup=reply_markup, one_time_keyboard=True)
    else:
        text = "Воу-воу! Сначала залогинься\nДанные должны быть в формате <логин пароль> (только логин пробел и пароль).\n \nНе пали свои данные, логинься через ЛС @EzStudyBot"
        chats_list[update.message.chat_id][update.message.from_user.id].authed = 'now'
        update.message.reply_text(text)

def end(bot, update):
    global chats_list
    usr = userDataExist(update.message)
    if(usr[0] == True or usr[1].write):
        tmp = chats_list
        del tmp[update.message.chat_id][update.message.from_user.id]
        chats_list = tmp
        update.message.reply_text("Спасибо за ваш вклад!")

def help(bot, update):
    """Send a message when the command /help is issued."""
    update.message.reply_text('Help!')

def userDataExist(message):
    if (not message.chat_id in chats_list):
        chats_list[message.chat_id] = {}
    for usr in chats_list[message.chat_id]:
        if usr == message.from_user.id:
            return [True, chats_list[message.chat_id][message.from_user.id]]
    
    o = chats_list[message.chat_id][message.from_user.id] = UserData(False, message.text, None, CheckAuth(message.from_user.id)[0])
    return [False, o]

def GetFile(bot, file_id):
    file = bot.getFile(file_id)
    filename = base64.urlsafe_b64encode(hashlib.md5(bytes(file.file_id,'utf-8')).digest())
    ext = file.file_path.split('/')[-1].split('.')[1].lower()
    types = 'other'
    photo_ext = ['jpg', 'png', 'gif']
    doc_ext = ['doc', 'docx', 'odf', 'rtf', 'txt', 'pdf']
    if (ext in photo_ext):
        types = 'photo'
    elif (ext in doc_ext):
        types = 'doc'
    return [filename, file.file_path, types]

def MsgSorter(message):
    if (message.document):
        file = GetFile(message.document.bot, message.document.file_id)
        WriteFileIntoDb(message.from_user.id, file[0], file[1], file[2])
        WriteTextIntoDb(message, None, file[0])
    elif (message.photo):
        file = GetFile(message.photo[-1].bot, message.photo[-1].file_id)
        WriteFileIntoDb(message.from_user.id, file[0], file[1], file[2])
        WriteTextIntoDb(message, file[0])
    elif (message.text):
        WriteTextIntoDb(message)
    


def echo(bot, update):
    global connection
    if (connection._closed):
        connection = pymysql.connect(host=cfg.db_host,user=cfg.db_user,password=cfg.db_pass,db=cfg.db_name)
    usr = userDataExist(update.message)
    if (usr[0] == True and usr[1].write and usr[1].authed):
        MsgSorter(update.message)
    elif(usr[0] == True and usr[1].authed == True and not usr[1].write):
        if update.message.text in class_list:
            chats_list[update.message.chat_id][update.message.from_user.id].sel = update.message.text
            chats_list[update.message.chat_id][update.message.from_user.id].write = True
            reply_markup = telegram.ReplyKeyboardRemove()
            text = "Выбран предмет: " + update.message.text + "\nОтправьте документ или текст, который необходимо прикрепить.\nДокумент может быть в формате doc, docx, odf, txt \nВесь текст и изображения будут импортированы в базу"
            update.message.reply_text(text, reply_markup=reply_markup)
    elif(usr[1].sel == None and usr[1].authed == 'now' and (update.message.from_user.id == update.message.chat_id)):
        res = Auth(update.message.text, update.message.from_user.id)
        if (res[0]):
            text = "Добро пожаловать, "+res[1]+"!\nВведите /start чтобы войти\nЗатем выберите предмет из списка"
            update.message.reply_text(text)
        else:
            update.message.reply_text("Что-то не так, попробуй еще")
    elif(usr[0] == False and usr[1].sel == None and (update.message.from_user.id == update.message.chat_id)):
        text = "Введите /start чтобы начать!\nЗатем выберите предмет из списка"
        update.message.reply_text(text)
    

def error(bot, update, error):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, error)


def main():
    """Start the bot."""

    TOKEN=cfg.tg_token
	
    if (cfg.socks_is_enabled)
        socks.set_default_proxy(socks.SOCKS5, cfg.socks_host, cfg.socks_port, True, cfg.socks_user,cfg.socks_pass)
        socket.socket = socks.socksocket

    updater = Updater(TOKEN)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("end", end))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(MessageHandler((Filters.text | Filters.photo | Filters.document), echo))
    dp.add_error_handler(error)
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()