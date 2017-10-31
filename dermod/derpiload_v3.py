import gc
from threading import Thread
import os
import sys
from . import input_parser as ip
from settings_file import *
import socket
import time
try:
    import requests
except Exception:
    print("This app requires python-requests")


class Error(Exception):
    pass


class Timeouted(Error):
        def __init__(self):
            pass


class Timer(Thread):

    def __init__(self, to):
        Thread.__init__(self)
        self.time = to
    
    def run(self):
        time.sleep(self.time)
        raise Timeouted


class Loader(Thread):

    def __init__(self, url, fileid, fileform, is_proxy, proxy_ip, proxy_port, is_local=False):
        Thread.__init__(self)
        self.readiness = 0
        self.url = url
        self.id = fileid
        self.format = fileform
        self.raw_data = b''
        self.proxy = is_proxy
        self.ip = proxy_ip
        self.port = proxy_port
        self.local = is_local
        global suppressor
        if suppressor is True:
            suppress = open(os.devnull, 'w')
            sys.stderr = suppress

    def run(self):
        try:
            timer = Timer(time_wait)
            timer.start()
            if self.local is not False:
                try:
                    self.get_locally()
                except Exception:
                    self.get_raw_image()
            else:
                self.get_raw_image()
            self.writer()
        except Timeouted():
            pass
        self.readiness = 1
        del self.raw_data

    def get_locally(self):
        sock = socket.socket()
        sock.connect(self.local)
        request = f"GET /raw?id={self.id+'.'+self.format} HTTP/1.1"
        sock.sendall(request.encode())
        while True:
            k = sock.recv(1024)
            if not k:
                break
            else:
                self.raw_data += k
        sock.close()
        if self.raw_data == b'500':
            self.get_raw_image()

    def get_raw_image(self):
        if self.proxy is False:
            self.raw_data = requests.get(
                f"https:{self.url}", verify=False).content
        else:
            self.raw_data = requests.get(
                f"https:{self.url}",
                proxies=dict(https=f'socks5://{self.ip}:{self.port}'), verify=False).content

    def writer(self):
        try:
            open(images_path+self.id+'.'+self.format, 'rb')
        except FileNotFoundError:
            with open(images_path+self.id+'.'+self.format, 'wb') as file:
                file.write(self.raw_data)
                file.flush()
        else:
            pass


def udp_check():
    sock = socket.socket(socket.SOCK_DGRAM, socket.AF_INET, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    p = socket.gethostname()
    h = str.encode(p)
    sock.sendto(h, ('192.168.1.255', 29888))
    sock1 = socket.socket(socket.SOCK_DGRAM, socket.AF_INET, socket.IPPROTO_UDP)
    sock1.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock1.bind(('', 29889))
    sock1.settimeout(2)
    k = ''
    try:
        k = sock1.recv(1024)
        if k is not '' and k is not b'':
            k = k.decode()
            k = (socket.gethostbyname(k.split(":")[0]), int(k.split(":")[1]))
    except socket.timeout:
        pass
    del sock, sock1
    if k == '':
        print("\rNo servers found                 ", flush=True, end='')
        k = False
    else:
        print("\rServer found                     ", flush=True, end='')
    return k


class ThreadController(Thread):
    @staticmethod
    def log_debug(*args):
        j = ''
        for i in args:
            j += str(i)
        print("[DEBUG] " + str(j))

    def __init__(self):
        Thread.__init__(self)
        self.threads = []

    def run(self):
        self.watcher()

    def watcher(self):
        while True:
            time.sleep(1)
            p = 0
            for i in self.threads:
                if i.readiness == 1:
                    self.threads.remove(i)
                    del i
                    p = p + 1


def run(file):
    tc = ThreadController()
    tc.start()
    global suppressor, images_path, derpicdn_enable_proxy, socks5_proxy_ip, socks5_proxy_port
    if suppressor is True:
        suppress = open(os.devnull, 'w')
        sys.stderr = suppress
    try:
        os.mkdir(images_path)
    except FileExistsError:
        pass
    print("\rChecking for local servers..." + " "*16, flush=True, end='')
    k = udp_check()
    parsed = ip.name_tag_parser(file)
    chk = len(parsed)
    print("\rLoading Images" + " "*16, flush=True, end='')
    for i in range(chk):
        gc.collect()
        print(f"\rLoading image {i} of {chk} ({format((i/chk)*100, '.4g')}% done)" + " "*16, flush=True, end='')
        try:
            open(images_path+parsed[i][0]+'.'+parsed[i][1], 'rb')
        except FileNotFoundError:
            t = Loader(parsed[i][2],
                       parsed[i][0],
                       parsed[i][1],
                       derpicdn_enable_proxy,
                       socks5_proxy_ip,
                       socks5_proxy_port,
                       k)
            t.start()
            tc.threads.append(t)
        else:
            pass
    while len(tc.threads) > 0:
        print(f"\rWaiting {len(tc.threads)} thread(s) to end routine" + " "*16, flush=True, end='')
    del tc
