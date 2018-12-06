from bunch import Bunch, Hashable_Bunch
import socket_util

import re
import json
import os.path
import logging

reply_end_re = re.compile("[^\s;]") # find last character which is not white space or ';'
def split_reply(reply):
    match = None
    for match in reply_end_re.finditer(reply):
        pass
    if not match:
        return [reply]
    end_index = match.end()
    if end_index != -1:
        reply = reply[:end_index]
    separator_index = reply.find('=')
    if separator_index == -1:
        separator_index = reply.find('?')
    if separator_index == -1:
        return [reply]

    return map(lambda x: x.strip(), [reply[0:separator_index]] + reply[separator_index+1:].split(': '))

def send_query(socket, query):
    socket_util.retry_interrupted(lambda: socket.send(query + "\n\r"))
    reply = socket_util.retry_interrupted(lambda: socket.recv(1024))

    peer = socket.getpeername()
    logging.debug("send '%s' to %s:%d, reply '%s'" % (query, peer[0], peer[1], reply))
    return reply

class QueryReturnCodeError(RuntimeError):
    def __init__(self, msg, code):
        super(QueryReturnCodeError, self).__init__(msg)
        self.return_code = code

def execute_query(socket, query, acceptable_replies = ["0", "1"]):
    # add a ';', if multiple commands get queued (because of timeouts), the command will at least be interpreted correctly (although the reply, if any, will not be as expected)
    reply = send_query(socket, query + ";")
    split = split_reply(reply)
    if split[1] not in acceptable_replies:
        raise QueryReturnCodeError("'%s' failed with reply '%s'" % (query, reply), split[1])
    return split

def get_machine(type_):
    file_name = os.path.join(os.path.split(__file__)[0], "config.json")
    with open(file_name, "r") as config_file:
        return [Hashable_Bunch(**x) for x in \
                json.load(config_file)[type_]]

def get_mark5s():
    return get_machine("mark5")

def get_local_flexbuffs():
    return get_machine("local_flexbuff")

def get_remote_flexbuffs():
    return get_machine("remote_flexbuff")

def get_file_machines():
    return get_machine("file")
